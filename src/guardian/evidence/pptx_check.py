"""Deterministic PPTX rubric. Reads XML only: never runs macros, never follows links.

Status meaning (rubric_version pptx-1):
- failed: a hard rule broke (not a pptx, unsafe, macros, wrong slide count, empty or placeholder slides)
- needs_review: hard rules hold but expected terms are missing, so a human must look
- passed: every deterministic rule holds. This is NOT credit: credit_eligible stays False
  until a reviewed defense exists (see docs/PRACTICE_VALIDATOR_PLAN.md).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .safe_zip import UnsafeArchive, has_macros, open_safe

RUBRIC_VERSION = "pptx-1"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_PLACEHOLDERS = ("click to edit", "haga clic para", "click to add")


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class Result:
    status: str
    checks: tuple[Check, ...] = field(default_factory=tuple)
    rubric_version: str = RUBRIC_VERSION
    assessment_source: str = "deterministic-rubric"
    credit_eligible: bool = False
    # Read-only facts about the deck, used to build the defense questions. Empty when the rubric failed early.
    titles: tuple[str, ...] = ()
    vocabulary: tuple[str, ...] = ()
    full_text: str = ""
    kind: str = "pptx"  # pptx, md or pdf
    unit_count: int = 0  # slides, sections or pages


def _slide_title(root: ET.Element) -> str:
    for shape in root.iter(f"{_P}sp"):
        if any(ph.get("type") in ("title", "ctrTitle") for ph in shape.iter(f"{_P}ph")):
            return " ".join(t.text or "" for t in shape.iter(f"{_A}t")).strip()
    return ""


def _fail(name: str, detail: str) -> Result:
    return Result("failed", (Check(name, False, detail),))


def _parse(xml: bytes) -> ET.Element:
    head = xml[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise UnsafeArchive("XML con DOCTYPE o ENTITY rechazado")
    try:
        return ET.fromstring(xml)
    except ET.ParseError as err:
        raise UnsafeArchive(f"XML dañado: {err}") from None


def check_pptx(
    path: Path | str, *, expected_slides: int | None = None, required_terms: tuple[str, ...] = ()
) -> Result:
    if Path(path).suffix.lower() != ".pptx":
        return _fail("extension", "La extensión debe ser .pptx")
    try:
        zf = open_safe(path)
    except UnsafeArchive as err:
        return _fail("archive", str(err))
    with zf:
        if has_macros(zf):
            return _fail("macros", "Contiene macros VBA: rechazado sin abrirlo")
        numbers = sorted(int(m.group(1)) for n in zf.namelist() if (m := _SLIDE.match(n)))
        if not numbers:
            return _fail("slides", "No se encontraron diapositivas")
        checks: list[Check] = [Check("archive", True), Check("macros", True, "sin macros")]
        texts: list[str] = []
        titles: list[str] = []
        titled, placeholder_hits, empty = 0, [], []
        try:
            for n in numbers:
                root = _parse(zf.read(f"ppt/slides/slide{n}.xml"))
                text = " ".join(t.text or "" for t in root.iter(f"{_A}t")).strip()
                texts.append(text)
                titles.append(_slide_title(root))
                if not text:
                    empty.append(n)
                if any(p in text.lower() for p in _PLACEHOLDERS):
                    placeholder_hits.append(n)
                if any(ph.get("type") in ("title", "ctrTitle") for ph in root.iter(f"{_P}ph")):
                    titled += 1
        except UnsafeArchive as err:
            return _fail("xml", str(err))
    count_ok = expected_slides is None or len(numbers) == expected_slides
    checks.append(
        Check(
            "slide_count",
            count_ok,
            f"{len(numbers)} diapositivas" + ("" if count_ok else f", se esperaban {expected_slides}"),
        )
    )
    checks.append(Check("no_empty_slides", not empty, f"vacías: {empty}" if empty else ""))
    checks.append(
        Check(
            "no_placeholder_text",
            not placeholder_hits,
            f"texto de plantilla en: {placeholder_hits}" if placeholder_hits else "",
        )
    )
    checks.append(Check("titles", titled == len(numbers), f"{titled}/{len(numbers)} con título"))
    non_empty = [t.casefold() for t in texts if t]
    checks.append(Check("no_duplicate_slides", len(set(non_empty)) == len(non_empty)))
    blob = " ".join(texts).casefold()
    missing = [t for t in required_terms if not re.search(rf"\b{re.escape(t.casefold())}\b", blob)]
    terms_ok = not missing
    checks.append(Check("required_terms", terms_ok, f"faltan: {missing}" if missing else ""))
    hard = [c for c in checks if c.name != "required_terms"]
    if not all(c.ok for c in hard):
        status = "failed"
    elif not terms_ok:
        status = "needs_review"
    else:
        status = "passed"
    words = sorted({w.casefold() for w in re.findall(r"\w{4,}", blob)})[:500]
    return Result(
        status,
        tuple(checks),
        titles=tuple(titles),
        vocabulary=tuple(words),
        full_text=blob[:200_000],
        unit_count=len(numbers),
    )
