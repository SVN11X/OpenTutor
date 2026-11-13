"""Deterministic PDF rubric (pdf-1), stdlib only. Nothing is rendered, opened or executed.

It checks structure, size, active content (JavaScript, launch actions, embedded files) also inside
compressed streams with hard limits, and the page count. Text extraction without a PDF library is
unreliable (subset fonts and custom encodings), so required terms that cannot be found give
needs_review, never a rejection.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path

from .pptx_check import Check, Result

RUBRIC_VERSION = "pdf-1"
MAX_BYTES = 50 * 1024 * 1024
MAX_STREAM_OUT = 10 * 1024 * 1024
MAX_TOTAL_OUT = 100 * 1024 * 1024
MAX_STREAMS = 20_000
_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFiles?|RichMedia|XFA)(?![A-Za-z0-9])")
_PAGE = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_TJ = re.compile(rb"\(((?:\\.|[^\\)])*)\)\s*Tj")
_TJ_ARRAY = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
_STR = re.compile(rb"\(((?:\\.|[^\\)])*)\)")


class _Unsafe(ValueError):
    pass


def _fail(name: str, detail: str) -> Result:
    return Result("failed", (Check(name, False, detail),), kind="pdf")


def _inflate(raw: bytes) -> list[bytes]:
    """Decompressed content of every zlib stream, with hard limits against decompression bombs."""
    outputs: list[bytes] = []
    total = 0
    for count, match in enumerate(_STREAM.finditer(raw)):
        if count >= MAX_STREAMS:
            raise _Unsafe("Demasiados flujos de datos")
        data = match.group(1)
        if not data[:1] == b"x":  # zlib streams start with 0x78
            continue
        inflater = zlib.decompressobj()
        try:
            out = inflater.decompress(data, MAX_STREAM_OUT)
        except zlib.error:
            continue
        if inflater.unconsumed_tail:
            raise _Unsafe("Un flujo comprimido es sospechosamente grande")
        total += len(out)
        if total > MAX_TOTAL_OUT:
            raise _Unsafe("El contenido descomprimido supera el límite")
        outputs.append(out)
    return outputs


def _unescape(chunk: bytes) -> str:
    text = chunk.decode("latin-1")
    return re.sub(r"\\([()\\])", r"\1", text)


def _extract_text(streams: list[bytes]) -> str:
    parts: list[str] = []
    for stream in streams:
        if b"BT" not in stream:
            continue
        parts += [_unescape(m.group(1)) for m in _TJ.finditer(stream)]
        for array in _TJ_ARRAY.finditer(stream):
            parts.append("".join(_unescape(s.group(1)) for s in _STR.finditer(array.group(1))))
    return " ".join(p for p in parts if p.strip())


def check_pdf(
    path: Path | str, *, expected_pages: int | None = None, required_terms: tuple[str, ...] = ()
) -> Result:
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return _fail("extension", "La extensión debe ser .pdf")
    try:
        if path.stat().st_size > MAX_BYTES:
            return _fail("readable", "El archivo supera 50 MB")
        raw = path.read_bytes()
    except OSError as err:
        return _fail("readable", f"No se pudo leer: {err.strerror or err}")
    if not raw.startswith(b"%PDF-"):
        return _fail("readable", "No empieza como un PDF")
    if b"%%EOF" not in raw[-2048:]:
        return _fail("readable", "El PDF está incompleto: falta el final del archivo")
    try:
        streams = _inflate(raw)
    except _Unsafe as err:
        return _fail("safe_streams", str(err))

    checks: list[Check] = [Check("readable", True), Check("safe_streams", True)]
    scanned = [raw, *streams]
    active = sorted({m.group(1).decode() for blob in scanned for m in _ACTIVE.finditer(blob)})
    checks.append(
        Check("active_content", not active, f"contiene: {active}. Rechazado sin abrirlo" if active else "")
    )
    pages = sum(len(_PAGE.findall(blob)) for blob in scanned)
    pages_ok = pages >= 1 and (expected_pages is None or pages == expected_pages)
    detail = f"{pages} páginas" + (f", se esperaban {expected_pages}" if not pages_ok and pages else "")
    checks.append(Check("page_count", pages_ok, detail))

    text = _extract_text(streams)
    blob = text.casefold()
    missing = [t for t in required_terms if not re.search(rf"\b{re.escape(t.casefold())}\b", blob)]
    checks.append(
        Check(
            "required_terms",
            not missing,
            f"no se pudieron confirmar en el texto: {missing}" if missing else "",
        )
    )
    hard = [c for c in checks if c.name != "required_terms"]
    if not all(c.ok for c in hard):
        status = "failed"
    elif missing:
        status = "needs_review"
    else:
        status = "passed"
    vocab = tuple(sorted({w.casefold() for w in re.findall(r"\w{4,}", text)})[:500])
    return Result(
        status,
        tuple(checks),
        rubric_version=RUBRIC_VERSION,
        vocabulary=vocab,
        full_text=blob[:200_000],
        kind="pdf",
        unit_count=pages,
    )
