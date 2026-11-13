# 0004. Hand-written tasks and a deterministic defense

- Status: accepted
- Date: 2026-11-13
- Proposed by: Claude Code
- Accepted by: owner

## Context

The OpenTutor planner that was meant to assign practical tasks was removed with the web app. Practical work still needs a
source of tasks and a way to check that the owner understands what they handed in.

## Decision

The owner writes tasks by hand in the Tareas tab (title, slide count, required terms). A .pptx goes through the
deterministic rubric. If it passes, three questions about the file follow: slide count, one slide title and one term that
appears. Decoys never appear in the deck. Validated means rubric passed and at least two of three answers right.

## Alternatives considered

A JSON file of tasks: more editing for the same result. A local model for the defense: slower, and a model must not decide.

## Consequences

Simple and fully local. The defense is weak proof, so it only adds to the rubric, and validated gives no leisure credit
because that system does not exist yet. To undo it, archive the tasks. Submissions stay in the database.
