from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import typer
from klib_core import ForgeEngine, LibraryManager
from klib_core.benchmarks import (
    BIOLOGY_BENCHMARK_ID,
    BIOLOGY_BENCHMARK_MODEL,
    LITERATURE_BIOLOGY_BENCHMARK_ID,
    install_biology_benchmark,
    install_literature_biology_benchmark,
)
from klib_core.errors import KlibError
from klib_core.library import slugify
from klib_core.profiles import ModelProfileManager
from klib_core.providers import get_provider

app = typer.Typer(
    name="klib",
    help="Build, compile, test, and export portable AI knowledge libraries.",
    no_args_is_help=True,
)
glossary_app = typer.Typer(help="Manage glossary terms.")
rule_app = typer.Typer(help="Manage K-LIB rules.")
example_app = typer.Typer(help="Manage prompt examples.")
profile_app = typer.Typer(help="Manage reusable model profiles.")
app.add_typer(glossary_app, name="glossary")
app.add_typer(rule_app, name="rule")
app.add_typer(example_app, name="example")
app.add_typer(profile_app, name="profile")


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def manager() -> LibraryManager:
    return LibraryManager()


def engine() -> ForgeEngine:
    return ForgeEngine(manager())


def profiles() -> ModelProfileManager:
    return ModelProfileManager(manager().home)


