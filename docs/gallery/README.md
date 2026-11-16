# Gallery

OpenTutor Guardian 0.5.0 as a user sees it on Windows. Real captures of the program's own
windows, made by `scripts/gallery.py` with throwaway data and a sample bank made of the 10 backup questions in `src/guardian/questions.py`.
The bank path in Ajustes is a neutral example, never a folder of the machine that made it.
The panel text is in Spanish. Regenerate after any interface change, from the repository root:

```
python scripts/gallery.py
```

Why it is versioned: `docs/decisions/0008-versioned-screenshot-gallery.md`.

## Hoy, first run

No session, no bank yet. The first-steps card says what to do.

![Hoy, first run](01-today-first-run.png)

## Hoy, studying all day

All-day session, counter running.

![Hoy, studying all day](02-today-all-day.png)

## Hoy, counter paused

The screen is locked, so no time is counted.

![Hoy, counter paused](03-today-paused-lock.png)

## Hoy, paused for 15 minutes

Pausar from the panel or the tray.

![Hoy, paused for 15 minutes](04-today-pause.png)

## Hoy, quiz waiting

A quiz is due but a full-screen app is open.

![Hoy, quiz waiting](05-today-pending-wait.png)

## Ajustes

Cuándo first, then Qué te pregunto. Changes save themselves.

![Ajustes](06-settings.png)

## Insistent quiz, just opened

Keys and clicks wait 2 s.

![Insistent quiz, just opened](07-quiz-insistent-guard.png)

## Insistent quiz

No exit button. It comes back if closed.

![Insistent quiz](08-quiz-insistent.png)

## Hoy, quiz open

The panel while the quiz is on screen.

![Hoy, quiz open](09-today-quiz-open.png)

## Result review

One question at a time, with the right answer.

![Result review](10-result.png)

## Repasos

Pending quiz and recent results.

![Repasos](11-reviews.png)

## Progreso

Totals and average.

![Progreso](12-progress.png)

## Tareas

Practical tasks written by hand.

![Tareas](13-tasks.png)

## Evidencia

Hand in a file and answer the defense.

![Evidencia](14-evidence.png)

## Quiz with insistent mode off

It can be postponed.

![Quiz with insistent mode off](15-quiz-normal.png)

## Notice with insistent mode off

Small, does not take focus.

![Notice with insistent mode off](16-notice.png)
