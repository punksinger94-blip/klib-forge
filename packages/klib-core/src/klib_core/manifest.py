from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from .errors import ManifestValidationError
from .models import Manifest


def package_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas" / "manifest.schema.json"


def load_schema() -> dict[str, Any]:
    path = package_schema_path()
    if not path.exists():
        raise ManifestValidationError(f"Manifest schema is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest_data(data: dict[str, Any]) -> Manifest:
    errors = sorted(
        Draft202012Validator(load_schema()).iter_errors(data),
        key=lambda item: list(item.path),
    )
    if errors:
        message = "; ".join(error.message for error in errors)
        raise ManifestValidationError(message)
    try:
        return Manifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestValidationError(str(exc)) from exc


def load_manifest(library_path: Path) -> Manifest:
    manifest_path = library_path / "manifest.json"
    if not manifest_path.exists():
        raise ManifestValidationError(f"No manifest.json found in {library_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestValidationError(f"Cannot read manifest: {exc}") from exc
    return validate_manifest_data(data)


def save_manifest(library_path: Path, manifest: Manifest) -> None:
    path = library_path / "manifest.json"
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
