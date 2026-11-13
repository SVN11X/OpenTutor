"""Local Ollama assessment generation with conservative validation.

MVP relies on generated answer keys; this is NOT a guarantee of factual truth.
Educators should review a generated bank before using results for high-stakes unlocks.
"""

from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .core import Question, validate_questions
from .fieldnotes import reviewed_questions

log = logging.getLogger(__name__)

# Validated, manually authored fallback for one known topic only. No fake
# auto-grading of arbitrary subjects when Ollama is unavailable.
FALLBACK_GCP = [
    Question(
        "¿Qué servicio de Google Cloud está orientado a análisis SQL de grandes conjuntos de datos?",
        ("BigQuery", "Cloud SQL", "Cloud DNS", "Cloud CDN"),
        0,
        "BigQuery es un almacén analítico administrado para consultas SQL a escala.",
    ),
    Question(
        "¿Cuál es un servicio de mensajería asíncrona de Google Cloud?",
        ("Cloud Storage", "Pub/Sub", "Cloud Run", "Cloud NAT"),
        1,
        "Pub/Sub permite publicar mensajes y recibirlos mediante suscripciones.",
    ),
    Question(
        "¿Qué producto administra objetos en buckets?",
        ("Bigtable", "Cloud SQL", "Cloud Storage", "Memorystore"),
        2,
        "Cloud Storage almacena objetos en buckets.",
    ),
    Question(
        "¿Qué servicio ejecuta contenedores sin administrar servidores?",
        ("Cloud DNS", "BigQuery", "Cloud IAM", "Cloud Run"),
        3,
        "Cloud Run ejecuta servicios y trabajos contenerizados sin administrar servidores.",
    ),
    Question(
        "¿Para qué se utiliza principalmente Cloud IAM?",
        ("Administrar permisos", "Crear subredes", "Almacenar objetos", "Crear imágenes de VM"),
        0,
        "IAM controla quién puede acceder a qué recursos mediante roles y permisos.",
    ),
    Question(
        "¿Qué servicio ofrece una base de datos relacional administrada?",
        ("Pub/Sub", "Cloud SQL", "Cloud Logging", "Cloud CDN"),
        1,
        "Cloud SQL es un servicio administrado de bases de datos relacionales.",
    ),
    Question(
        "¿Qué herramienta procesa datos mediante pipelines por lotes o streaming?",
        ("Cloud NAT", "Cloud DNS", "Dataflow", "Cloud CDN"),
        2,
        "Dataflow permite ejecutar pipelines de procesamiento por lotes y streaming.",
    ),
    Question(
        "¿Qué servicio organiza acceso y facturación dentro de una jerarquía de recursos?",
        ("Cloud Router", "Pub/Sub", "Cloud Functions", "Resource Manager"),
        3,
        "Resource Manager gestiona la jerarquía de recursos, como organizaciones, carpetas y proyectos.",
    ),
    Question(
        "¿Qué producto permite observar métricas de recursos y servicios?",
        ("Cloud Monitoring", "Cloud Storage", "Bigtable", "Cloud Armor"),
        0,
        "Cloud Monitoring recopila y presenta métricas y alertas.",
    ),
    Question(
        "¿Qué producto está diseñado para almacenar grandes volúmenes de datos NoSQL de columnas anchas?",
        ("Cloud SQL", "Bigtable", "Cloud DNS", "Secret Manager"),
        1,
        "Bigtable es una base de datos NoSQL de columnas anchas para grandes escalas.",
    ),
]


SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                    "answer_index": {"type": "integer", "minimum": 0, "maximum": 3},
                    "explanation": {"type": "string"},
                },
                "required": ["prompt", "options", "answer_index", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def get_questions(
    topic: str,
    recent: set[str],
    model: str = "qwen3.5:4b",
    endpoint: str = "http://127.0.0.1:11434",
    *,
    mode: str = "bank-first",
    bank_path=None,
) -> tuple[list[Question], str]:
    """Prefer reviewed local questions; use Ollama only when explicitly requested.

    Modes: 'bank-first', 'bank-only', 'bank-practice' use local Fieldnotes; 'ollama'
    requests generation. The local bank is read-only and not automatically
    downloaded. Remote Ollama endpoints are forbidden by this MVP.
    """
    if endpoint not in ("http://127.0.0.1:11434", "http://localhost:11434"):
        raise ValueError("Solo se permite Ollama local en este MVP")
    if mode not in {"bank-first", "bank-only", "bank-practice", "ollama"}:
        raise ValueError("Modo de preguntas inválido")

    gcp = topic.strip().casefold() in {
        "google cloud",
        "gcp",
        "google cloud pde",
        "google cloud data engineer",
    }
    if gcp and mode != "ollama":
        practice = mode == "bank-practice"
        selected = reviewed_questions(recent, bank_path=bank_path, limit=5, reviewed_only=not practice)
        reviewed_count = len(selected)
        if len(selected) == 5:
            return selected, "fieldnotes-practice-unverified" if practice else "fieldnotes-reviewed"
        # Small curated fallback; never recycle prompts already answered.
        fallback = [q for q in FALLBACK_GCP if q.prompt.strip().casefold() not in recent]
        used = {candidate.prompt.strip().casefold() for candidate in selected}
        available = [q for q in fallback if q.prompt.strip().casefold() not in used]
        selected.extend(available[: 5 - len(selected)])
        if len(selected) == 5:
            if practice and reviewed_count:
                return selected, "fieldnotes-practice-unverified"
            return selected, "fieldnotes+fallback-reviewed" if reviewed_count else "fallback-reviewed"
        raise RuntimeError("No quedan cinco preguntas disponibles sin repetir; revisa tu banco Fieldnotes")
    if mode in {"bank-only", "bank-practice"}:
        raise RuntimeError(
            "No existe un banco para este tema. Selecciona Ollama si deseas generar preguntas nuevas"
        )

    query = {
        "model": model,
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0.2},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres tutor. Devuelve solo JSON que siga el esquema. "
                    "Genera 5 preguntas en español, cada una con 4 opciones diferentes, "
                    "una sola opción correcta y explicación clara. "
                    "No uses respuestas obvias ni hechos dudosos. No inventes fuentes."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Tema: {topic[:160]}. Evita repetir: " + "; ".join(list(sorted(recent))[:8])[:1000]
                ),
            },
        ],
    }
    request = Request(
        endpoint + "/api/chat",
        data=json.dumps(query).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        generated = json.loads(payload["message"]["content"])
        questions = validate_questions(generated["questions"])
        if any(q.prompt.strip().casefold() in recent for q in questions):
            raise ValueError("Preguntas ya utilizadas")
        return questions, "ollama-unreviewed"
    except (URLError, HTTPError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as err:
        log.warning(
            "Ollama gave no usable questions (%s); falling back to the reviewed bank", type(err).__name__
        )
        if not gcp:
            raise RuntimeError(
                "Ollama no respondió con preguntas válidas para este tema; no hay banco revisado"
            ) from None
        available = [q for q in FALLBACK_GCP if q.prompt.strip().casefold() not in recent]
        if len(available) < 5:
            raise RuntimeError(
                "Banco revisado agotado; se requiere generar y revisar preguntas nuevas"
            ) from None
        return available[:5], "fallback-reviewed"
