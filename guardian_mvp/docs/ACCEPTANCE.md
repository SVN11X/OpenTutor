# Criterios de aceptación y estado de evidencias

| Caso | Resultado esperado | Estado actual |
|---|---|---|
| Programa inicia desactivado | No genera interrupciones sin iniciar estudio | Código implementado; Windows sin verificar |
| Reloj elegible | Intervalo 600–1500 s; sin contar inactividad/suspensión | Test unitario |
| Aviso sorpresa | Ventana no modal y pregunta pendiente | Código implementado; Windows sin verificar |
| Generación | 5 preguntas distintas, 4 opciones y clave válida | Test estructural; calidad pedagógica por validar |
| Calificación | 4/5 aprueba, 3/5 reprueba | Test unitario |
| Persistencia | SQLite conserva resultados tras reinicio | Test unitario |
| Contingencia Ollama | Fallo sin bloqueo; banco validado solo GCP | Implementado; test de caída real pendiente |
| Bloqueo FocoLocal | No altera FocoLocal sin contrato validado | No implementado |
| Revisión de PPTX | Archivo, rúbrica y defensa | No implementado |
| Inicio automático/tray | Opt-in y salida de emergencia | No implementado |
| DPI y segundo monitor | Compatible con Windows real | No probado |

## Cómo probar sin reiniciar la batería histórica

1. `python -m unittest discover -s guardian_mvp/tests -v`
2. Revisar únicamente archivos del módulo Guardian.
3. En Windows: `python -m guardian_mvp.desktop --demo`.
4. Validar arranque opt-in, aviso, cinco preguntas, 4/5, 3/5, historial,
   salida, Ollama detenido y reinicio.
5. Registrar comando, commit/huella, sistema y resultado. En caso de cambio
   acotado repetir solamente tests afectados; suite global para release.

No llamar «validado en Windows» a una ejecución de `unittest` en Linux.
