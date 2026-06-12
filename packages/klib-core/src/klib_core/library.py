from __future__ import annotations

import json
import re
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Any

from .database import Database
from .errors import KlibError, LibraryNotFoundError, ManifestValidationError
from .files import iter_source_files
from .manifest import load_manifest, save_manifest
from .models import Manifest, utc_now

PACKAGE_DIRECTORIES = (
    "sources",
    "chunks",
    "evals",
    "prompts",
    "policies",
    "indexes",
    "runs",
    "build",
    "build/snapshots",
)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise KlibError("Library name must contain letters or numbers")
    return slug


class LibraryManager:
    def __init__(self, home: Path | None = None):
        self.home = (home or Path.home() / ".klib-forge").resolve()
        self.libraries_dir = self.home / "libraries"
        self.libraries_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.home / "forge.db")

    def create(
        self,
        name: str,
        *,
        library_id: str | None = None,
        description: str = "",
        domain: str = "general",
        path: Path | None = None,
    ) -> Manifest:
        resolved_id = slugify(library_id or name)
        library_path = (path or self.libraries_dir / resolved_id).resolve()
        if library_path.exists() and any(library_path.iterdir()):
            raise KlibError(f"Target directory is not empty: {library_path}")
        library_path.mkdir(parents=True, exist_ok=True)
        for directory in PACKAGE_DIRECTORIES:
            (library_path / directory).mkdir(parents=True, exist_ok=True)
        manifest = Manifest(
            id=resolved_id,
            name=name,
            description=description,
            domain=domain,
        )
        save_manifest(library_path, manifest)
        self._write_json(library_path / "glossary.json", [])
        (library_path / "rules.md").write_text("# Rules\n", encoding="utf-8")
        (library_path / "examples.jsonl").touch()
        (library_path / "corrections.jsonl").touch()
        self.register(library_path)
        return manifest

    def register(self, library_path: Path) -> Manifest:
        library_path = library_path.resolve()
        manifest = load_manifest(library_path)
        self.db.execute(
            """
            INSERT INTO libraries (
                id, name, description, domain, version, path, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                domain=excluded.domain,
                version=excluded.version,
                path=excluded.path,
                updated_at=excluded.updated_at
            """,
            (
                manifest.id,
                manifest.name,
                manifest.description,
                manifest.domain,
                manifest.version,
                str(library_path),
                manifest.created_at,
                manifest.updated_at,
            ),
        )
        return manifest

    def list(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM libraries ORDER BY updated_at DESC")

    def resolve(self, identifier: str | Path) -> Path:
        candidate = Path(identifier).expanduser()
        if candidate.exists():
            path = candidate.resolve()
            if path.is_file() and path.name == "manifest.json":
                path = path.parent
            if (path / "manifest.json").exists():
                return path
        row = self.db.fetch_one("SELECT path FROM libraries WHERE id = ?", (str(identifier),))
        if row and Path(row["path"]).exists():
            return Path(row["path"]).resolve()
        raise LibraryNotFoundError(f"Library not found: {identifier}")

    def get(self, identifier: str | Path) -> tuple[Manifest, Path]:
        path = self.resolve(identifier)
        return load_manifest(path), path

    def delete(self, identifier: str, *, remove_files: bool = False) -> None:
        _, path = self.get(identifier)
        self.db.execute("DELETE FROM libraries WHERE id = ?", (identifier,))
        if remove_files:
            if self.libraries_dir not in path.parents:
                raise KlibError("Refusing to delete a library outside the managed K-LIB home")
            shutil.rmtree(path)

    def export(self, identifier: str | Path, destination: Path) -> Path:
        manifest, source = self.get(identifier)
        destination = destination.resolve()
        if destination.suffix.casefold() != ".klib":
            destination = destination.with_suffix(".klib")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if path.is_file():
                    archive.write(path, Path(manifest.id) / path.relative_to(source))
        return destination

    def import_package(self, archive_path: Path, destination: Path | None = None) -> Manifest:
        archive_path = archive_path.resolve()
        if not zipfile.is_zipfile(archive_path):
            raise KlibError(f"Not a valid .klib ZIP package: {archive_path}")
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            roots = {
                Path(member.filename).parts[0]
                for member in members
                if Path(member.filename).parts
            }
            if len(roots) != 1:
                raise KlibError("A .klib archive must contain one top-level library directory")
            root = next(iter(roots))
            target_parent = (destination or self.libraries_dir).resolve()
            target = target_parent / root
            if target.exists():
                raise KlibError(f"Import target already exists: {target}")
            for member in members:
                resolved = (target_parent / member.filename).resolve()
                if target_parent not in resolved.parents and resolved != target_parent:
                    raise KlibError("Archive contains an unsafe path")
            archive.extractall(target_parent)
        try:
            return self.register(target)
        except ManifestValidationError:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def add_glossary(
        self,
        identifier: str | Path,
        source_term: str,
        target_term: str,
        *,
        notes: str = "",
    ) -> dict[str, Any]:
        _, path = self.get(identifier)
        glossary_path = path / "glossary.json"
        entries = self._read_json(glossary_path, [])
        existing = next(
            (item for item in entries if item["source_term"].casefold() == source_term.casefold()),
            None,
        )
        entry = {
            "id": existing["id"] if existing else uuid.uuid4().hex,
            "source_term": source_term,
            "target_term": target_term,
            "notes": notes,
            "confidence": 1.0,
            "created_at": existing.get("created_at", utc_now()) if existing else utc_now(),
        }
        if existing:
            entries[entries.index(existing)] = entry
        else:
            entries.append(entry)
        self._write_json(glossary_path, entries)
        self._touch(identifier)
        return entry

    def add_sources(self, identifier: str | Path, source_path: Path) -> list[dict[str, Any]]:
        manifest, library_path = self.get(identifier)
        added = []
        for source in iter_source_files(source_path.resolve()):
            source_id = uuid.uuid4().hex
            destination = library_path / "sources" / f"{source_id}-{source.name}"
            shutil.copy2(source, destination)
            item = {
                "id": source_id,
                "library_id": manifest.id,
                "title": source.name,
                "type": source.suffix.lower().lstrip("."),
                "path": str(destination.relative_to(library_path)),
                "trust_level": "user_added",
                "metadata": {"original_path": str(source.resolve())},
                "created_at": utc_now(),
            }
            self.db.execute(
                """
                INSERT INTO sources
                    (id, library_id, title, type, path, trust_level, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    item["library_id"],
                    item["title"],
                    item["type"],
                    item["path"],
                    item["trust_level"],
                    self.db.json(item["metadata"]),
                    item["created_at"],
                ),
            )
            added.append(item)
        if added:
            self._touch(identifier)
        return added

    def sources(self, identifier: str | Path) -> list[dict[str, Any]]:
        manifest, _ = self.get(identifier)
        return self.db.fetch_all(
            "SELECT * FROM sources WHERE library_id = ? ORDER BY created_at",
            (manifest.id,),
        )

    def glossary(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        return self._read_json(path / "glossary.json", [])

    def add_rule(
        self,
        identifier: str | Path,
        body: str,
        *,
        title: str = "",
        priority: int = 5,
    ) -> dict[str, Any]:
        _, path = self.get(identifier)
        rule = {
            "id": uuid.uuid4().hex,
            "title": title or body[:60],
            "body": body,
            "priority": priority,
            "created_at": utc_now(),
        }
        rules = self.rules(identifier)
        rules.append(rule)
        lines = ["# Rules", ""]
        for item in sorted(rules, key=lambda value: value.get("priority", 5)):
            lines.extend(
                [
                    f"## {item['title']}",
                    f"<!-- id:{item['id']} priority:{item.get('priority', 5)} -->",
                    item["body"],
                    "",
                ]
            )
        (path / "rules.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self._touch(identifier)
        return rule

    def rules(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        rules_path = path / "rules.md"
        if not rules_path.exists():
            return []
        text = rules_path.read_text(encoding="utf-8-sig")
        pattern = re.compile(
            r"^## (?P<title>.+?)\n<!-- id:(?P<id>\S+) priority:(?P<priority>\d+) -->\n"
            r"(?P<body>.*?)(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        return [
            {
                "id": match.group("id"),
                "title": match.group("title").strip(),
                "body": match.group("body").strip(),
                "priority": int(match.group("priority")),
            }
            for match in pattern.finditer(text)
        ]

    def add_example(
        self,
        identifier: str | Path,
        input_text: str,
        output_text: str,
        *,
        task: str = "",
        mode: str = "",
    ) -> dict[str, Any]:
        _, path = self.get(identifier)
        item = {
            "id": uuid.uuid4().hex,
            "input": input_text,
            "output": output_text,
            "task": task,
            "mode": mode,
            "created_at": utc_now(),
        }
        self._append_jsonl(path / "examples.jsonl", item)
        self._touch(identifier)
        return item

    def examples(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        return self._read_jsonl(path / "examples.jsonl")

    def evals(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        items = []
        for eval_path in sorted((path / "evals").glob("*.json")):
            try:
                items.append(json.loads(eval_path.read_text(encoding="utf-8-sig")))
            except json.JSONDecodeError:
                continue
        return items

    def corrections(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        return self._read_jsonl(path / "corrections.jsonl")

    def _touch(self, identifier: str | Path) -> None:
        manifest, path = self.get(identifier)
        manifest.updated_at = utc_now()
        save_manifest(path, manifest)
        self.register(path)

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                items.append(json.loads(line))
        return items
