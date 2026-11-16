# 0007. Insistent quiz window and all-day mode

- Status: accepted
- Date: 2026-11-16
- Proposed by: Claude Code
- Accepted by: owner, through the answers given on 2026-11-16

## Context

The owner wants Guardian installed and running all day in the background, asking Google Cloud Data Engineer questions in a window that must be answered. Decision 0002 says the surprise notice never takes keyboard focus, the quiz has a "Posponer / salir" button and a session lasts 60 minutes. The bank has only 12 reviewed single-answer questions without images, so an all-day rhythm of one quiz every 10 to 25 minutes runs out of reviewed questions in about an hour.

## Decision

- Insistent quiz window, on by default, with a setting in Ajustes to turn it off. When a quiz is due, the quiz itself opens centered, always on top and with focus. It has no "Más tarde" and no exit button. Closing or minimizing it brings it back after a few seconds. Keyboard input is ignored for the first two seconds, so typing in another app does not answer by accident.
- Emergencia and Salir stay in the tray menu at all times. Emergencia ends the session and drops the pending quiz. Salir closes Guardian and keeps the quiz pending, so it opens again at the next start.
- While Windows reports a full-screen app, presentation mode or quiet hours, the quiz waits and opens when that state ends. Guardian reads only this state flag from `SHQueryUserNotificationState`, never the screen.
- All-day mode, a setting. A session in this mode has no 60-minute limit. It lasts until Terminar or Emergencia and asks only inside the schedule, when one is set. With autostart on, the session starts by itself when the owner signs in to Windows. Turning the setting on counts as the explicit start that decision 0002 requires.
- The eligible clock stops while the computer is suspended, while the Windows session is locked and while the owner is idle. Suspend and lock arrive as Windows messages on the hidden tray window.
- Questions are chosen by spaced repetition with Leitner boxes: a wrong answer comes back sooner, a right one later, and the bank never runs out. The default source is the whole bank as practice, about 310 questions, always labelled Práctica. Reviewed only stays as an option.
- What Guardian asks is set in Ajustes, under "Qué te pregunto": the question set (only Google Cloud Data Engineer for now), the source, the exam domains and the minimum and maximum minutes between quizzes.

## Alternatives considered

- Keep the notice that does not take focus, with "Más tarde". The owner rejected it because it is easy to ignore.
- A full-screen or system-modal window. Rejected, because it would block work tools and emergencies, a non-goal.
- An Emergencia button inside the window, or one postponement of five minutes. Offered, and the owner chose no exit in the window.
- Show the quiz over full-screen apps too. Offered, and the owner chose to wait.
- Reviewed questions only by default. Offered, and the owner chose the whole bank as practice.

## Consequences

- Supersedes two lines of decision 0002: the notice that does not take focus, and the rule that nothing starts without a manual start, which now also accepts the all-day setting.
- The quiz interrupts work while it is open, but it never blocks another app, the taskbar or the tray menu.
- A video call in a normal window is not detected. The owner can pause from the tray before a call.
- Results from the whole bank are practice, never a certified pass. The goals stay unchanged on this point.
- To undo: turn off "Ventana insistente" and "Todo el día" in Ajustes, or revert this decision and its code.
