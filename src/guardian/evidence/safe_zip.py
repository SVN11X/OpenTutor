"""Open untrusted ZIP-based files (pptx, docx) without extracting or executing anything."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

MAX_ENTRIES = 2000
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_ENTRY_BYTES = 50 * 1024 * 1024
MAX_RATIO = 200  # uncompressed / compressed, per entry
MACRO_MARKERS = ("vbaproject.bin", "vbadata.xml")


class UnsafeArchive(ValueError):
    """The archive is not safe to read. The message is meant for the user."""


def open_safe(path: Path | str) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as err:
        raise UnsafeArchive(f"No es un archivo ZIP válido: {err}") from None
    try:
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise UnsafeArchive(f"Demasiadas entradas ({len(infos)})")
        total = 0
        for info in infos:
            name = info.filename
            posix = PurePosixPath(name.replace("\\", "/"))
            if posix.is_absolute() or ".." in posix.parts or (len(name) > 1 and name[1] == ":"):
                raise UnsafeArchive(f"Ruta peligrosa dentro del archivo: {name!r}")
            if info.file_size > MAX_ENTRY_BYTES:
                raise UnsafeArchive(f"Entrada demasiado grande: {name!r}")
            if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                raise UnsafeArchive(f"Relación de compresión sospechosa en {name!r}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeArchive("El contenido descomprimido supera el límite")
        return zf
    except UnsafeArchive:
        zf.close()
        raise


def has_macros(zf: zipfile.ZipFile) -> bool:
    return any(n.lower().endswith(MACRO_MARKERS) for n in zf.namelist())
