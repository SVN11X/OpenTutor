"""Draws Guardian's icon (a blue shield with a white check) and writes src/guardian/assets/guardian.ico.

Usage (repository root): python scripts/make_icon.py

Own work, drawn with plain geometry and the standard library, so no image tool or third-party asset is
needed. The output is deterministic: running it again gives the same bytes.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "guardian" / "assets" / "guardian.ico"
SIZES = (16, 20, 24, 32, 40, 48, 64, 256)
SHIELD = (26, 79, 138)  # the panel's accent blue, #1a4f8a
CHECK = (255, 255, 255)
SAMPLES = 4  # 4 x 4 samples per pixel smooth the edges


def _in_shield(x: float, y: float) -> bool:
    """Shield in a unit square: a rounded top half and an elliptic point at the bottom."""
    top, middle, bottom, half = 0.08, 0.52, 0.95, 0.38
    if y < top or y > bottom:
        return False
    if y <= middle:
        radius = 0.12
        left, right = 0.5 - half, 0.5 + half
        if y < top + radius:  # round the two top corners
            for cx in (left + radius, right - radius):
                if abs(x - cx) <= radius and (x < left + radius or x > right - radius):
                    return (x - cx) ** 2 + (y - (top + radius)) ** 2 <= radius**2
        return left <= x <= right
    t = (y - middle) / (bottom - middle)
    return abs(x - 0.5) <= half * math.sqrt(max(0.0, 1 - t * t))


def _near_check(x: float, y: float) -> bool:
    """A check mark drawn as two thick segments."""
    points = ((0.31, 0.50), (0.45, 0.65), (0.70, 0.36))
    width = 0.085
    for (ax, ay), (bx, by) in zip(points, points[1:], strict=False):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        if (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= (width / 2) ** 2:
            return True
    return False


def render(size: int) -> bytes:
    """RGBA pixels, top row first."""
    pixels = bytearray()
    step = 1 / (size * SAMPLES)
    for row in range(size):
        for col in range(size):
            shield = check = 0
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    x = (col * SAMPLES + sx + 0.5) * step
                    y = (row * SAMPLES + sy + 0.5) * step
                    if _in_shield(x, y):
                        shield += 1
                        check += _near_check(x, y)
            total = SAMPLES * SAMPLES
            alpha = shield / total
            mix = check / shield if shield else 0.0
            color = [round(s + (c - s) * mix) for s, c in zip(SHIELD, CHECK, strict=True)]
            pixels += bytes([*color, round(alpha * 255)])
    return bytes(pixels)


def png_rgba(size: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    stride = size * 4
    raw = b"".join(b"\x00" + rgba[y * stride : (y + 1) * stride] for y in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def dib(size: int, rgba: bytes) -> bytes:
    """A classic 32-bit icon image (BGRA bottom-up plus an empty AND mask), read by every Windows API."""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = []
    for y in reversed(range(size)):
        row = rgba[y * size * 4 : (y + 1) * size * 4]
        bgra = bytearray(len(row))
        bgra[0::4], bgra[1::4], bgra[2::4], bgra[3::4] = row[2::4], row[1::4], row[0::4], row[3::4]
        rows.append(bytes(bgra))
    mask_stride = ((size + 31) // 32) * 4
    return header + b"".join(rows) + bytes(mask_stride * size)


def ico(images: list[tuple[int, bytes]]) -> bytes:
    """An ICO file: 256 px as PNG, the small sizes as classic bitmaps."""
    directory = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = [], []
    for size, data in images:
        edge = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", edge, edge, 0, 0, 1, 32, len(data), offset))
        blobs.append(data)
        offset += len(data)
    return directory + b"".join(entries) + b"".join(blobs)


def build() -> bytes:
    images = []
    for size in SIZES:
        rgba = render(size)
        images.append((size, png_rgba(size, rgba) if size >= 256 else dib(size, rgba)))
    return ico(images)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build())
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes, sizes {', '.join(map(str, SIZES))})")


if __name__ == "__main__":
    main()
