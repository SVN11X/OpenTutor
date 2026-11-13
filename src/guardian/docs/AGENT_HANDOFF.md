# Instrucciones de continuación para agentes (después de aplicar el parche)

Objetivo: evolucionar Guardian sin repetir trabajo ni generar bloqueos
irreversibles. El parche actual es un MVP no privilegiado: **no es el producto final**.

## Reglas de trabajo

1. Leer instrucciones `AGENTS.md`, `CLAUDE.md`, `.standard.yml`, `docs/goals.md`
   si existen; la política efectiva del repo tiene precedencia sobre este archivo.
2. Registrar rama, commit base, `git status`, versión de OpenTutor y FocoLocal.
3. No volver a crear fork, no clonar repos existentes, no descargar modelos no
   autorizados, no pedir benchmarks ya documentados. Usar el enrutador real de
   modelos de `SVN11X/standards` y su modo de costo.
4. No reimplementar Tutor/Planner/FSRS/quiz de OpenTutor: primero integrar por
   contratos/API que existan, después extensión mínima.
5. No editar JSON de configuración de FocoLocal como mecanismo de integración.
   Definir IPC versionado que respete límites existentes, Shorts/vídeos, tareas
   automatizadas, doble monitor y preferencias.
6. No escribir sobre main, hacer commits/push/PR solo con permiso, no forzar push.
7. Verificar tests por huella de cambio: si no cambió, reutilizar evidencia
   anterior; no declarar validación Windows por tests hechos en Linux.

## Tickets siguientes y dependencias

- GDN-010 (primero): conectar lectura de objetivos y fuentes de OpenTutor en
  Guardian; tests de contrato; reutilizar los cuestionarios existentes.
- GDN-020: adaptar interfaz a Win32/.NET o librería de bandeja robusta,
  autoarranque opt-in, ventanas accesibles y excepciones de reuniones.
- GDN-030: validar presentaciones PPTX, rubricar evidencia y defensa; separar
  controles objetivos de valoración asistida por LLM.
- GDN-040: diseñar y desarrollar IPC con FocoLocal, leases temporales,
  idempotencia, ACL y TTL, sin romper reglas preexistentes.
- GDN-050: integrar motor de bloqueo solo tras pasar GDN-040 y probar en Windows
  real. Desactivar leases de Guardian al fallar; mantener salida de emergencia.
- GDN-060: instalador, telemetría local opcional, recuperación, revisión de
  licencia/avisos, regresión y release candidate.

## Validación del parche inicial (no repetir por defecto)

`python -m unittest discover -s tests -v`

Luego validar GUI manualmente en Windows, primero con `--demo`, y registrar
por qué y cuándo la prueba debe repetirse. No anunciar que la GUI está validada
por una prueba unitaria.
