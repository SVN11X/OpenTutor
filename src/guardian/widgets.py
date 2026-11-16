"""Small tkinter helpers shared by the panel and the quiz window.

Both have content taller than a small screen and one main action per state, so both need a scrolled area
that keeps their fixed buttons in view and one way to mark the main action.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PRIMARY = "Primary.TButton"


def primary_style(widget: tk.Misc) -> str:
    """The style name for the main action of a window: the theme's button with bold text."""
    style = ttk.Style(widget)
    if not style.configure(PRIMARY, "font"):  # its own font, lookup would return the inherited one
        style.configure(PRIMARY, font=("Segoe UI", 10, "bold"))
        widget.update_idletasks()  # apply it now, not in an idle call that could outlive the window
    return PRIMARY


def scrolled(parent: tk.Misc, *, padding: int | tuple[int, ...] = 0) -> tuple[tk.Canvas, ttk.Frame]:
    """A frame that scrolls vertically inside parent, with the mouse wheel while the pointer is over it."""
    canvas = tk.Canvas(parent, highlightthickness=0, height=200)
    bar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    content = ttk.Frame(canvas, padding=padding)
    item = canvas.create_window((0, 0), window=content, anchor="nw", state="hidden")
    content.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width), add="+")
    # A canvas keeps its inner window mapped when a notebook hides its tab. Hide it too, so screen
    # readers and checks see only the tab on screen.
    canvas.bind("<Unmap>", lambda _e: canvas.itemconfigure(item, state="hidden"), add="+")
    canvas.bind("<Map>", lambda _e: canvas.itemconfigure(item, state="normal"), add="+")

    def wheel(event: tk.Event) -> None:
        try:
            widget = canvas.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):  # a popup Tk does not name, such as a combobox list
            return
        while widget is not None and widget is not canvas:
            widget = widget.master
        if widget is canvas:
            canvas.yview_scroll(-int(event.delta / 120), "units")

    canvas.winfo_toplevel().bind("<MouseWheel>", wheel, add="+")
    return canvas, content
