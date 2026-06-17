from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from klib_core.engine import ForgeEngine
from klib_core.examples import install_builtin_example
from klib_core.library import LibraryManager
from klib_core.providers import get_provider

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ID = "biomedical-evidence-synthesis"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a real-world public primary-literature A/B test: NVIDIA alone "
            "versus Hermes Agent using K-LIB Forge MCP tools."
        )
    )
    parser.add_argument("--model", default="minimaxai/minimax-m3")
    parser.add_argument("--hermes-provider", default="nvidia")
    parser.add_argument("--library", default=LIBRARY_ID)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--limit", type=int, default=0, help="Optional task limit for smoke runs.")
    parser.add_argument(
        "--hermes-timeout",
        type=int,
        default=180,
        help="Seconds to wait for each Hermes + K-LIB answer before stopping it.",
    )
    parser.add_argument(
        "--hermes-max-turns",
        type=int,
        default=12,
        help="Maximum Hermes agent turns for each K-LIB answer.",
    )
    parser.add_argument(
        "--no-prompt-key",
        action="store_true",
        help="Fail instead of prompting for key.",
    )
    args = parser.parse_args()

    hermes_env = read_env_file(hermes_env_path())
    baseline_key = (
        os.getenv("NVIDIA_API_KEY")
        or os.getenv("NVIDIA_BASELINE_API_KEY")
        or os.getenv("NVIDIA_KLIB_API_KEY")
        or hermes_env.get("NVIDIA_API_KEY")
        or hermes_env.get("NVIDIA_BASELINE_API_KEY")
        or hermes_env.get("NVIDIA_KLIB_API_KEY")
    )
    hermes_key = (
        os.getenv("NVIDIA_KLIB_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
        or hermes_env.get("NVIDIA_KLIB_API_KEY")
        or hermes_env.get("NVIDIA_API_KEY")
    )
    if not baseline_key and not args.no_prompt_key:
        baseline_key = getpass.getpass("NVIDIA baseline API key: ")
    if not baseline_key:
        raise SystemExit(
            "NVIDIA_API_KEY is not set. Set it, or run without "
            "--no-prompt-key to enter it securely."
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    output = (
        args.output
        or ROOT / "build" / "experiments" / f"hermes-nvidia-public-ab-{timestamp}.json"
    ).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    manager = LibraryManager()
    created, library_path = install_builtin_example(manager, args.library)
    engine = ForgeEngine(manager)
    evals = manager.evals(args.library)
    if args.limit > 0:
        evals = evals[: args.limit]
    if not evals:
        raise SystemExit(f"No evals found for library {args.library!r}.")

    hermes_mcp_test = run_command(
        ["hermes", "mcp", "test", "klib_forge"],
        env=os.environ.copy(),
        timeout=60,
    )
    if hermes_mcp_test["exit_code"] != 0:
        raise SystemExit(f"Hermes MCP test failed:\n{hermes_mcp_test['output']}")

    provider = get_provider(
        "nvidia",
        base_url=NVIDIA_BASE_URL,
        api_key=baseline_key,
    )
    common_options = {"temperature": 0, "max_tokens": 900}
    results = []
    for eval_data in evals:
        task_id = eval_data["id"]
        question = eval_data["input"]
        checks = eval_data.get("checks", {})

        baseline_started = time.perf_counter()
        baseline_output = provider.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Answer from your pretrained model knowledge only. Do not use tools, "
                        "K-LIB, web search, or local files. If exact paper-specific details are "
                        "unknown, say unknown rather than guessing."
                    ),
                },
                {"role": "user", "content": question},
            ],
            args.model,
            common_options,
        )
        baseline_latency_ms = round((time.perf_counter() - baseline_started) * 1000)
        baseline_checks, baseline_score = engine._score_output(baseline_output, checks)

        hermes_prompt = build_hermes_prompt(args.library, question)
        hermes_started = time.perf_counter()
        hermes_run = invoke_hermes(
            hermes_prompt,
            model=args.model,
            provider=args.hermes_provider,
            api_key=hermes_key,
            timeout=args.hermes_timeout,
            max_turns=args.hermes_max_turns,
        )
        hermes_latency_ms = round((time.perf_counter() - hermes_started) * 1000)
        if hermes_run["exit_code"] != 0:
            hermes_output = hermes_run["output"]
            hermes_checks = []
            hermes_score = 0.0
        else:
            hermes_output = hermes_run["output"]
            hermes_checks, hermes_score = engine._score_output(hermes_output, checks)

        results.append(
            {
                "task_id": task_id,
                "name": eval_data.get("name", task_id),
                "question": question,
                "checks": checks,
                "baseline": {
                    "label": "nvidia_without_k_lib",
                    "score": baseline_score,
                    "latency_ms": baseline_latency_ms,
                    "output": baseline_output,
                    "checks": [item.model_dump(mode="json") for item in baseline_checks],
                },
                "hermes_klib": {
                    "label": "hermes_agent_with_klib_forge_mcp",
                    "score": hermes_score,
                    "latency_ms": hermes_latency_ms,
                    "exit_code": hermes_run["exit_code"],
                    "output": hermes_output,
                    "checks": [item.model_dump(mode="json") for item in hermes_checks],
                },
                "score_delta": round(hermes_score - baseline_score, 2),
            }
        )

    baseline_average = round(sum(item["baseline"]["score"] for item in results) / len(results), 2)
    hermes_average = round(sum(item["hermes_klib"]["score"] for item in results) / len(results), 2)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "benchmark": "Hermes Agent + NVIDIA Public Primary-Literature A/B",
        "scope": (
            "Public-world primary literature questions. Baseline calls NVIDIA directly "
            "without tools. Treatment calls Hermes Agent chat -Q with the same NVIDIA "
            "model and requires K-LIB Forge MCP search over the biomedical evidence "
            "package."
        ),
        "provider": "nvidia",
        "model": args.model,
        "hermes_provider": args.hermes_provider,
        "library_id": args.library,
        "library_path": str(library_path),
        "library_created": created,
        "mcp_test": hermes_mcp_test["output"],
        "baseline_average": baseline_average,
        "hermes_klib_average": hermes_average,
        "score_delta": round(hermes_average - baseline_average, 2),
        "results": results,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = output.with_suffix(".md")
    markdown.write_text(render_markdown(report), encoding="utf-8")

    print(f"Model: {args.model}")
    print(f"Without K-LIB: {baseline_average:.2f}")
    print(f"Hermes + K-LIB: {hermes_average:.2f}")
    print(f"Delta: {report['score_delta']:+.2f}")
    for result in results:
        print(
            f"- {result['task_id']}: "
            f"{result['baseline']['score']:.2f} -> "
            f"{result['hermes_klib']['score']:.2f}"
        )
    print(f"Report: {output}")
    print(f"Summary: {markdown}")


