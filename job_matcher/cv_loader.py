from __future__ import annotations

from pathlib import Path


def load_cv_text(path: Path) -> str:
    """Extract plain text from a CV file. Supports .pdf, .docx, .txt, .md."""
    if not path.exists():
        raise FileNotFoundError(
            f"CV not found at {path}. Update `cv.path` in config.yaml, "
            "or add the file to the repo."
        )

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    if suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported CV format: {suffix}")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _load_docx(path: Path) -> str:
    import docx

    doc = docx.Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)
