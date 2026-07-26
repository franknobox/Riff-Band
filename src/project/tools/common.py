from __future__ import annotations

import re
from pathlib import Path
from typing import Set, Tuple


def safe_resolve(sources_dir: Path, rel_path: str) -> Tuple[Path | None, str | None]:
    target = (sources_dir / rel_path).resolve()
    if not str(target).startswith(str(sources_dir.resolve())):
        return None, "Path traversal is not allowed."
    if not target.exists():
        return None, f"Source file not found: {rel_path}"
    if not target.is_file():
        return None, f"Path is not a file: {rel_path}"
    return target, None


def tokenize(text: str) -> Set[str]:
    return set(re.findall(r"[a-zA-Z0-9_\u4e00-\u9fff]{2,}", text.lower()))


def extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks = []
    for page in getattr(reader, "pages", []) or []:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(item for item in chunks if item).strip()
    if not text:
        raise RuntimeError("No extractable text found in PDF.")
    return text


def read_source_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    return path.read_text(encoding="utf-8")
