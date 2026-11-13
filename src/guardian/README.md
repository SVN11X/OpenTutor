# OpenTutor Guardian — notas de uso (Windows)

Este directorio es un agente de escritorio local.
No modifica FocoLocal. Es una prueba funcional
reducida, no un producto completo ni un bloqueo estricto todavía.

## Incluido / no incluido

**Implementado**

- App de escritorio opt-in, usando `tkinter` (Python 3.12 recomendado).
- Sesiones de 60 minutos iniciadas manualmente: no hay interrupciones fuera de la sesión.
- Contador de tiempo activo de 10 a 25 minutos y aviso no modal de 5 preguntas.
- Corrección con aprobación 4/5 y persistencia local en SQLite.
- **Fieldnotes primero:** preguntas desde `../GCP_Data_Engineer_Fieldnotes/content/imported.json`, sin esperar a Ollama.
- Dos modalidades de banco: **revisado/puntuable** y **completo/práctica no puntuable**; se excluyen imágenes y respuestas múltiples en este MVP.
- Ollama opcional por selección explícita, con esquema JSON, verificación estructural y límite de 30 segundos por solicitud.
- Banco pequeño de contingencia para Google Cloud cuando no quedan cinco preguntas revisadas.
- Pausa de 15 minutos, detención voluntaria y salida normal.

**Pendiente (no afirmar como implementado)**

- Detección fiable de reuniones, presentaciones y tareas sensibles.
- Entregas PPTX conectadas al panel, revisión de contenido y defensa oral/escrita.
- API/IPC con FocoLocal y bloqueo de aplicaciones/navegadores; no hay bloqueo alguno.
- Instalador `.exe`, pruebas GUI reales con DPI y dos monitores, revisión pedagógica humana.

## Prerrequisitos

- Windows 10/11, Python con `tkinter` (distribución estándar), Ollama instalado en local.
- Modelo sugerido: `qwen3.5:4b` **si está instalado**. El tiempo de generación
  depende del hardware; el programa lo solicita en un hilo para no congelar la UI.
- No hay dependencias Python de terceros en este MVP.

## Ejecutar (en PowerShell desde la raíz del repositorio)

```powershell
python -m unittest discover -s tests -v
python -m guardian.desktop
```

Para probar rápidamente las alertas sin esperar 10–25 min:

```powershell
python -m guardian.desktop --demo
```

Selecciona **Banco local (rápido)** para cinco preguntas revisadas de Google Cloud.
No espera a Ollama. La aplicación encuentra el repositorio hermano:
`C:\my_drive\Portafolio\GCP_Data_Engineer_Fieldnotes\content\imported.json`.
Si el banco está en otra ubicación, establece la variable `GUARDIAN_GCP_BANK`
con la ruta de la carpeta o del `imported.json` antes de ejecutar la app.

**Banco completo (práctica)** permite utilizar las preguntas no revisadas que
puedan representarse sin imágenes y con una sola respuesta; su clave es
orientativa, los resultados nunca otorgan aprobaciones para desbloqueo.
El banco original no se modifica ni se copia. 349 preguntas importadas no
significa 349 preguntas verificadas o compatibles con el MVP.

Para generar preguntas nuevas, elige **Ollama (puede tardar)**. Es una
acción opcional, no la ruta predeterminada de exámenes sorpresa.
Para otros temas sin banco local, el modo rápido informa la ausencia de contenido.

El archivo SQLite se guarda en
`%LOCALAPPDATA%\OpenTutorGuardian\guardian_mvp.sqlite3`.

## Aislamiento, seguridad, límites

- No se recolectan teclas, ventanas, capturas ni URL; solo se consulta el tiempo
  desde la última entrada mediante la API de Windows.
- Las interrupciones solo se activan por acción del usuario y se pueden detener.
- No se usan políticas de sistema, controlador, proxy, `hosts`, firewall ni credenciales elevadas.
- El MVP es **fail-open**: si Ollama no responde no se impone restricción alguna.
- Las respuestas de Ollama están estructuradas, pero eso **no verifica su veracidad**.
- Fieldnotes se abre solo en lectura. Filtrar por `status=reviewed`, `gradable=true`,
  sin imágenes, sin respuesta múltiple; nunca alterar las 349 preguntas, sus 25 imágenes ni claves.
- El modo de práctica puede usar claves importadas **no verificadas** y no genera
  aprobaciones válidas para ningún bloqueo futuro.
  No usar evaluaciones generadas sin revisión humana como condición para bloquear
  aplicaciones ni para decisiones de alto impacto.
- No registra texto de respuestas, solo índice elegido, enunciados y puntuación.
- La comprobación de actividad mediante Win32 es aproximada: no implica que se
  esté aprendiendo. La elegibilidad real y el modo de segundo monitor requieren
  pruebas e integración adicional.

## Desarrollo posterior

Leer [`docs/CONTRACTS.md`](docs/CONTRACTS.md) y
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) antes de modificar FocoLocal.
Seguir `SVN11X/standards`: PRs pequeños, no repetir pruebas sin cambio de huella,
no commits/push/merge no autorizados.

## v0.2.0 resident agent (delivery A)

Run from the repository root in Windows PowerShell:

    .\scripts\run-dev.ps1            # tests, then the panel
    .\scripts\run-dev.ps1 -Hidden    # starts hidden in the tray

- Tray menu: Abrir panel, Iniciar sesión, Pausar, Terminar, Emergencia, Salir.
- Closing the window hides it to the tray. If the tray icon could not be created, closing exits.
- One instance per user session. A second launch prints a notice and exits.
- A started session survives a restart (`%LOCALAPPDATA%\OpenTutorGuardian\session.json`) until it expires, Terminar or Emergencia.
- No autostart, no blocking, no network. Unverified questions are practice only.
- Design: `docs/ADR-0001-resident-agent.md`.
- Panel tabs: Hoy (state, next review, services, emergency), Tareas (empty state until delivery B),
  Repasos (pending exam and recent results), Progreso, Ajustes (topic, source, schedule, autostart).
  Every status uses icon + text. Unverified sources show as "◐ Práctica".
- Audits and plans: `docs/FOCOLOCAL_ADAPTER_AUDIT.md`, `docs/PRACTICE_VALIDATOR_PLAN.md`.
