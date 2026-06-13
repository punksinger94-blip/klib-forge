from __future__ import annotations

import importlib.util
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from klib_core import ForgeEngine, LibraryManager, __version__
from klib_core.errors import KlibError, LibraryNotFoundError
from klib_core.examples import install_builtin_example, list_builtin_examples
from klib_core.profiles import ModelProfileManager
from klib_core.providers import get_provider, provider_specs
from pydantic import BaseModel, Field


class LibraryCreate(BaseModel):
    name: str = Field(min_length=1)
    id: str | None = None
    description: str = ""
    domain: str = "general"


class GlossaryCreate(BaseModel):
    source_term: str = Field(min_length=1)
    target_term: str = Field(min_length=1)
    notes: str = ""


class RuleCreate(BaseModel):
    body: str = Field(min_length=1)
    title: str = ""
    priority: int = Field(default=5, ge=1, le=10)


class ExampleCreate(BaseModel):
    input: str = Field(min_length=1)
    output: str = Field(min_length=1)
    task: str = ""
    mode: str = ""


class AskRequest(BaseModel):
    input: str = Field(min_length=1)
    provider: str | None = None
    model: str | None = None
    mode: str | None = None
    base_url: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class CorrectionCreate(BaseModel):
    input: str
    bad_output: str
    corrected_output: str
    lesson: str = ""
    create_eval: bool = True
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)


class EvalRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


class ModelTestRequest(BaseModel):
    provider: str
    model: str
    base_url: str | None = None


class LibraryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    languages: list[str] | None = None
    default_mode: str | None = None
    supported_tasks: list[str] | None = None
    retrieval_policy: dict[str, Any] | None = None
    model_policy: dict[str, Any] | None = None


class SourceUpdate(BaseModel):
    title: str | None = None
    trust_level: Literal["trusted", "user_added", "flagged", "blocked"] | None = None


class RuleUpdate(BaseModel):
    body: str = Field(min_length=1)
    title: str = ""
    priority: int = Field(default=5, ge=1, le=10)


class ExampleUpdate(BaseModel):
    input: str | None = None
    output: str | None = None
    task: str | None = None
    mode: str | None = None


class CorrectionReview(BaseModel):
    status: Literal["pending", "approved", "rejected"]


class SuggestionApply(BaseModel):
    kind: Literal["glossary", "rule", "example", "eval"]
    payload: dict[str, Any]


class EvalUpsert(BaseModel):
    id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    name: str = ""
    task: str = ""
    input: str = Field(min_length=1)
    checks: dict[str, Any] = Field(default_factory=dict)


class ArenaModel(BaseModel):
    name: str = ""
    provider: str
    model: str
    base_url: str | None = None


class ArenaRequest(BaseModel):
    models: list[ArenaModel] = Field(min_length=2)


class ProfileCreate(BaseModel):
    id: str | None = None
    name: str
    provider: str
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(
    title="K-LIB Forge API",
    version=__version__,
    description="Local-first API for building and running portable .klib packages.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "tauri://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def manager() -> LibraryManager:
    configured_home = os.getenv("KLIB_HOME")
    return LibraryManager(Path(configured_home) if configured_home else None)


def engine() -> ForgeEngine:
    return ForgeEngine(manager())


def profiles() -> ModelProfileManager:
    return ModelProfileManager(manager().home)


def library_detail(library_id: str) -> dict[str, Any]:
    forge = manager()
    manifest, path = forge.get(library_id)
    return {
        "manifest": manifest.model_dump(mode="json"),
        "path": str(path),
        "source_count": len(forge.sources(library_id)),
        "glossary_count": len(forge.glossary(library_id)),
        "rule_count": len(forge.rules(library_id)),
        "eval_count": len(forge.evals(library_id)),
    }


@app.exception_handler(KlibError)
async def handle_klib_error(_request: Any, exc: KlibError) -> Any:
    return _error_response(400, str(exc))


@app.exception_handler(LibraryNotFoundError)
async def handle_library_not_found(_request: Any, exc: LibraryNotFoundError) -> Any:
    return _error_response(404, str(exc))


def _error_response(status_code: int, detail: str) -> Any:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "version": __version__,
        "vector_adapters": {
            "local": True,
            "chroma": importlib.util.find_spec("chromadb") is not None,
            "qdrant": True,
        },
    }


@app.post("/libraries", status_code=201)
def create_library(request: LibraryCreate) -> dict[str, Any]:
    manifest = manager().create(
        request.name,
        library_id=request.id,
        description=request.description,
        domain=request.domain,
    )
    _, path = manager().get(manifest.id)
    return {"manifest": manifest.model_dump(mode="json"), "path": str(path)}


@app.get("/libraries")
def list_libraries() -> list[dict[str, Any]]:
    return manager().list()


@app.get("/libraries/{library_id}")
def get_library(library_id: str) -> dict[str, Any]:
    return library_detail(library_id)


