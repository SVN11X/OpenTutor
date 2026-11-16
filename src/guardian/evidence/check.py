"""One entry point for every supported file kind."""

from __future__ import annotations

from pathlib import Path

from ..i18n import t
from .md_check import check_markdown
from .pdf_check import check_pdf
from .pptx_check import Result, check_pptx

KINDS = ("pptx", "md", "pdf")

# Screen words come from es.json: (plural, singular, "your <thing>"), the file filter, the dialog pattern.
KIND_INFO = {
    "pptx": {
        "plural": t("check.pptx_plural"),
        "singular": t("check.pptx_singular"),
        "owner_thing": t("check.pptx_owner_thing"),
        "name": t("check.pptx_name"),
        "pattern": "*.pptx",
    },
    "md": {
        "plural": t("check.md_plural"),
        "singular": t("check.md_singular"),
        "owner_thing": t("check.md_owner_thing"),
        "name": t("check.md_name"),
        "pattern": "*.md *.markdown",
    },
    "pdf": {
        "plural": t("check.pdf_plural"),
        "singular": t("check.pdf_singular"),
        "owner_thing": t("check.pdf_owner_thing"),
        "name": t("check.pdf_name"),
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
    raise ValueError(t("check.unknown_kind", kind=kind))
