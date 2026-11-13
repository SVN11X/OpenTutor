# Practice work validator plan (deliveries B and C, not implemented)

Goal: check a deliverable (`.pptx`, `.pdf`, `.md`) with deterministic rules first. Never
approve only because a file exists. Never run macros or any code from the file.

## Safe reading
- PPTX/DOCX are ZIP files. Read XML with `zipfile` + `xml.etree` only. Reject files with
  `vbaProject.bin`, more than 200 MB uncompressed, more than 2000 entries, or path
  traversal names (zip bomb and zip slip checks) before parsing.
- No `python-pptx` macro execution paths, no LibreOffice conversion, no external links followed.
- PDF: page count and text through a pure parser only if one is approved in the radar.

## Rubric (versioned, `rubric_version`)
Deterministic checks, each pass/fail with evidence:
- file type matches extension, size limit, opens as ZIP/PDF/UTF-8
- slide count equals the task (for example 5), each slide has a title and non-empty text
- required terms from the task appear (case-insensitive, whole word)
- no duplicated slides, no placeholder text such as "Click to edit"

## Result contract
`{submission_id, status, rubric_version, evidence_ref, assessment_source}` with `status` in
`passed`, `failed`, `needs_review`. Ambiguous content is always `needs_review` plus a short
three-question defense. Only `passed` from a deterministic rubric plus a reviewed defense
can count as credit. A local model may explain, never decide.

## Order
1. `evidence/safe_zip.py` + tests with hostile samples (bomb, slip, macro).
2. `evidence/pptx_check.py` + rubric JSON + tests.
3. Panel tab "Evidencia" (accessible: icon + text + color).
4. OpenTutor planner task creation, only after the user consents at setup.
