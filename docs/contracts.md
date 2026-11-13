# Contratos futuros. Guardian ⇆ OpenTutor ⇆ FocoLocal

**Estado:** diseño, NO implementado. No inventar endpoints que los repositorios
no exponen. Auditar el código real antes de codificar adaptadores.

## Riesgos que el contrato debe resolver

- Un dominio puede usarse tanto para ocio como para formación.
- FocoLocal conserva sus reglas, contadores, exclusiones de automatización y
  diferenciación Shorts/vídeos. Guardian no modificará su JSON de configuración
  como protocolo IPC.
- Bloqueo temporal debe tener TTL, dueño, causa y reversión sin corromper reglas.
- Si Guardian, Ollama u OpenTutor fallan, la integración debe liberar los
  bloqueos efímeros creados por Guardian; no los límites permanentes de FocoLocal.
- Un LLM sin revisión no decide privilegios ni desbloqueos.

## API local FocoLocal (propuesta v1; *no existe actualmente*)

Canal: IPC de Windows restringido al usuario, con ACL y autenticación; evitar
abrir puertos públicos. Implementar solo tras inspeccionar el repositorio Go.

- `capabilities()` -> `{protocol_version, supported_scopes, fallback_mode}`
- `apply_lease({idempotency_key, owner, scope, reason, expires_at})`
- `release_lease({idempotency_key, owner, lease_id})`
- `list_active_leases({owner})`
- `health()`

Garantías: idempotencia; operaciones atómicas; duración máxima; prioridad de
excepciones esenciales; separación entre reglas propias y leases de Guardian;
`emergency_release(owner)` siempre disponible al usuario.

La aplicación de estas propuestas requiere una ADR y pruebas de contrato en
ambos repositorios. No asumir que `apply_lease` puede bloquear por URL/ruta
individual sin extensiones. La capacidad debe anunciarse realmente.

## OpenTutor (adaptador futuro)

El planificador debe consumir **la API que exista en la versión fijada** para:

1. Recuperar objetivos aprobados por el usuario y temas pendientes.
2. Pedir un lote de cinco preguntas con evidencia de fuente, dificultad y clave.
3. Enviar resultado y registrar errores en progreso de aprendizaje.
4. Recibir una siguiente tarea propuesta, sin autoautorizar obligaciones.

Si la API no existe, agregar un endpoint mínimo y versionado mediante PR
separado. No duplicar el motor educativo entero dentro de Guardian.

## Seguridad de concesión de ocio (futuro)

El evaluador entrega `submission_id`, `status`, `rubric_version`, `evidence_ref`
y `assessment_source`. El motor de reglas concede un crédito solo cuando la
fuente de evaluación y los requisitos aprobados sean confiables para la política.
Una pregunta autogenerada sin revisión editorial se marca `unreviewed`, y no
es evidencia suficiente para un bloqueo/desbloqueo estricto.
