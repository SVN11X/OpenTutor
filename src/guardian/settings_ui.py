"""Ajustes tab, section "Qué te pregunto": the question set, its source, exam domains, minutes between
quizzes and the bank folder. Kept apart from desktop.py so the panel module stays readable.

Every change saves itself a moment after the last keystroke, like the switches of the "Cuándo" section,
so the tab needs no Guardar button and nothing typed is lost by leaving it.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import replace
from tkinter import filedialog, ttk

from . import fieldnotes
from .i18n import t
from .settings_store import DOMAIN_IDS, INTERVAL_BOUNDS, QUESTION_SETS, Settings, SettingsStore

log = logging.getLogger(__name__)

SAVE_DELAY_MS = 700  # wait for the owner to stop typing before saving

SOURCE_LABELS = {
    "practice": t("settings.source_practice"),
    "reviewed": t("settings.source_reviewed"),
    "ollama": t("settings.source_ollama"),
}
LANGUAGE_LABELS = {
    "es": t("settings.language_es"),
    "en": t("settings.language_en"),
}
SET_TOPICS = {"gcp-pde": "Google Cloud Data Engineer"}  # the topic name get_questions knows


def quiz_mode(source: str) -> str:
    """The get_questions mode for a saved source."""
    return {"practice": "bank-practice", "reviewed": "bank-only"}.get(source, "ollama")


def bank_summary(bank_path: str) -> tuple[bool, str]:
    """(found, text for the owner) about the bank folder. Read-only."""
    path = fieldnotes.find_bank_path(bank_path or None)
    if path is None:
        return False, t("settings.bank_missing")
    try:
        practice = len(fieldnotes.load_pool(path, reviewed_only=False))
        reviewed = len(fieldnotes.load_pool(path))
    except (OSError, ValueError) as err:
        return False, t("settings.bank_read_error", error=err)
    return True, t("settings.bank_ok", practice=practice, reviewed=reviewed)


def bank_folder(bank_path: str) -> str:
    """The folder to show in the bank field: the one typed, else the one Guardian found by itself."""
    if bank_path:
        return bank_path
    path = fieldnotes.find_bank_path(None)
    if path is None:
        return ""
    return str(path.parent.parent if path.parent.name == "content" else path.parent)


def domain_labels(bank_path: str) -> dict[int, str]:
    """Domain id to its label, with the bank's names and weights when the bank has them."""
    names = {
        i: t("settings.domain_named", number=i, name=name, weight=weight)
        for i, name, weight in fieldnotes.domain_names(bank_path or None)
    }
    return {i: names.get(i, t("settings.domain_fallback", number=i)) for i in DOMAIN_IDS}


