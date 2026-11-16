"""Screenshot gallery of Guardian as a user sees it, so the interface can be reviewed without running it.

Usage (Windows, repository root): python scripts/gallery.py [--out build/gallery] [--bank FOLDER]

It starts the real panel with a throwaway data folder, puts it in each state a user meets, and saves one
PNG per state plus an index.html. Only Guardian's own windows are captured, with PrintWindow, never the
rest of the screen. Windows are fully transparent and never take focus, so it can run while you work.
"""

from __future__ import annotations

import argparse
import ctypes
import html
import os
import struct
import sys
import tempfile
import time
import tkinter as tk
import zlib
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PW_RENDERFULLCONTENT = 2


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _win32():
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    handle = ctypes.c_void_p
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetDC.restype = handle
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, handle]
    user32.PrintWindow.argtypes = [wintypes.HWND, handle, wintypes.UINT]
    gdi32.CreateCompatibleDC.restype = handle
    gdi32.CreateCompatibleDC.argtypes = [handle]
    gdi32.CreateCompatibleBitmap.restype = handle
    gdi32.CreateCompatibleBitmap.argtypes = [handle, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = handle
    gdi32.SelectObject.argtypes = [handle, handle]
    gdi32.GetDIBits.argtypes = [
        handle,
        handle,
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(BITMAPINFOHEADER),
        wintypes.UINT,
    ]
    gdi32.DeleteObject.argtypes = [handle]
    gdi32.DeleteDC.argtypes = [handle]
    return user32, gdi32


def capture(window: tk.Misc) -> tuple[int, int, bytes]:
    """(width, height, RGB bytes) of one Tk window with its title bar, without the invisible borders."""
    user32, gdi32 = _win32()
    window.update_idletasks()
    window.update()
    hwnd = user32.GetAncestor(window.winfo_id(), 2)  # GA_ROOT: the frame that holds the title bar
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    screen = user32.GetDC(None)
    dc = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    old = gdi32.SelectObject(dc, bitmap)
    try:
        if not user32.PrintWindow(hwnd, dc, PW_RENDERFULLCONTENT):
            raise OSError("PrintWindow failed")
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        pixels = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(dc, bitmap, 0, height, pixels, ctypes.byref(header), 0):
            raise OSError("GetDIBits failed")
    finally:
        gdi32.SelectObject(dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(dc)
        user32.ReleaseDC(None, screen)
    # Windows 10 and 11 keep a transparent resize border left, right and bottom. Keep one visible pixel.
    border = max(0, window.winfo_rootx() - rect.left - 1)
    return crop_bgra(pixels.raw, width, height, border)


def crop_bgra(bgra: bytes, width: int, height: int, border: int) -> tuple[int, int, bytes]:
    """Drop `border` pixels left, right and bottom, and turn BGRA into RGB."""
    new_w, new_h = width - 2 * border, height - border
    rows = []
    for y in range(new_h):
        start = (y * width + border) * 4
        row = bgra[start : start + new_w * 4]
        rgb = bytearray(new_w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        rows.append(bytes(rgb))
    return new_w, new_h, b"".join(rows)


def png_bytes(width: int, height: int, rgb: bytes) -> bytes:
    """A minimal PNG (8-bit RGB) with zlib from the standard library, so no imaging package is needed."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    stride = width * 3
    raw = b"".join(b"\x00" + rgb[y * stride : (y + 1) * stride] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def write_index(out: Path, shots: list[tuple[str, str, str]]) -> None:
    cards = "\n".join(
        f'<figure><img src="{name}" alt="{html.escape(title)}" loading="lazy">'
        f"<figcaption><b>{html.escape(title)}</b><br>{html.escape(note)}</figcaption></figure>"
        for name, title, note in shots
    )
    page = f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guardian gallery</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 16px; background: #f4f5f7; color: #1d2433; }}
main {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }}
figure {{ margin: 0; background: #fff; border-radius: 8px; padding: 10px; box-shadow: 0 1px 3px #0002; }}
img {{ width: 100%; height: auto; display: block; }}
figcaption {{ margin-top: 8px; font-size: 14px; line-height: 1.4; }}
</style>
<h1>OpenTutor Guardian, as a user sees it</h1>
<p>Generated by scripts/gallery.py on {time.strftime("%Y-%m-%d %H:%M")}. Panel text is in Spanish.</p>
<main>
{cards}
</main>
</html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")


def run(out: Path, bank: Path | None) -> list[tuple[str, str, str]]:
    """Drive the real panel through each state and save the screenshots. Returns (file, title, note)."""
    data = Path(tempfile.mkdtemp(prefix="guardian-gallery-"))
    os.environ["LOCALAPPDATA"] = str(data)  # never touch the owner's real results or settings
    os.environ["GUARDIAN_GCP_BANK"] = str(data / "no-bank")  # first run: no bank found yet

    from guardian import desktop, integrations
    from guardian.questions import get_questions
    from guardian.quiz_window import QuizWindow
    from guardian.settings_ui import SET_TOPICS, quiz_mode

    tk.Misc.focus_force = lambda self: None  # the gallery never steals focus from the person working
    toplevel_init = tk.Toplevel.__init__

    def invisible_toplevel(self, *args, **kwargs):
        # Off-screen windows are never painted, so they stay on screen but fully transparent.
        toplevel_init(self, *args, **kwargs)
        self.attributes("-alpha", 0.0)

    tk.Toplevel.__init__ = invisible_toplevel

    class GalleryUI(desktop.GuardianUI):
        """The real panel without the live clock or service probes, so every shot shows a chosen state."""

        def _tick(self) -> None:
            self._refresh_views()

        def _refresh_health(self, repeat: bool = True) -> None:
            states = [
                integrations.Health("Preguntas locales", "ok" if self.bank_found else "degraded"),
                integrations.Health("Ollama", "disconnected"),
                integrations.Health("FocoLocal", "unavailable"),
            ]
            self.health.set("  ·  ".join(h.text() for h in states))

    root = tk.Tk()
    root.attributes("-alpha", 0.0)
    ui = GalleryUI(root)
    ui.autostart_var.set(False)  # show the first run, whatever this machine has in its registry
    shots: list[tuple[str, str, str]] = []

    def shoot(window: tk.Misc, name: str, title: str, note: str) -> None:
        ui._refresh_views()
        window.update()
        time.sleep(0.2)
        width, height, rgb = capture(window)
        (out / f"{name}.png").write_bytes(png_bytes(width, height, rgb))
        shots.append((f"{name}.png", title, note))
        print(f"saved {name}.png ({width}x{height})")

    def tab(index: int) -> None:
        ui.tabs.select(index)
        root.update()

    try:
        tab(0)
        shoot(
            root,
            "01-today-first-run",
            "Hoy, first run",
            "No session, no bank yet. The first-steps card says what to do.",
        )

        os.environ.pop("GUARDIAN_GCP_BANK")
        if bank is not None:
            os.environ["GUARDIAN_GCP_BANK"] = str(bank)
        saved = ui.settings_store.save(replace(ui.settings_store.load(), all_day=True))
        ui._on_settings_saved(saved)
        ui.all_day_var.set(True)
        ui.autostart_var.set(True)
        ui.start_label.set(ui._start_text())
        ui._start()
        ui._refresh_health()
        ui.question_panel._refresh_bank()
        ui.question_panel._render_domains()
        ui.status.set("")
        shoot(root, "02-today-all-day", "Hoy, studying all day", "All-day session, counter running.")

        ui.presence.on_event("lock")
        ui.paused_reason = ui.presence.paused_reason(True)
        shoot(
            root,
            "03-today-paused-lock",
            "Hoy, counter paused",
            "The screen is locked, so no time is counted.",
        )
        ui.presence.on_event("unlock")
        ui.paused_reason = None

        ui._pause()
        shoot(root, "04-today-pause", "Hoy, paused for 15 minutes", "Pausar from the panel or the tray.")
        ui.pause_until = desktop._EPOCH

        ui.pending = True
        ui.status.set("Examen pendiente en espera: pantalla completa")
        shoot(
            root, "05-today-pending-wait", "Hoy, quiz waiting", "A quiz is due but a full-screen app is open."
        )

        tab(5)
        shoot(root, "06-settings", "Ajustes", "Qué te pregunto, the bank folder, and Cuándo.")

        settings = ui.settings
        topic = SET_TOPICS[settings.question_set]
        questions, source = get_questions(
            topic,
            set(),
            settings.model,
            mode=quiz_mode(settings.source),
            bank_path=settings.bank_path or None,
            cards={},
            domains=settings.domains,
        )
        ui.in_quiz = True
        ui._present_quiz(topic, questions, source, insistent=True)
        quiz = ui.quiz
        shoot(
            quiz.window, "07-quiz-insistent-guard", "Insistent quiz, just opened", "Keys and clicks wait 2 s."
        )
        quiz._set_input(True)
        quiz.selected.set(1)
        shoot(quiz.window, "08-quiz-insistent", "Insistent quiz", "No exit button. It comes back if closed.")

        tab(0)
        shoot(root, "09-today-quiz-open", "Hoy, quiz open", "The panel while the quiz is on screen.")

        for i, q in enumerate(questions):
            quiz.selected.set(q.answer_index if i % 2 == 0 else (q.answer_index + 1) % 4)
            quiz._next()
        result = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_exists()][-1]
        shoot(result, "10-result", "Result review", "One question at a time, with the right answer.")
        result.destroy()

        tab(3)
        shoot(root, "11-reviews", "Repasos", "Pending quiz and recent results.")
        tab(4)
        shoot(root, "12-progress", "Progreso", "Totals and average.")
        tab(1)
        shoot(root, "13-tasks", "Tareas", "Practical tasks written by hand.")
        tab(2)
        shoot(root, "14-evidence", "Evidencia", "Hand in a file and answer the defense.")

        calm = QuizWindow(
            root,
            questions=questions,
            source=source,
            insistent=False,
            on_done=lambda _a: None,
            on_leave=lambda: None,
        )
        shoot(calm.window, "15-quiz-normal", "Quiz with insistent mode off", "It can be postponed.")
        calm.close()

        ui.settings = replace(ui.settings, insistent=False)
        ui._surprise_notice()
        shoot(ui.surprise_popup, "16-notice", "Notice with insistent mode off", "Small, does not take focus.")
    finally:
        ui.tray.stop()
        ui.store.close()
        root.destroy()
    return shots


def main() -> None:
    if sys.platform != "win32":
        sys.exit("The gallery captures native windows and runs on Windows only.")
    parser = argparse.ArgumentParser(description="Screenshots of Guardian as a user sees it")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "gallery")
    parser.add_argument(
        "--bank", type=Path, help="GCP_Data_Engineer_Fieldnotes folder, if it is not found alone"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shots = run(args.out, args.bank)
    write_index(args.out, shots)
    print(f"gallery: {args.out / 'index.html'} ({len(shots)} screenshots)")


if __name__ == "__main__":
    main()
