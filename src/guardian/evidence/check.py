"""One entry point for every supported file kind."""

from __future__ import annotations

from pathlib import Path

from .md_check import check_markdown
from .pdf_check import check_pdf
from .pptx_check import Result, check_pptx

KINDS = ("pptx", "md", "pdf")

# Spanish words for the screens: (plural, singular, "your <thing>"), the file filter, the dialog pattern.
KIND_INFO = {
    "pptx": {
        "plural": "diapositivas",
        "singular": "diapositiva",
        "owner_thing": "tu presentación",
        "name": "PowerPoint (.pptx)",
        "pattern": "*.pptx",
    },
    "md": {
        "plural": "secciones",
        "singular": "sección",
        "owner_thing": "tu documento",
        "name": "Markdown (.md)",
        "pattern": "*.md *.markdown",
    },
    "pdf": {
        "plural": "páginas",
        "singular": "página",
        "owner_thing": "tu PDF",
        "name": "PDF (.pdf)",
        "pattern": "*.pdf",
    },
}


def check_file(kind: str, path: Path | str, expected: int, required_terms: tuple[str, ...]) -> Result:
    if kind == "pptx":
        return check_pptx(path, expected_slides=expected, required_terms=required_terms)
    if kind == "md":
        return check_markdown(path, expected_sections=expected, required_terms=required_terms)
    if kind == "pdf":
        return check_pdf(path, expected_pages=expected, required_terms=required_terms)
    raise ValueError(f"Tipo de archivo desconocido: {kind}")
