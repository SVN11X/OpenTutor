"""Ajustes tab, section "Qué te pregunto": the question set, its source, exam domains, minutes between
quizzes and the bank folder. Kept apart from desktop.py so the panel module stays readable.
"""

from __future__ import annotations

import logging
import tkinter as tk
from collections.abc import Callable
from dataclasses import replace
from tkinter import filedialog, ttk

from . import fieldnotes
from .settings_store import DOMAIN_IDS, INTERVAL_BOUNDS, QUESTION_SETS, Settings, SettingsStore

log = logging.getLogger(__name__)

SOURCE_LABELS = {
    "practice": "Todo el banco (práctica, unas 300 preguntas)",
    "reviewed": "Solo revisadas (pocas, se repiten)",
    "ollama": "Ollama local (genera preguntas, puede tardar)",
}
SET_TOPICS = {"gcp-pde": "Google Cloud Data Engineer"}  # the topic name get_questions knows


def quiz_mode(source: str) -> str:
    """The get_questions mode for a saved source."""
    return {"practice": "bank-practice", "reviewed": "bank-only"}.get(source, "ollama")


def bank_summary(bank_path: str) -> tuple[bool, str]:
    """(found, text for the owner) about the bank folder. Read-only."""
    path = fieldnotes.find_bank_path(bank_path or None)
    if path is None:
        return False, "✖ No encuentro el banco. Elige la carpeta GCP_Data_Engineer_Fieldnotes."
    try:
        practice = len(fieldnotes.load_pool(path, reviewed_only=False))
        reviewed = len(fieldnotes.load_pool(path))
    except (OSError, ValueError) as err:
        return False, f"✖ El banco no se pudo leer: {err}"
    return True, f"✔ {practice} preguntas usables, {reviewed} revisadas · {path}"


def domain_labels(bank_path: str) -> dict[int, str]:
    """Domain id to its label, with the bank's names and weights when the bank has them."""
    names = {i: f"{i}. {name} ({weight} %)" for i, name, weight in fieldnotes.domain_names(bank_path or None)}
    return {i: names.get(i, f"Dominio {i}") for i in DOMAIN_IDS}


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
        chosen = set(settings.domains or DOMAIN_IDS)
        self.domain_vars = {i: tk.BooleanVar(value=i in chosen) for i in DOMAIN_IDS}
        self.min_var = tk.StringVar(value=str(settings.interval_min))
        self.max_var = tk.StringVar(value=str(settings.interval_max))
        self.bank_var = tk.StringVar(value=settings.bank_path)
        self.bank_text = tk.StringVar()
        self.model_var = tk.StringVar(value=settings.model)
        self.frame = ttk.LabelFrame(parent, text="Qué te pregunto", padding=10)
        self.frame.pack(fill="x", pady=(0, 10))
        self._build()

    def _build(self) -> None:
        f = self.frame
        ttk.Label(f, text="Conjunto de preguntas:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            f, textvariable=self.set_var, state="readonly", values=list(QUESTION_SETS.values()), width=44
        ).grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Label(f, text="Origen:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            f, textvariable=self.source_var, state="readonly", values=list(SOURCE_LABELS.values()), width=44
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Label(f, text="Dominios del examen:").grid(row=2, column=0, sticky="nw", pady=(6, 0))
        self.domain_box = ttk.Frame(f)
        self.domain_box.grid(row=2, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self._render_domains()
        ttk.Label(f, text="Minutos de actividad entre preguntas:").grid(row=3, column=0, sticky="w", pady=6)
        span = ttk.Frame(f)
        span.grid(row=3, column=1, columnspan=2, sticky="w")
        low, high = INTERVAL_BOUNDS
        ttk.Label(span, text="de").pack(side="left")
        ttk.Spinbox(span, from_=low, to=high, textvariable=self.min_var, width=5).pack(side="left", padx=4)
        ttk.Label(span, text="a").pack(side="left")
        ttk.Spinbox(span, from_=low, to=high, textvariable=self.max_var, width=5).pack(side="left", padx=4)
        ttk.Label(span, text="(al azar dentro del rango)").pack(side="left")
        ttk.Label(f, text="Carpeta del banco:").grid(row=4, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.bank_var, width=36).grid(row=4, column=1, sticky="we", pady=2)
        ttk.Button(f, text="Elegir carpeta…", command=self._choose_bank).grid(row=4, column=2, padx=(6, 0))
        ttk.Label(f, textvariable=self.bank_text, wraplength=500, justify="left").grid(
            row=5, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(f, text="Modelo Ollama:").grid(row=6, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(f, textvariable=self.model_var, width=24).grid(row=6, column=1, sticky="w", pady=(6, 0))
        ttk.Button(f, text="Guardar ajustes", command=self.save).grid(
            row=7, column=2, sticky="e", pady=(10, 0)
        )
        f.columnconfigure(1, weight=1)
        self._refresh_bank()

    def _render_domains(self) -> None:
        for child in self.domain_box.winfo_children():
            child.destroy()
        for i, label in domain_labels(self.bank_var.get().strip()).items():
            ttk.Checkbutton(self.domain_box, text=label, variable=self.domain_vars[i]).pack(anchor="w")

    def _refresh_bank(self) -> None:
        _found, text = bank_summary(self.bank_var.get().strip())
        self.bank_text.set(text)

    def _choose_bank(self) -> None:
        folder = filedialog.askdirectory(parent=self.frame, title="Carpeta GCP_Data_Engineer_Fieldnotes")
        if folder:
            self.bank_var.set(folder)
            self._refresh_bank()
            self._render_domains()

    def read(self) -> Settings:
        """The settings as typed in the form. Raises ValueError with a message for the owner."""
        try:
            low, high = int(self.min_var.get()), int(self.max_var.get())
        except ValueError:
            raise ValueError("Los minutos deben ser números enteros") from None
        domains = tuple(i for i, var in self.domain_vars.items() if var.get())
        if not domains:
            raise ValueError("Marca al menos un dominio del examen")
        set_id = next(k for k, v in QUESTION_SETS.items() if v == self.set_var.get())
        source = next(k for k, v in SOURCE_LABELS.items() if v == self.source_var.get())
        return replace(
            self.settings,
            question_set=set_id,
            source=source,
            domains=() if len(domains) == len(DOMAIN_IDS) else domains,
            interval_min=low,
            interval_max=high,
            bank_path=self.bank_var.get().strip(),
            model=self.model_var.get().strip() or "qwen3.5:4b",
        )

    def save(self) -> None:
        try:
            saved = self.store.save(self.read())
        except ValueError as err:
            self.status(f"Ajustes sin guardar: {err}")
            return
        self.settings = saved
        self._refresh_bank()
        self.on_saved(saved)
        self.status("Ajustes guardados")
