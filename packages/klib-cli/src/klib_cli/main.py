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
from klib_core.examples import install_builtin_example, list_builtin_examples
from klib_core.library import slugify
from klib_core.medchem import (
    MedChemStore,
    conformer_3d_sdf,
    describe_molecule,
    initialize_medchem_library,
    medchem_source_catalog,
    safety_check,
    scaffold_for_smiles,
)
from klib_core.profiles import ModelProfileManager
from klib_core.providers import get_provider, provider_specs

app = typer.Typer(
    name="klib",
    help="Build, compile, test, and export portable AI knowledge libraries.",
    no_args_is_help=True,
)
glossary_app = typer.Typer(help="Manage glossary terms.")
rule_app = typer.Typer(help="Manage K-LIB rules.")
example_app = typer.Typer(help="Manage prompt examples.")
profile_app = typer.Typer(help="Manage reusable model profiles.")
medchem_app = typer.Typer(help="Build safe, research-only molecular evidence libraries.")
app.add_typer(glossary_app, name="glossary")
app.add_typer(rule_app, name="rule")
app.add_typer(example_app, name="example")
app.add_typer(profile_app, name="profile")
app.add_typer(medchem_app, name="medchem")


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def manager() -> LibraryManager:
    return LibraryManager()


def engine() -> ForgeEngine:
    return ForgeEngine(manager())


def profiles() -> ModelProfileManager:
    return ModelProfileManager(manager().home)


def medchem_store(library: str | None) -> MedChemStore:
    return MedChemStore(manager(), resolve_library(library))


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

    emit(provider_specs())


@app.command("example-catalog")
def example_catalog() -> None:
    """List advanced built-in example packages."""

    emit(list_builtin_examples())


@app.command("install-example")
def install_example(example_id: str) -> None:
    """Install and compile an advanced built-in example package."""

    def action() -> None:
        created, path = install_builtin_example(manager(), example_id)
        emit({"created": created, "id": example_id, "path": str(path)})

    run_command(action)


@app.command("model-test")
def model_test(
    provider: str = typer.Option("ollama"),
    model: str = typer.Option("gemma3"),
    base_url: str | None = typer.Option(None),
) -> None:
    """Test a model connector."""

    run_command(lambda: emit(get_provider(provider, base_url=base_url).test(model)))


@medchem_app.command("init")
def medchem_init(
    name: str = typer.Argument("MedChem-KLIB Lite"),
    library_id: str | None = typer.Option(None, "--id", help="Stable package id."),
    path: Path | None = typer.Option(None, help="Target directory."),
) -> None:
    """Create a research-only MedChem K-LIB package."""

    def action() -> None:
        target = path or Path.cwd() / slugify(library_id or name)
        manifest, library_path = initialize_medchem_library(
            manager(),
            name,
            library_id=library_id,
            path=target,
        )
        emit(
            {
                "created": str(library_path),
                "manifest": manifest.model_dump(mode="json"),
            }
        )

    run_command(action)


