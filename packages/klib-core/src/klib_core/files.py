from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from .errors import KlibError

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".json", ".jsonl"}


@dataclass
class ExtractedDocument:
    text: str
    metadata: dict = field(default_factory=dict)


def iter_source_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise KlibError(f"Unsupported source type: {path.suffix}")
        yield path
        return
    if not path.is_dir():
        raise KlibError(f"Source path does not exist: {path}")
    for item in sorted(path.rglob("*")):
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield item


def extract_text(path: Path) -> str:
    return extract_document(path).text


def extract_document(path: Path) -> ExtractedDocument:
    extension = path.suffix.lower()
    if extension == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        cleaned_pages = _remove_repeated_pdf_margins(pages)
        metadata = {
            "page_count": len(reader.pages),
            "title": getattr(reader.metadata, "title", None) if reader.metadata else None,
            "author": getattr(reader.metadata, "author", None) if reader.metadata else None,
            "subject": getattr(reader.metadata, "subject", None) if reader.metadata else None,
        }
        return ExtractedDocument(
            text="\n\n".join(
                f"[Page {index}]\n{page}" for index, page in enumerate(cleaned_pages, start=1)
            ),
            metadata={key: value for key, value in metadata.items() if value},
        )
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if extension == ".json":
        try:
            value = json.loads(text)
            return ExtractedDocument(
                text=json.dumps(value, ensure_ascii=False, indent=2),
                metadata={"json_type": type(value).__name__},
            )
        except json.JSONDecodeError:
            return ExtractedDocument(text=text, metadata={"json_valid": False})
    if extension == ".jsonl":
        lines = [line for line in text.splitlines() if line.strip()]
        return ExtractedDocument(text=text, metadata={"record_count": len(lines)})
    return ExtractedDocument(
        text=text,
        metadata={"line_count": len(text.splitlines())},
    )


def _remove_repeated_pdf_margins(pages: list[str]) -> list[str]:
    if len(pages) < 3:
        return pages
    line_counts: dict[str, int] = {}
    normalized_pages: list[list[str]] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        normalized_pages.append(lines)
        candidates = lines[:3] + lines[-3:]
        for line in set(candidates):
            if len(line) <= 160:
                line_counts[line] = line_counts.get(line, 0) + 1
    threshold = max(3, round(len(pages) * 0.6))
    repeated = {line for line, count in line_counts.items() if count >= threshold}
    return ["\n".join(line for line in lines if line not in repeated) for lines in normalized_pages]


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> list[str]:
    if not text:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(len(paragraph), start + size)
                chunks.append(paragraph[start:end].strip())
                if end == len(paragraph):
                    break
                start = max(start + 1, end - overlap)
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > size:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail}\n\n{paragraph}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
