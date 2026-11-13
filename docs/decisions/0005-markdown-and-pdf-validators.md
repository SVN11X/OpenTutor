# 0005. Markdown and PDF validators without third-party libraries

- Status: accepted
- Date: 2026-11-13
- Proposed by: Claude Code
- Accepted by: owner

## Context

Practical work can be a presentation, a Markdown document or a PDF. The project has no runtime dependencies and a new
tool or library has to pass the radar first.

## Decision

Check Markdown as text (sections, empty sections, placeholders, duplicate headings, minimum words, UTF-8 and size).
Check PDF with the standard library only: structure, size, active content also inside compressed streams, decompression
bomb limits and page count. A PDF cannot be read reliably without a parser, so required terms that are not found give
needs review and never a rejection. The defense asks about sections for Markdown and about the page count for PDF.

## Alternatives considered

A PDF library such as pypdf: reads text properly, but it adds a dependency and its own attack surface. Revisit it after a
radar entry if PDF text matters.

## Consequences

No new dependencies and nothing is rendered or run. The PDF defense is one question, so it is the weakest proof of the
three kinds. To undo it, remove the kind from the task form. Existing evidence stays in the database.