@app.patch("/libraries/{library_id}")
def update_library(library_id: str, request: LibraryUpdate) -> dict[str, Any]:
    return manager().update_manifest(
        library_id,
        request.model_dump(exclude_none=True),
    ).model_dump(mode="json")


@app.get("/examples")
def builtin_examples() -> list[dict[str, Any]]:
    return list_builtin_examples()


@app.post("/examples/{example_id}/install", status_code=201)
def install_example(example_id: str) -> dict[str, Any]:
    created, _ = install_builtin_example(manager(), example_id)
    return {"created": created, "library": library_detail(example_id)}


@app.delete("/libraries/{library_id}", status_code=204)
def delete_library(library_id: str, remove_files: bool = False) -> None:
    manager().delete(library_id, remove_files=remove_files)


@app.post("/libraries/{library_id}/sources", status_code=201)
async def upload_source(
    library_id: str,
    file: UploadFile = File(...),
) -> list[dict[str, Any]]:
    suffix = Path(file.filename or "source.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
        shutil.copyfileobj(file.file, temporary)
        temporary_path = Path(temporary.name)
    try:
        return manager().add_sources(library_id, temporary_path)
    finally:
        temporary_path.unlink(missing_ok=True)


@app.post("/libraries/{library_id}/sources/path", status_code=201)
def add_source_path(library_id: str, path: str = Form(...)) -> list[dict[str, Any]]:
    return manager().add_sources(library_id, Path(path))


@app.get("/libraries/{library_id}/sources")
def list_sources(library_id: str) -> list[dict[str, Any]]:
    return manager().sources(library_id)


@app.patch("/libraries/{library_id}/sources/{source_id}")
def update_source(
    library_id: str,
    source_id: str,
    request: SourceUpdate,
) -> dict[str, Any]:
    return manager().update_source(
        library_id,
        source_id,
        title=request.title,
        trust_level=request.trust_level,
    )


@app.delete("/libraries/{library_id}/sources/{source_id}", status_code=204)
def delete_source(library_id: str, source_id: str) -> None:
    manager().delete_source(library_id, source_id)


@app.post("/libraries/{library_id}/glossary", status_code=201)
def create_glossary(library_id: str, request: GlossaryCreate) -> dict[str, Any]:
    return manager().add_glossary(
        library_id,
        request.source_term,
        request.target_term,
        notes=request.notes,
    )


@app.get("/libraries/{library_id}/glossary")
def list_glossary(library_id: str) -> list[dict[str, Any]]:
    return manager().glossary(library_id)


@app.delete("/libraries/{library_id}/glossary/{entry_id}", status_code=204)
def delete_glossary(library_id: str, entry_id: str) -> None:
    manager().delete_glossary(library_id, entry_id)


@app.post("/libraries/{library_id}/rules", status_code=201)
def create_rule(library_id: str, request: RuleCreate) -> dict[str, Any]:
    return manager().add_rule(
        library_id,
        request.body,
        title=request.title,
        priority=request.priority,
    )


@app.get("/libraries/{library_id}/rules")
def list_rules(library_id: str) -> list[dict[str, Any]]:
    return manager().rules(library_id)


@app.put("/libraries/{library_id}/rules/{rule_id}")
def update_rule(library_id: str, rule_id: str, request: RuleUpdate) -> dict[str, Any]:
    return manager().update_rule(
        library_id,
        rule_id,
        title=request.title,
        body=request.body,
        priority=request.priority,
    )


@app.delete("/libraries/{library_id}/rules/{rule_id}", status_code=204)
def delete_rule(library_id: str, rule_id: str) -> None:
    manager().delete_rule(library_id, rule_id)


@app.post("/libraries/{library_id}/examples", status_code=201)
def create_example(library_id: str, request: ExampleCreate) -> dict[str, Any]:
    return manager().add_example(
        library_id,
        request.input,
        request.output,
        task=request.task,
        mode=request.mode,
    )


@app.get("/libraries/{library_id}/examples")
def list_examples(library_id: str) -> list[dict[str, Any]]:
    return manager().examples(library_id)


@app.patch("/libraries/{library_id}/examples/{example_id}")
def update_example(
    library_id: str,
    example_id: str,
    request: ExampleUpdate,
) -> dict[str, Any]:
    return manager().update_example(
        library_id,
        example_id,
        request.model_dump(exclude_none=True),
    )


@app.delete("/libraries/{library_id}/examples/{example_id}", status_code=204)
def delete_example(library_id: str, example_id: str) -> None:
    manager().delete_example(library_id, example_id)


@app.get("/libraries/{library_id}/evals")
def list_evals(library_id: str) -> list[dict[str, Any]]:
    return manager().evals(library_id)


@app.post("/libraries/{library_id}/evals", status_code=201)
def save_eval(library_id: str, request: EvalUpsert) -> dict[str, Any]:
    return manager().save_eval(
        library_id,
        request.model_dump(exclude_none=True),
    )


@app.delete("/libraries/{library_id}/evals/{eval_id}", status_code=204)
def delete_eval(library_id: str, eval_id: str) -> None:
    manager().delete_eval(library_id, eval_id)


@app.post("/libraries/{library_id}/compile")
def compile_library(library_id: str) -> dict[str, Any]:
    return engine().compile(library_id).model_dump(mode="json")


@app.get("/libraries/{library_id}/search")
def search_library(
    library_id: str,
    q: str = Query(min_length=1),
    top_k: int = Query(default=8, ge=1, le=50),
) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json")
        for item in engine().search(library_id, q, top_k)
    ]