@medchem_app.command("import")
def medchem_import(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Import compounds from CSV, JSONL, SDF, SMI, or SMILES text."""

    run_command(lambda: emit(medchem_store(library).import_compounds(source)))


@medchem_app.command("sources")
def medchem_sources() -> None:
    """List supported and planned MedChem data providers with license notes."""

    emit(medchem_source_catalog())


@medchem_app.command("import-pubchem")
def medchem_import_pubchem(
    identifiers: list[str] = typer.Argument(
        ...,
        help="One or more PubChem names or CIDs.",
    ),
    library: str | None = typer.Option(None, "--library", "-l"),
    namespace: str = typer.Option(
        "name",
        "--namespace",
        help="PubChem lookup namespace: name or cid.",
    ),
    synonyms_limit: int = typer.Option(12, min=0, max=50),
) -> None:
    """Import compounds directly from PubChem PUG-REST."""

    run_command(
        lambda: emit(
            medchem_store(library).import_pubchem(
                identifiers,
                namespace=namespace,
                synonyms_limit=synonyms_limit,
            )
        )
    )


@medchem_app.command("import-targets")
def medchem_import_targets(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Import target registry records from CSV or JSONL."""

    run_command(lambda: emit(medchem_store(library).import_targets(source)))


@medchem_app.command("import-environments")
def medchem_import_environments(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Import lab, assay, or in-silico test environments from CSV or JSONL."""

    run_command(lambda: emit(medchem_store(library).import_environments(source)))


@medchem_app.command("import-bioactivity")
def medchem_import_bioactivity(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Import compound-target bioactivity records from CSV or JSONL."""

    run_command(lambda: emit(medchem_store(library).import_bioactivity(source)))


@medchem_app.command("import-literature")
def medchem_import_literature(
    source: Path = typer.Argument(..., exists=True, readable=True),
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Import literature records from CSV, JSONL, Markdown, or text."""

    run_command(lambda: emit(medchem_store(library).import_literature(source)))


@medchem_app.command("validate")
def medchem_validate(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Validate imported molecular structures with RDKit."""

    run_command(lambda: emit(medchem_store(library).validate()))


@medchem_app.command("compile")
def medchem_compile(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Canonicalize molecules and build descriptors and scaffold records."""

    run_command(lambda: emit(medchem_store(library).compile()))


@medchem_app.command("descriptors")
def medchem_descriptors(smiles: str) -> None:
    """Calculate research descriptors for one SMILES structure."""

    run_command(lambda: emit(describe_molecule(smiles)))


@medchem_app.command("scaffold")
def medchem_scaffold(smiles: str) -> None:
    """Extract the Bemis-Murcko scaffold for one SMILES structure."""

    run_command(lambda: emit(scaffold_for_smiles(smiles)))


@medchem_app.command("conformer")
def medchem_conformer(
    smiles: str,
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Generate a deterministic RDKit 3D conformer as SDF."""

    def action() -> None:
        sdf = conformer_3d_sdf(smiles)
        if output:
            destination = output.expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(sdf, encoding="utf-8")
            emit({"output": str(destination), "status": "research_reference_only"})
        else:
            typer.echo(sdf)

    run_command(action)


@medchem_app.command("search")
def medchem_search(
    query: str,
    library: str | None = typer.Option(None, "--library", "-l"),
    limit: int = typer.Option(20, min=1, max=500),
) -> None:
    """Search compiled compounds by id, name, synonym, SMILES, or InChIKey."""

    run_command(lambda: emit(medchem_store(library).search(query, limit)))


@medchem_app.command("similar")
def medchem_similar(
    smiles: str,
    library: str | None = typer.Option(None, "--library", "-l"),
    top_k: int = typer.Option(10, min=1, max=100),
) -> None:
    """Rank compiled compounds by Morgan-fingerprint Tanimoto similarity."""

    run_command(lambda: emit(medchem_store(library).similar(smiles, top_k)))


@medchem_app.command("evidence-status")
def medchem_evidence_status(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Check compound, target, bioactivity, and citation link integrity."""

    run_command(lambda: emit(medchem_store(library).evidence_status()))


@medchem_app.command("research")
def medchem_research(
    question: str,
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Generate a deterministic, citation-grounded compound research brief."""

    run_command(lambda: emit(medchem_store(library).research_brief(question)))


@medchem_app.command("agent")
def medchem_agent(
    question: str,
    library: str | None = typer.Option(None, "--library", "-l"),
    provider: str = typer.Option("mock", "--provider"),
    model: str = typer.Option("offline", "--model"),
    base_url: str | None = typer.Option(None, "--base-url"),
    pubchem: list[str] | None = typer.Option(
        None,
        "--pubchem",
        help="PubChem name or CID to import before the research pass. Repeatable.",
    ),
    pubchem_namespace: str = typer.Option("name", "--pubchem-namespace"),
    synonyms_limit: int = typer.Option(12, min=0, max=50),
    max_tokens: int = typer.Option(1600, min=128, max=32000),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Run the collect -> validate -> K-LIB context -> model research pipeline."""

    def action() -> None:
        report = medchem_store(library).research_agent(
            question,
            provider=provider,
            model=model,
            base_url=base_url,
            pubchem_identifiers=pubchem or [],
            pubchem_namespace=pubchem_namespace,
            synonyms_limit=synonyms_limit,
            options={"max_tokens": max_tokens},
        )
        if output:
            destination = output.expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            emit({"output": str(destination), "ready_for_review": report["ready_for_review"]})
        else:
            emit(report)

    run_command(action)


@medchem_app.command("evidence-evals")
def medchem_evidence_evals(
    library: str | None = typer.Option(None, "--library", "-l"),
) -> None:
    """Run link, citation, grounding, and safety regression checks."""

    run_command(lambda: emit(medchem_store(library).run_evidence_evals()))


@medchem_app.command("safety-check")
def medchem_safety_check(request: str) -> None:
    """Check whether a request is inside the research-only MedChem boundary."""

    emit(safety_check(request))


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
