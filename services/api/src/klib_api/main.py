from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from klib_core import ForgeEngine, LibraryManager
from klib_core.errors import KlibError, LibraryNotFoundError
from klib_core.manifest import save_manifest
from klib_core.providers import get_provider
from pydantic import BaseModel, Field


class LibraryCreate(BaseModel):
    name: str
    id: str | None = None
    description: str = ""
    domain: str = "general"


class GlossaryCreate(BaseModel):
    source_term: str
    target_term: str
    notes: str = ""


class RuleCreate(BaseModel):
    body: str
    title: str = ""
    priority: int = Field(default=5, ge=1, le=10)


class ExampleCreate(BaseModel):
    input: str
    output: str
    task: str = ""
    mode: str = ""


class AskRequest(BaseModel):
    input: str
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


app = FastAPI(
    title="K-LIB Forge API",
    version="0.1.1",
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


def _error_response(status_code: int, detail: str) -> Any:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.1"}


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


@app.post("/examples/arabic-technical-translation/install", status_code=201)
def install_arabic_translation_example() -> dict[str, Any]:
    library_id = "arabic-technical-translation"
    forge = manager()
    try:
        forge.get(library_id)
        return {"created": False, "library": library_detail(library_id)}
    except LibraryNotFoundError:
        pass

    manifest = forge.create(
        "Arabic Technical Translation",
        library_id=library_id,
        description=(
            "A ready-to-run example for consistent English-to-Arabic "
            "software terminology."
        ),
        domain="translation/software",
    )
    manifest.languages = ["en", "ar"]
    manifest.default_mode = "developer_docs"
    manifest.supported_tasks = ["translate", "review_translation"]
    manifest.retrieval_policy.top_k = 6
    manifest.model_policy.default_provider = "mock"
    manifest.model_policy.default_model = "offline-demo"
    _, library_path = forge.get(library_id)
    save_manifest(library_path, manifest)
    forge.register(library_path)

    forge.add_glossary(
        library_id,
        "latency",
        "زمن الاستجابة",
        notes="Use in software and networking contexts.",
    )
    forge.add_glossary(
        library_id,
        "deployment",
        "النشر",
        notes="Use for software deployment.",
    )
    forge.add_rule(
        library_id,
        "Keep code identifiers, commands, file paths, API names, and model names in English.",
        title="Preserve technical identifiers",
        priority=1,
    )
    forge.add_rule(
        library_id,
        "Use the package glossary whenever a preferred technical term exists.",
        title="Follow preferred terminology",
        priority=2,
    )
    forge.add_example(
        library_id,
        "The server crashed after deployment.",
        "تعطل الخادم بعد النشر.",
        task="translate",
        mode="developer_docs",
    )

    with tempfile.TemporaryDirectory() as temporary_dir:
        source_path = Path(temporary_dir) / "software-translation-guide.md"
        source_path.write_text(
            "# Software translation guide\n\n"
            "Translate software behavior precisely and keep code identifiers in English. "
            "In networking and performance contexts, latency means زمن الاستجابة. "
            "Deployment means النشر when releasing software to an environment.\n",
            encoding="utf-8",
        )
        forge.add_sources(library_id, source_path)

    eval_data = {
        "id": "translation-latency-001",
        "name": "Translate latency and deployment consistently",
        "task": "translation",
        "input": "Translate: The app has high latency after deployment.",
        "checks": {
            "must_include": ["زمن الاستجابة", "النشر"],
            "must_not_include": ["تأخير"],
        },
    }
    (library_path / "evals" / "translation-latency-001.json").write_text(
        json.dumps(eval_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    engine().compile(library_id)
    return {"created": True, "library": library_detail(library_id)}


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


@app.post("/libraries/{library_id}/compile")
def compile_library(library_id: str) -> dict[str, Any]:
    return engine().compile(library_id).model_dump(mode="json")


@app.get("/libraries/{library_id}/search")
def search_library(library_id: str, q: str, top_k: int = 8) -> list[dict[str, Any]]:
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
def list_models() -> list[dict[str, str | None]]:
    return [
        {"provider": "ollama", "base_url": "http://localhost:11434/v1"},
        {"provider": "lmstudio", "base_url": "http://localhost:1234/v1"},
        {"provider": "nvidia", "base_url": "https://integrate.api.nvidia.com/v1"},
        {"provider": "openai", "base_url": "https://api.openai.com/v1"},
        {"provider": "openai-compatible", "base_url": os.getenv("OPENAI_BASE_URL")},
        {"provider": "mock", "base_url": None},
    ]


@app.post("/models/test")
def test_model(request: ModelTestRequest) -> dict[str, Any]:
    try:
        return get_provider(request.provider, base_url=request.base_url).test(request.model)
    except KlibError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def run() -> None:
    uvicorn.run(
        "klib_api.main:app",
        host=os.getenv("KLIB_API_HOST", "127.0.0.1"),
        port=int(os.getenv("KLIB_API_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