@app.post("/libraries/{library_id}/ask")
def ask_library(library_id: str, request: AskRequest) -> dict[str, Any]:
    return engine().ask(
        library_id,
        request.input,
        provider=request.provider,
        model=request.model,
        mode=request.mode,
        base_url=request.base_url,
        options=request.options,
    ).model_dump(mode="json")


@app.post("/libraries/{library_id}/correct", status_code=201)
def correct_output(library_id: str, request: CorrectionCreate) -> dict[str, Any]:
    return engine().correct(
        library_id,
        input_text=request.input,
        bad_output=request.bad_output,
        corrected_output=request.corrected_output,
        lesson=request.lesson,
        create_eval=request.create_eval,
        must_include=request.must_include or None,
        must_not_include=request.must_not_include or None,
    )


@app.get("/libraries/{library_id}/corrections")
def list_corrections(library_id: str) -> list[dict[str, Any]]:
    return manager().corrections(library_id)


@app.post("/libraries/{library_id}/corrections/{correction_id}/review")
def review_correction(
    library_id: str,
    correction_id: str,
    request: CorrectionReview,
) -> dict[str, Any]:
    return manager().review_correction(library_id, correction_id, request.status)


@app.get("/libraries/{library_id}/suggestions")
def list_suggestions(library_id: str) -> list[dict[str, Any]]:
    return engine().suggestions(library_id)


@app.post("/libraries/{library_id}/suggestions/apply", status_code=201)
def apply_suggestion(library_id: str, request: SuggestionApply) -> dict[str, Any]:
    return engine().apply_suggestion(library_id, request.kind, request.payload)


@app.post("/libraries/{library_id}/eval")
def evaluate_library(library_id: str, request: EvalRequest) -> list[dict[str, Any]]:
    return [
        item.model_dump(mode="json")
        for item in engine().run_evals(
            library_id,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
        )
    ]


@app.post("/libraries/{library_id}/arena")
def evaluate_arena(library_id: str, request: ArenaRequest) -> dict[str, Any]:
    return engine().compare_models(
        library_id,
        [item.model_dump(mode="json") for item in request.models],
    )


@app.get("/libraries/{library_id}/runs")
def list_runs(library_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return manager().model_runs(library_id, min(max(limit, 1), 500))


@app.get("/libraries/{library_id}/eval-runs")
def list_eval_runs(library_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return manager().eval_runs(library_id, min(max(limit, 1), 500))


@app.get("/libraries/{library_id}/trust")
def library_trust(library_id: str) -> list[dict[str, Any]]:
    return manager().trust_reports(library_id)


@app.post("/libraries/{library_id}/diff")
def diff_library(library_id: str) -> dict[str, Any]:
    return engine().diff(library_id).model_dump(mode="json")


@app.post("/libraries/{library_id}/export")
def export_library(library_id: str) -> FileResponse:
    output_dir = manager().home / "exports"
    output = manager().export(library_id, output_dir / f"{library_id}.klib")
    return FileResponse(output, filename=output.name, media_type="application/zip")


@app.post("/libraries/import", status_code=201)
async def import_library(file: UploadFile = File(...)) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".klib") as temporary:
        shutil.copyfileobj(file.file, temporary)
        archive = Path(temporary.name)
    try:
        manifest = manager().import_package(archive)
        return manifest.model_dump(mode="json")
    finally:
        archive.unlink(missing_ok=True)


@app.get("/models")
def list_models() -> list[dict[str, Any]]:
    return provider_specs()


@app.post("/models/test")
def test_model(request: ModelTestRequest) -> dict[str, Any]:
    try:
        return get_provider(request.provider, base_url=request.base_url).test(request.model)
    except KlibError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/model-profiles")
def list_model_profiles() -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in profiles().list()]


@app.post("/model-profiles", status_code=201)
def save_model_profile(request: ProfileCreate) -> dict[str, Any]:
    return profiles().create(
        name=request.name,
        provider=request.provider,
        model=request.model,
        base_url=request.base_url,
        api_key_env=request.api_key_env,
        options=request.options,
        profile_id=request.id,
    ).model_dump(mode="json")


@app.delete("/model-profiles/{profile_id}", status_code=204)
def delete_model_profile(profile_id: str) -> None:
    profiles().delete(profile_id)


def run() -> None:
    uvicorn.run(
        "klib_api.main:app",
        host=os.getenv("KLIB_API_HOST", "127.0.0.1"),
        port=int(os.getenv("KLIB_API_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
