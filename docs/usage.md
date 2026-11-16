# Usage guide (Windows)

OpenTutor Guardian 0.3.0. The panel is in Spanish, this guide is in English. Design reasons are in
[decisions/0007-insistent-quiz-and-all-day-mode.md](decisions/0007-insistent-quiz-and-all-day-mode.md).

## Install or run

- Installer: run `OpenTutorGuardian-Setup-0.3.0.exe` from `dist\installer\` or a release. No administrator
  rights. It is unsigned, so SmartScreen may ask for "More info" and "Run anyway".
- From source, in Windows PowerShell at the repository root: `.\scripts\run-dev.ps1`. Add `-Hidden` to start
  in the tray, `-Demo` for quizzes after 20 to 30 seconds of activity, `-TestsOnly` to run the tests.

## First steps

1. Open the panel from the tray icon next to the clock, a blue shield with a check. Windows 11 puts new icons
   behind the arrow (^) next to the clock: drag the shield out of it to keep it always visible.
   The Hoy tab lists the first steps.
2. Ajustes, "Qué te pregunto": check the line under "Carpeta del banco". It must say how many questions it
   found. If not, press "Elegir carpeta…" and pick `GCP_Data_Engineer_Fieldnotes` (or its `content` folder).
   The environment variable `GUARDIAN_GCP_BANK` also works.
3. Ajustes, "Cuándo": turn on "Todo el día". This also turns on "Iniciar Guardian con Windows".
4. Optional: a study schedule such as `08:00-13:00, 15:00-20:00`. Outside it, no quiz opens.

## What happens during the day

- The session starts when Guardian starts and renews at midnight. "Terminar" ends it until the next start
  or until you press "Iniciar día".
- The counter adds only seconds of real activity: keyboard or mouse in the last 3 minutes, session not
  locked, computer not suspended, not paused, inside the schedule. Hoy shows the minutes to the next quiz,
  today's active time, and why the counter is paused.
- When the quiz is due it opens centered and on top, with no exit button. Closing or minimizing it brings it
  back after 5 seconds. It waits while a full-screen app or presentation mode is on, and while paused,
  locked or outside the schedule. For 2 seconds after it appears it ignores keys and clicks.
- Answer all 5 questions to close it. The result appears in Repasos and Progreso.

## What it asks

- Question set: Google Cloud Professional Data Engineer, the only one for now.
- Language: questions appear in Spanish when the bank has a current translation. "Inglés (original)" shows the
  English bank instead. A question whose translation is stale stays in English.
- Source: "Todo el banco (práctica)" uses about 305 questions without images and with one answer. Their keys
  are not reviewed, so results count as practice, never as a certified pass. "Solo revisadas" uses 12
  reviewed questions plus 10 backup ones. "Ollama local" generates questions with a local model and may take
  up to 30 seconds.
- Exam domains: uncheck the ones you do not want.
- Minutes between quizzes: a random value inside the range, 2 to 240.
- Spaced repetition: a wrong answer returns after 10 minutes, a right one after 1 hour, then 4 hours, 1, 3
  and 7 days. Due questions come first, then new ones.

## Ways out

- Tray menu: Pausar (15 minutes), Terminar, Emergencia, Salir. They work while a quiz is open.
- Terminar keeps the pending quiz for the next session. Emergencia ends the session, drops the pending quiz
  and forgets the schedule. Salir closes Guardian and keeps the quiz pending.
- Turn off "Ventana insistente" in Ajustes to get a small notice with "Más tarde" instead.
- Uninstall from Windows Settings, Apps. The uninstaller removes the autostart value.

## Data and privacy

- Everything is stored in `%LOCALAPPDATA%\OpenTutorGuardian\guardian_mvp.sqlite3`: results, settings,
  session, per-question scheduling and active seconds per day. Logs are in the same folder.
- Guardian reads only the time since the last input, lock and suspend messages, and whether a full-screen
  app or presentation mode is on. Never keys, screens, window titles or URLs. No telemetry.
- The question bank is read only. It is never copied or changed.
- The only network call is the optional local Ollama at `127.0.0.1:11434`.

## Known limits

- No app or site blocking, no FocoLocal link.
- Windows Do Not Disturb and video calls in a normal window are not detected.
- Bank questions appear in the language of the bank, mostly English.
- High DPI at 150 percent, two monitors and real suspend and lock still need a check on the owner's machine.