def build_hermes_prompt(library_id: str, question: str) -> str:
    return f"""
Use only the klib_forge MCP tool `klib_search`.
Search K-LIB package `{library_id}` with this exact query:
{question}

Rules:
- Use K-LIB evidence, not memory, for paper-specific facts.
- Include exact identifiers, quantities, and mechanisms.
- Include numeric citations like [1] from the retrieved evidence.
- Do not use web, browser, terminal, files, or any non-K-LIB source.
- If K-LIB search returns no relevant evidence, say that explicitly.

Question:
{question}
""".strip()


def invoke_hermes(
    prompt: str,
    *,
    model: str,
    provider: str,
    api_key: str | None,
    timeout: int,
    max_turns: int,
) -> dict[str, Any]:
    env = {
        **os.environ,
        "HERMES_ACCEPT_HOOKS": "1",
        "HERMES_INFERENCE_MODEL": model,
    }
    if api_key:
        env["NVIDIA_API_KEY"] = api_key
        env["OPENAI_API_KEY"] = api_key
        env["OPENAI_BASE_URL"] = NVIDIA_BASE_URL
    return run_command(
        [
            "hermes",
            "chat",
            "-Q",
            "--accept-hooks",
            "--ignore-rules",
            "--provider",
            provider,
            "-m",
            model,
            "--max-turns",
            str(max_turns),
            "-q",
            prompt,
        ],
        env=env,
        timeout=timeout,
    )


def run_command(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: int | None = None,
) -> dict[str, Any]:
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process_tree(process.pid)
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
    output = "\n".join(
        part.strip()
        for part in (stdout, stderr)
        if part and part.strip()
    )
    if timed_out:
        timeout_message = f"Timed out after {timeout} seconds; stopped process tree."
        output = "\n".join(part for part in (timeout_message, output) if part)
    return {"exit_code": 124 if timed_out else process.returncode, "output": output}


def stop_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def hermes_env_path() -> Path | None:
    command = ["hermes", "config", "env-path"]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    path = Path(completed.stdout.strip())
    return path if path.exists() else None


def read_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes Agent + NVIDIA Public Primary-Literature A/B",
        "",
        f"- Created: `{report['created_at']}`",
        f"- Model: `{report['model']}`",
        f"- Library: `{report['library_id']}`",
        f"- Without K-LIB: `{report['baseline_average']:.2f}`",
        f"- Hermes + K-LIB: `{report['hermes_klib_average']:.2f}`",
        f"- Delta: `{report['score_delta']:+.2f}`",
        "",
        "| Task | NVIDIA Only | Hermes + K-LIB | Delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["results"]:
        lines.append(
            "| "
            f"{item['task_id']} | "
            f"{item['baseline']['score']:.2f} | "
            f"{item['hermes_klib']['score']:.2f} | "
            f"{item['score_delta']:+.2f} |"
        )
    lines.extend(["", "## Notes", "", report["scope"], ""])
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