class QuestionSettingsPanel:
    """Edits the saved Settings. on_saved receives the validated settings after a save."""

    def __init__(
        self,
        parent: ttk.Frame,
        store: SettingsStore,
        settings: Settings,
        on_saved: Callable[[Settings], None],
        status: Callable[[str], None],
    ) -> None:
        self.store, self.settings, self.on_saved, self.status = store, settings, on_saved, status
        self.set_var = tk.StringVar(value=QUESTION_SETS[settings.question_set])
        self.source_var = tk.StringVar(value=SOURCE_LABELS[settings.source])
        self.language_var = tk.StringVar(value=LANGUAGE_LABELS[settings.language])
        chosen = set(settings.domains or DOMAIN_IDS)
        self.domain_vars = {i: tk.BooleanVar(value=i in chosen) for i in DOMAIN_IDS}
        self.min_var = tk.StringVar(value=str(settings.interval_min))
        self.max_var = tk.StringVar(value=str(settings.interval_max))
        # A bank found by itself is shown in the field but saved as "", so the automatic search still runs.
        self.found_folder = "" if settings.bank_path else bank_folder("")
        self.bank_var = tk.StringVar(value=settings.bank_path or self.found_folder)
        self.save_job: str | None = None
        self.bank_text = tk.StringVar()
        self.model_var = tk.StringVar(value=settings.model)
        self.frame = ttk.LabelFrame(parent, text=t("settings.section"), padding=10)
        self.frame.pack(fill="x", pady=(0, 10))
        self._build()
        for var in (
            self.set_var,
            self.source_var,
            self.language_var,
            self.min_var,
            self.max_var,
            self.bank_var,
            self.model_var,
            *self.domain_vars.values(),
        ):
            var.trace_add("write", self._changed)

    def _build(self) -> None:
        f = self.frame
        ttk.Label(f, text=t("settings.question_set_label")).grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            f, textvariable=self.set_var, state="readonly", values=list(QUESTION_SETS.values()), width=44
        ).grid(row=0, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(f, text=t("settings.source_label")).grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            f, textvariable=self.source_var, state="readonly", values=list(SOURCE_LABELS.values()), width=44
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(f, text=t("settings.language_label")).grid(row=2, column=0, sticky="w")
        ttk.Combobox(
            f,
            textvariable=self.language_var,
            state="readonly",
            values=list(LANGUAGE_LABELS.values()),
            width=44,
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(f, text=t("settings.domains_label")).grid(row=3, column=0, sticky="nw", pady=(6, 0))
        self.domain_box = ttk.Frame(f)
        self.domain_box.grid(row=3, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self._render_domains()
        ttk.Label(f, text=t("settings.interval_label")).grid(row=4, column=0, sticky="w", pady=8)
        span = ttk.Frame(f)
        span.grid(row=4, column=1, columnspan=2, sticky="w")
        low, high = INTERVAL_BOUNDS
        ttk.Label(span, text=t("settings.interval_from")).pack(side="left")
        ttk.Spinbox(span, from_=low, to=high, textvariable=self.min_var, width=5).pack(side="left", padx=4)
        ttk.Label(span, text=t("settings.interval_to")).pack(side="left")
        ttk.Spinbox(span, from_=low, to=high, textvariable=self.max_var, width=5).pack(side="left", padx=4)
        ttk.Label(span, text=t("settings.interval_random")).pack(side="left")
        ttk.Label(f, text=t("settings.bank_label")).grid(row=5, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.bank_var, width=36).grid(row=5, column=1, sticky="we", pady=4)
        ttk.Button(f, text=t("settings.choose_folder"), command=self._choose_bank).grid(
            row=5, column=2, padx=(8, 0)
        )
        ttk.Label(f, textvariable=self.bank_text, wraplength=500, justify="left").grid(
            row=6, column=1, columnspan=2, sticky="w"
        )
        ttk.Label(f, text=t("settings.model_label")).grid(row=7, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(f, textvariable=self.model_var, width=24).grid(row=7, column=1, sticky="w", pady=(8, 0))
        f.columnconfigure(1, weight=1)
        self._refresh_bank()

    def _render_domains(self) -> None:
        for child in self.domain_box.winfo_children():
            child.destroy()
        for i, label in domain_labels(self.bank_var.get().strip()).items():
            ttk.Checkbutton(self.domain_box, text=label, variable=self.domain_vars[i]).pack(
                anchor="w", pady=4
            )

    def _refresh_bank(self) -> None:
        _found, text = bank_summary(self.bank_var.get().strip())
        self.bank_text.set(text)

    def _choose_bank(self) -> None:
        folder = filedialog.askdirectory(parent=self.frame, title=t("settings.bank_dialog_title"))
        if folder:
            self.bank_var.set(folder)  # _changed saves it, counts its questions and relabels the domains

    def read(self) -> Settings:
        """The settings as typed in the form. Raises ValueError with a message for the owner."""
        try:
            low, high = int(self.min_var.get()), int(self.max_var.get())
        except ValueError:
            raise ValueError(t("settings.error_minutes")) from None
        domains = tuple(i for i, var in self.domain_vars.items() if var.get())
        if not domains:
            raise ValueError(t("settings.error_no_domains"))
        set_id = next(k for k, v in QUESTION_SETS.items() if v == self.set_var.get())
        source = next(k for k, v in SOURCE_LABELS.items() if v == self.source_var.get())
        language = next(k for k, v in LANGUAGE_LABELS.items() if v == self.language_var.get())
        typed_bank = self.bank_var.get().strip()
        return replace(
            self.store.load(),  # other sections save their own fields, never overwrite them here
            question_set=set_id,
            source=source,
            language=language,
            domains=() if len(domains) == len(DOMAIN_IDS) else domains,
            interval_min=low,
            interval_max=high,
            bank_path="" if typed_bank == self.found_folder else typed_bank,
            model=self.model_var.get().strip() or "qwen3.5:4b",
        )

    def _changed(self, *_args: object) -> None:
        """Save a moment after the last change, so typing a number or a path saves once."""
        if self.save_job is not None:
            self.frame.after_cancel(self.save_job)
        self.save_job = self.frame.after(SAVE_DELAY_MS, self.save)

    def save(self) -> None:
        """Save the form now. A value that cannot be saved is reported and the saved settings stay."""
        if self.save_job is not None:
            self.frame.after_cancel(self.save_job)  # saved now, the delayed save has nothing left to do
            self.save_job = None
        try:
            saved = self.store.save(self.read())
        except ValueError as err:
            self.status(t("settings.save_error", error=err))
            return
        bank_moved = saved.bank_path != self.settings.bank_path
        self.settings = saved
        self._refresh_bank()
        if bank_moved:
            self._render_domains()
        self.on_saved(saved)
        self.status(t("settings.saved"))
