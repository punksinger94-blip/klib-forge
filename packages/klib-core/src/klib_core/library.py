from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from .database import Database
from .errors import KlibError, LibraryNotFoundError, ManifestValidationError
from .files import extract_document, iter_source_files
from .manifest import load_manifest, save_manifest, validate_manifest_data
from .models import Manifest, utc_now
from .trust import scan_prompt_injection, trust_risk_score

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
TRUST_LEVELS = {"trusted", "user_added", "flagged", "blocked"}
EVAL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_MEMBER_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 1024 * 1024 * 1024


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        raise KlibError("Library name must contain letters or numbers")
    return slug


class LibraryManager:
    def __init__(self, home: Path | None = None):
        configured_home = os.getenv("KLIB_HOME")
        self.home = (
            home
            or (Path(configured_home) if configured_home else Path.home() / ".klib-forge")
        ).resolve()
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
        existing_id = self.db.fetch_one(
            "SELECT path FROM libraries WHERE id = ?",
            (resolved_id,),
        )
        if existing_id:
            raise KlibError(
                f"Library id is already registered at {existing_id['path']}: {resolved_id}"
            )
        existing_path = self.db.fetch_one(
            "SELECT id FROM libraries WHERE path = ?",
            (str(library_path),),
        )
        if existing_path:
            raise KlibError(
                f"Target directory is already registered as {existing_path['id']}: "
                f"{library_path}"
            )
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
        self._sync_sources(manifest, library_path)
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
        manifest, path = self.get(identifier)
        if remove_files:
            if self.libraries_dir not in path.parents:
                raise KlibError("Refusing to delete a library outside the managed K-LIB home")
        self.db.execute("DELETE FROM libraries WHERE id = ?", (manifest.id,))
        if remove_files:
            shutil.rmtree(path)

    def export(self, identifier: str | Path, destination: Path) -> Path:
        manifest, source = self.get(identifier)
        destination = destination.resolve()
        if destination.suffix.casefold() != ".klib":
            destination = destination.with_suffix(".klib")
        if source == destination or source in destination.parents:
            raise KlibError("Export destination must be outside the package directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in source.rglob("*"):
                if path.is_file():
                    if path.is_symlink():
                        raise KlibError(f"Refusing to export symbolic link: {path}")
                    archive.write(path, Path(manifest.id) / path.relative_to(source))
        return destination

    def import_package(self, archive_path: Path, destination: Path | None = None) -> Manifest:
        archive_path = archive_path.resolve()
        if not zipfile.is_zipfile(archive_path):
            raise KlibError(f"Not a valid .klib ZIP package: {archive_path}")
        with zipfile.ZipFile(archive_path) as archive:
            members, root, manifest = self._validate_archive(archive)
            existing_id = self.db.fetch_one(
                "SELECT path FROM libraries WHERE id = ?",
                (manifest.id,),
            )
            if existing_id:
                raise KlibError(
                    f"Library id is already registered at {existing_id['path']}: "
                    f"{manifest.id}"
                )
            target_parent = (destination or self.libraries_dir).resolve()
            target_parent.mkdir(parents=True, exist_ok=True)
            target = target_parent / root
            if target.exists():
                raise KlibError(f"Import target already exists: {target}")
            with tempfile.TemporaryDirectory(
                prefix=".klib-import-",
                dir=target_parent,
            ) as temporary:
                staging_parent = Path(temporary)
                for member in members:
                    archive.extract(member, staging_parent)
                staging_target = staging_parent / root
                if not staging_target.is_dir():
                    raise KlibError("Archive does not contain a package directory")
                shutil.move(str(staging_target), target)
        try:
            registered = self.register(target)
            if registered.id != manifest.id:
                raise KlibError("Imported manifest changed during extraction")
            return registered
        except (KlibError, ManifestValidationError):
            self.db.execute("DELETE FROM libraries WHERE id = ?", (manifest.id,))
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
            document = extract_document(source)
            findings = scan_prompt_injection(document.text)
            risk_score = trust_risk_score(findings)
            trust_level = "flagged" if risk_score >= 40 else "user_added"
            source_id = uuid.uuid4().hex
            destination = library_path / "sources" / f"{source_id}-{source.name}"
            shutil.copy2(source, destination)
            item = {
                "id": source_id,
                "library_id": manifest.id,
                "title": source.name,
                "type": source.suffix.lower().lstrip("."),
                "path": str(destination.relative_to(library_path)),
                "trust_level": trust_level,
                "metadata": {
                    "original_path": str(source.resolve()),
                    **document.metadata,
                    "risk_score": risk_score,
                    "trust_findings": [
                        finding.model_dump(mode="json") for finding in findings
                    ],
                },
                "created_at": utc_now(),
            }
            try:
                self._insert_source(item)
            except Exception:
                destination.unlink(missing_ok=True)
                raise
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

    def delete_source(self, identifier: str | Path, source_id: str) -> None:
        manifest, library_path = self.get(identifier)
        source = self.db.fetch_one(
            "SELECT * FROM sources WHERE id = ? AND library_id = ?",
            (source_id, manifest.id),
        )
        if not source:
            raise KlibError(f"Source not found: {source_id}")
        (library_path / source["path"]).unlink(missing_ok=True)
        self.db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        self._touch(identifier)

    def update_source(
        self,
        identifier: str | Path,
        source_id: str,
        *,
        title: str | None = None,
        trust_level: str | None = None,
    ) -> dict[str, Any]:
        manifest, _ = self.get(identifier)
        source = self.db.fetch_one(
            "SELECT * FROM sources WHERE id = ? AND library_id = ?",
            (source_id, manifest.id),
        )
        if not source:
            raise KlibError(f"Source not found: {source_id}")
        resolved_title = title if title is not None else source["title"]
        resolved_trust = trust_level if trust_level is not None else source["trust_level"]
        if resolved_trust not in TRUST_LEVELS:
            raise KlibError(
                "Source trust level must be trusted, user_added, flagged, or blocked"
            )
        self.db.execute(
            "UPDATE sources SET title = ?, trust_level = ? WHERE id = ?",
            (resolved_title, resolved_trust, source_id),
        )
        self._touch(identifier)
        return self.db.fetch_one("SELECT * FROM sources WHERE id = ?", (source_id,)) or {}

    def update_manifest(self, identifier: str | Path, changes: dict[str, Any]) -> Manifest:
        manifest, path = self.get(identifier)
        protected = {"id", "created_at", "klib_format_version"}
        data = manifest.model_dump(mode="json")
        for key, value in changes.items():
            if key not in protected and value is not None:
                data[key] = value
        updated = Manifest.model_validate(data)
        updated.updated_at = utc_now()
        save_manifest(path, updated)
        self.register(path)
        return updated

    def delete_glossary(self, identifier: str | Path, entry_id: str) -> None:
        _, path = self.get(identifier)
        entries = self.glossary(identifier)
        kept = [item for item in entries if item["id"] != entry_id]
        if len(entries) == len(kept):
            raise KlibError(f"Glossary entry not found: {entry_id}")
        self._write_json(path / "glossary.json", kept)
        self._touch(identifier)

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

    def update_rule(
        self,
        identifier: str | Path,
        rule_id: str,
        *,
        title: str,
        body: str,
        priority: int,
    ) -> dict[str, Any]:
        rules = self.rules(identifier)
        rule = next((item for item in rules if item["id"] == rule_id), None)
        if not rule:
            raise KlibError(f"Rule not found: {rule_id}")
        rule.update(title=title or body[:60], body=body, priority=priority)
        self._write_rules(identifier, rules)
        return rule

    def delete_rule(self, identifier: str | Path, rule_id: str) -> None:
        rules = self.rules(identifier)
        kept = [item for item in rules if item["id"] != rule_id]
        if len(rules) == len(kept):
            raise KlibError(f"Rule not found: {rule_id}")
        self._write_rules(identifier, kept)

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

    def update_example(
        self,
        identifier: str | Path,
        example_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        _, path = self.get(identifier)
        items = self.examples(identifier)
        item = next((value for value in items if value["id"] == example_id), None)
        if not item:
            raise KlibError(f"Example not found: {example_id}")
        item.update({key: value for key, value in changes.items() if value is not None})
        self._write_jsonl(path / "examples.jsonl", items)
        self._touch(identifier)
        return item

    def delete_example(self, identifier: str | Path, example_id: str) -> None:
        _, path = self.get(identifier)
        items = self.examples(identifier)
        kept = [item for item in items if item["id"] != example_id]
        if len(items) == len(kept):
            raise KlibError(f"Example not found: {example_id}")
        self._write_jsonl(path / "examples.jsonl", kept)
        self._touch(identifier)

    def examples(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        return self._read_jsonl(path / "examples.jsonl")

    def evals(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        items = []
        for eval_path in sorted((path / "evals").glob("*.json")):
            try:
                payload = json.loads(eval_path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                raise KlibError(f"Eval file is invalid JSON: {eval_path.name}") from exc
            items.append(self._validate_eval(payload))
        return items

    def save_eval(self, identifier: str | Path, eval_data: dict[str, Any]) -> dict[str, Any]:
        _, path = self.get(identifier)
        eval_id = str(eval_data.get("id") or f"eval-{uuid.uuid4().hex[:12]}")
        self._validate_eval_id(eval_id)
        payload = self._validate_eval({**eval_data, "id": eval_id})
        (path / "evals" / f"{eval_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._touch(identifier)
        return payload

    def delete_eval(self, identifier: str | Path, eval_id: str) -> None:
        _, path = self.get(identifier)
        self._validate_eval_id(eval_id)
        target = path / "evals" / f"{eval_id}.json"
        if not target.exists():
            raise KlibError(f"Eval not found: {eval_id}")
        target.unlink()
        self._touch(identifier)

    def corrections(self, identifier: str | Path) -> list[dict[str, Any]]:
        _, path = self.get(identifier)
        return self._read_jsonl(path / "corrections.jsonl")

    def review_correction(
        self,
        identifier: str | Path,
        correction_id: str,
        status: str,
    ) -> dict[str, Any]:
        if status not in {"pending", "approved", "rejected"}:
            raise KlibError("Correction status must be pending, approved, or rejected")
        _, path = self.get(identifier)
        corrections = self.corrections(identifier)
        correction = next(
            (item for item in corrections if item["id"] == correction_id),
            None,
        )
        if not correction:
            raise KlibError(f"Correction not found: {correction_id}")
        correction["status"] = status
        correction["reviewed_at"] = utc_now()
        self._write_jsonl(path / "corrections.jsonl", corrections)
        self._touch(identifier)
        return correction

    def model_runs(self, identifier: str | Path, limit: int = 100) -> list[dict[str, Any]]:
        manifest, _ = self.get(identifier)
        rows = self.db.fetch_all(
            """
            SELECT id, provider, model, input, output, prompt, retrieved_context_json,
                   latency_ms, created_at
            FROM model_runs
            WHERE library_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (manifest.id, limit),
        )
        for row in rows:
            row["retrieved_context"] = json.loads(row.pop("retrieved_context_json") or "[]")
        return rows

    def eval_runs(self, identifier: str | Path, limit: int = 100) -> list[dict[str, Any]]:
        manifest, _ = self.get(identifier)
        rows = self.db.fetch_all(
            """
            SELECT id, model_provider, model_name, score, result_json, created_at
            FROM eval_runs
            WHERE library_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (manifest.id, limit),
        )
        for row in rows:
            row["results"] = json.loads(row.pop("result_json") or "[]")
        return rows

    def trust_reports(self, identifier: str | Path) -> list[dict[str, Any]]:
        reports = []
        for source in self.sources(identifier):
            metadata = json.loads(source.get("metadata_json") or "{}")
            reports.append(
                {
                    "source_id": source["id"],
                    "title": source["title"],
                    "trust_level": source["trust_level"],
                    "risk_score": metadata.get("risk_score", 0),
                    "findings": metadata.get("trust_findings", []),
                }
            )
        return reports

    def _touch(self, identifier: str | Path) -> None:
        manifest, path = self.get(identifier)
        manifest.updated_at = utc_now()
        save_manifest(path, manifest)
        self.register(path)

    def _write_rules(self, identifier: str | Path, rules: list[dict[str, Any]]) -> None:
        _, path = self.get(identifier)
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

    def _sync_sources(self, manifest: Manifest, library_path: Path) -> None:
        sources_path = library_path / "sources"
        sources_path.mkdir(parents=True, exist_ok=True)
        existing = {
            item["path"]: item
            for item in self.db.fetch_all(
                "SELECT * FROM sources WHERE library_id = ?",
                (manifest.id,),
            )
        }
        discovered_paths: set[str] = set()
        for source in iter_source_files(sources_path):
            relative = str(source.relative_to(library_path))
            discovered_paths.add(relative)
            if relative in existing:
                continue
            source_id, title = self._source_identity(manifest.id, relative)
            collision = self.db.fetch_one(
                "SELECT library_id FROM sources WHERE id = ?",
                (source_id,),
            )
            if collision and collision["library_id"] != manifest.id:
                source_id = uuid.uuid4().hex
            document = extract_document(source)
            findings = scan_prompt_injection(document.text)
            risk_score = trust_risk_score(findings)
            item = {
                "id": source_id,
                "library_id": manifest.id,
                "title": title,
                "type": source.suffix.lower().lstrip("."),
                "path": relative,
                "trust_level": "flagged" if risk_score >= 40 else "user_added",
                "metadata": {
                    **document.metadata,
                    "risk_score": risk_score,
                    "trust_findings": [
                        finding.model_dump(mode="json") for finding in findings
                    ],
                },
                "created_at": utc_now(),
            }
            self._insert_source(item)
        for relative, item in existing.items():
            if relative not in discovered_paths:
                self.db.execute("DELETE FROM sources WHERE id = ?", (item["id"],))

    def _insert_source(self, item: dict[str, Any]) -> None:
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

    @staticmethod
    def _source_identity(library_id: str, relative_path: str) -> tuple[str, str]:
        filename = Path(relative_path).name
        match = re.match(r"^([0-9a-f]{32})-(.+)$", filename)
        if match:
            return match.group(1), match.group(2)
        source_id = uuid.uuid5(uuid.NAMESPACE_URL, f"klib:{library_id}:{relative_path}").hex
        return source_id, filename

    @staticmethod
    def _validate_eval_id(eval_id: str) -> None:
        if not EVAL_ID_PATTERN.fullmatch(eval_id):
            raise KlibError(
                "Eval id must start with a letter or number and contain only "
                "letters, numbers, dots, underscores, or hyphens"
            )

    @staticmethod
    def _validate_eval(payload: dict[str, Any]) -> dict[str, Any]:
        schema_path = Path(__file__).resolve().parent / "schemas" / "eval.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema).iter_errors(payload),
            key=lambda item: list(item.path),
        )
        if errors:
            detail = "; ".join(error.message for error in errors)
            raise KlibError(f"Eval is invalid: {detail}")
        LibraryManager._validate_eval_id(str(payload["id"]))
        return payload

    @staticmethod
    def _validate_archive(
        archive: zipfile.ZipFile,
    ) -> tuple[list[zipfile.ZipInfo], str, Manifest]:
        members = archive.infolist()
        if not members:
            raise KlibError("A .klib archive is empty")
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise KlibError("A .klib archive contains too many entries")
        total_size = 0
        roots: set[str] = set()
        names: set[str] = set()
        normalized_members: list[zipfile.ZipInfo] = []
        for member in members:
            normalized_name = member.filename.replace("\\", "/")
            pure_path = PurePosixPath(normalized_name)
            parts = pure_path.parts
            if (
                not parts
                or pure_path.is_absolute()
                or re.match(r"^[A-Za-z]:", normalized_name)
                or any(part in {"", ".", ".."} for part in parts)
            ):
                raise KlibError("Archive contains an unsafe path")
            normalized_key = normalized_name.rstrip("/").casefold()
            if normalized_key in names:
                raise KlibError("Archive contains duplicate paths")
            names.add(normalized_key)
            roots.add(parts[0])
            if member.flag_bits & 0x1:
                raise KlibError("Encrypted .klib archives are not supported")
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise KlibError("Archive contains a symbolic link")
            if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                raise KlibError(f"Archive member is too large: {member.filename}")
            total_size += member.file_size
            if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                raise KlibError("Archive uncompressed size is too large")
            member.filename = normalized_name
            normalized_members.append(member)
        if len(roots) != 1:
            raise KlibError("A .klib archive must contain one top-level library directory")
        root = next(iter(roots))
        manifest_name = f"{root}/manifest.json"
        try:
            manifest_data = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
        except KeyError as exc:
            raise KlibError("A .klib archive must contain manifest.json") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KlibError("Archive manifest is invalid") from exc
        manifest = validate_manifest_data(manifest_data)
        if root != manifest.id:
            raise KlibError("Archive top-level directory must match manifest id")
        return normalized_members, root, manifest

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
    def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
        path.write_text(
            "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
            encoding="utf-8",
        )

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                items.append(json.loads(line))
        return items