def emit(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


def resolve_library(value: str | None) -> str | Path:
    if value:
        return value
    current = Path.cwd()
    for candidate in (current, *current.parents):
        if (candidate / "manifest.json").exists():
            return candidate
    libraries = manager().list()
    if len(libraries) == 1:
        return libraries[0]["id"]
    raise typer.BadParameter("Use --library ID or run the command inside a .klib folder")


def run_command(callback: Any) -> None:
    try:
        callback()
    except (KlibError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc


@app.command("init")
def init_library(
    name: str = typer.Argument(..., help="Human-readable library name or id."),
    library_id: str | None = typer.Option(None, "--id", help="Stable package id."),
    domain: str = typer.Option("general", help="Knowledge domain."),
    description: str = typer.Option("", help="Short package description."),
    path: Path | None = typer.Option(None, help="Target directory."),
) -> None:
    """Create a new .klib package folder."""

    def action() -> None:
        target = path or Path.cwd() / slugify(library_id or name)
        manifest = manager().create(
            name,
            library_id=library_id,
            description=description,
            domain=domain,
            path=target,
        )
        emit({"created": str(target.resolve()), "manifest": manifest.model_dump(mode="json")})

    run_command(action)


@app.command("list")
def list_libraries() -> None:
    """List registered K-LIB packages."""

    emit(manager().list())


@app.command("info")
def library_info(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Show a package manifest and local path."""

    def action() -> None:
        manifest, path = manager().get(resolve_library(library))
        emit({"path": str(path), "manifest": manifest.model_dump(mode="json")})

    run_command(action)


@app.command("add")
def add_sources(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Add supported source files from a file or directory."""

    run_command(lambda: emit(manager().add_sources(resolve_library(library), source)))


@app.command("compile")
def compile_library(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Compile sources into chunks and a local retrieval index."""

    run_command(lambda: emit(engine().compile(resolve_library(library))))


@app.command("search")
def search_library(
    query: str,
    library: str | None = typer.Option(None, "--library", "-l"),
    top_k: int = typer.Option(8, min=1, max=50),
) -> None:
    """Search the compiled local index."""

    run_command(
        lambda: emit(
            [
                item.model_dump(mode="json")
                for item in engine().search(resolve_library(library), query, top_k)
            ]
        )
    )


@app.command("suggest")
def suggest_knowledge_assets(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Suggest glossary terms, rules, examples, and evals from package sources."""

    run_command(lambda: emit(engine().suggestions(resolve_library(library))))


@app.command("trust")
def trust_report(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Show source trust levels and prompt-injection findings."""

    run_command(lambda: emit(manager().trust_reports(resolve_library(library))))


@app.command("runs")
def run_history(
    library: str | None = typer.Option(None, "--library", "-l"),
    limit: int = typer.Option(50, min=1, max=500),
) -> None:
    """Show local model run history with assembled prompts."""

    run_command(lambda: emit(manager().model_runs(resolve_library(library), limit)))


@app.command("ask")
def ask_library(
    prompt: str,
    library: str | None = typer.Option(None, "--library", "-l"),
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    mode: str | None = typer.Option(None),
    base_url: str | None = typer.Option(None),
) -> None:
    """Ask a model using K-LIB rules and retrieved context."""

    run_command(
        lambda: emit(
            engine().ask(
                resolve_library(library),
                prompt,
                provider=provider,
                model=model,
                mode=mode,
                base_url=base_url,
            )
        )
    )


@app.command("correct")
def correct_output(
    input_text: str = typer.Option(..., "--input"),
    bad_output: str = typer.Option(..., "--bad-output"),
    corrected_output: str = typer.Option(..., "--corrected-output"),
    lesson: str = typer.Option(""),
    library: str | None = typer.Option(None, "--library", "-l"),
    create_eval: bool = typer.Option(True, "--create-eval/--no-create-eval"),
) -> None:
    """Save a correction and optionally create a regression eval."""

    run_command(
        lambda: emit(
            engine().correct(
                resolve_library(library),
                input_text=input_text,
                bad_output=bad_output,
                corrected_output=corrected_output,
                lesson=lesson,
                create_eval=create_eval,
            )
        )
    )


@app.command("eval")
def run_evals(
    library: str | None = typer.Option(None, "--library", "-l"),
    provider: str | None = typer.Option(None),
    model: str | None = typer.Option(None),
    base_url: str | None = typer.Option(None),
) -> None:
    """Run all package evals against a model."""

    run_command(
        lambda: emit(
            [
                item.model_dump(mode="json")
                for item in engine().run_evals(
                    resolve_library(library),
                    provider=provider,
                    model=model,
                    base_url=base_url,
                )
            ]
        )
    )


@app.command("arena")
def run_arena(
    candidates: list[str] = typer.Option(
        ...,
        "--candidate",
        help="Repeat provider:model, for example --candidate mock:offline-demo.",
    ),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Compare two or more model configurations on package evals."""

    configurations = []
    for candidate in candidates:
        if ":" not in candidate:
            raise typer.BadParameter("Candidates must use provider:model")
        provider, model = candidate.split(":", 1)
        configurations.append(
            {"name": candidate, "provider": provider, "model": model}
        )
    run_command(
        lambda: emit(
            engine().compare_models(resolve_library(library), configurations)
        )
    )


@app.command("nvidia-ab")
def run_nvidia_ab(
    model: str = typer.Option(
        BIOLOGY_BENCHMARK_MODEL,
        help="NVIDIA model id used for both conditions.",
    ),
    repeats: int = typer.Option(1, min=1, max=10),
    crossover: bool = typer.Option(
        False,
        "--crossover/--no-crossover",
        help="Repeat with the two API key slots swapped.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Optional path for a combined JSON report.",
    ),
) -> None:
    """Compare a raw NVIDIA model with the same model plus a biology K-LIB."""
    _run_nvidia_ab(
        benchmark_id=BIOLOGY_BENCHMARK_ID,
        installer=install_biology_benchmark,
        model=model,
        repeats=repeats,
        crossover=crossover,
        output=output,
    )


@app.command("nvidia-literature-ab")
def run_nvidia_literature_ab(
    model: str = typer.Option(
        BIOLOGY_BENCHMARK_MODEL,
        help="NVIDIA model id used for both conditions.",
    ),
    repeats: int = typer.Option(1, min=1, max=10),
    crossover: bool = typer.Option(
        False,
        "--crossover/--no-crossover",
        help="Repeat with the two API key slots swapped.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Optional path for a combined JSON report.",
    ),
) -> None:
    """Compare a raw NVIDIA model with a primary-literature biology K-LIB."""
    _run_nvidia_ab(
        benchmark_id=LITERATURE_BIOLOGY_BENCHMARK_ID,
        installer=install_literature_biology_benchmark,
        model=model,
        repeats=repeats,
        crossover=crossover,
        output=output,
    )


def _run_nvidia_ab(
    *,
    benchmark_id: str,
    installer: Any,
    model: str,
    repeats: int,
    crossover: bool,
    output: Path | None,
) -> None:

    def action() -> None:
        baseline_key = os.getenv("NVIDIA_BASELINE_API_KEY")
        klib_key = os.getenv("NVIDIA_KLIB_API_KEY")
        if not baseline_key or not klib_key:
            raise KlibError(
                "Set NVIDIA_BASELINE_API_KEY and NVIDIA_KLIB_API_KEY in the "
                "current process before running this command"
            )

        forge = manager()
        library_path = installer(forge, model=model)
        comparison_engine = ForgeEngine(forge)
        reports = [
            comparison_engine.compare_evals(
                benchmark_id,
                provider="nvidia",
                model=model,
                baseline_api_key=baseline_key,
                klib_api_key=klib_key,
                base_url="https://integrate.api.nvidia.com/v1",
                repeats=repeats,
                baseline_key_label="NVIDIA_BASELINE_API_KEY",
                klib_key_label="NVIDIA_KLIB_API_KEY",
            )
        ]
        if crossover:
            reports.append(
                comparison_engine.compare_evals(
                    benchmark_id,
                    provider="nvidia",
                    model=model,
                    baseline_api_key=klib_key,
                    klib_api_key=baseline_key,
                    base_url="https://integrate.api.nvidia.com/v1",
                    repeats=repeats,
                    baseline_key_label="NVIDIA_KLIB_API_KEY",
                    klib_key_label="NVIDIA_BASELINE_API_KEY",
                )
            )

        result = {
            "library_path": str(library_path),
            "model": model,
            "crossover": crossover,
            "reports": reports,
        }
        if output:
            destination = output.expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result["combined_report_path"] = str(destination)
        emit(result)

    run_command(action)


@app.command("diff")
def diff_library(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Compare current knowledge with the latest compiled snapshot."""

    run_command(lambda: emit(engine().diff(resolve_library(library))))


@app.command("export")
def export_library(
    destination: Path,
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Export a package as a .klib ZIP archive."""

    run_command(
        lambda: emit(
            {"exported": str(manager().export(resolve_library(library), destination))}
        )
    )


@app.command("import")
def import_library(
    archive: Path = typer.Argument(..., exists=True, readable=True),
    destination: Path | None = typer.Option(None),
) -> None:
    """Import and register a .klib package."""

    run_command(
        lambda: emit(
            manager().import_package(archive, destination).model_dump(mode="json")
        )
    )


@app.command("models")
def models() -> None:
    """List built-in model connector types."""

    emit(
        [
            {"provider": "ollama", "default_base_url": "http://localhost:11434/v1"},
            {"provider": "lmstudio", "default_base_url": "http://localhost:1234/v1"},
            {
                "provider": "nvidia",
                "default_base_url": "https://integrate.api.nvidia.com/v1",
            },
            {"provider": "openai", "default_base_url": "https://api.openai.com/v1"},
            {"provider": "openai-compatible", "default_base_url": "OPENAI_BASE_URL"},
            {"provider": "mock", "default_base_url": None},
        ]
    )


@app.command("model-test")
def model_test(
    provider: str = typer.Option("ollama"),
    model: str = typer.Option("gemma3"),
    base_url: str | None = typer.Option(None),
) -> None:
    """Test a model connector."""

    run_command(lambda: emit(get_provider(provider, base_url=base_url).test(model)))


@glossary_app.command("add")
def glossary_add(
    source_term: str,
    target_term: str,
    notes: str = typer.Option(""),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(
        lambda: emit(
            manager().add_glossary(resolve_library(library), source_term, target_term, notes=notes)
        )
    )


@glossary_app.command("list")
def glossary_list(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(lambda: emit(manager().glossary(resolve_library(library))))


@rule_app.command("add")
def rule_add(
    body: str,
    title: str = typer.Option(""),
    priority: int = typer.Option(5, min=1, max=10),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(
        lambda: emit(
            manager().add_rule(
                resolve_library(library),
                body,
                title=title,
                priority=priority,
            )
        )
    )


@rule_app.command("list")
def rule_list(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(lambda: emit(manager().rules(resolve_library(library))))


@example_app.command("add")
def example_add(
    input_text: str = typer.Option(..., "--input"),
    output_text: str = typer.Option(..., "--output"),
    task: str = typer.Option(""),
    mode: str = typer.Option(""),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(
        lambda: emit(
            manager().add_example(
                resolve_library(library),
                input_text,
                output_text,
                task=task,
                mode=mode,
            )
        )
    )


@example_app.command("list")
def example_list(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    run_command(lambda: emit(manager().examples(resolve_library(library))))


@profile_app.command("add")
def profile_add(
    name: str,
    provider: str = typer.Option(...),
    model: str = typer.Option(...),
    base_url: str | None = typer.Option(None),
    api_key_env: str | None = typer.Option(None),
) -> None:
    """Save a model profile without storing the credential value."""

    run_command(
        lambda: emit(
            profiles().create(
                name=name,
                provider=provider,
                model=model,
                base_url=base_url,
                api_key_env=api_key_env,
            )
        )
    )


@profile_app.command("list")
def profile_list() -> None:
    emit([item.model_dump(mode="json") for item in profiles().list()])


@profile_app.command("delete")
def profile_delete(profile_id: str) -> None:
    run_command(lambda: profiles().delete(profile_id))


if __name__ == "__main__":
    app()
