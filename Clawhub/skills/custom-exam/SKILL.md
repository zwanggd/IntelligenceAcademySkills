---
name: custom-exam
description: Fixed 5-dimension exam skill for producing answer artifacts for isolated evaluation.
user-invocable: true
---

# Custom Exam

## Purpose

Run a fixed exam from editable files inside this folder and write machine-readable answer artifacts.

This skill must not judge or score answers.
This skill must not run the judge inline inside the same evaluation context.

## Inputs

- Exam config: `configs/exam_v1.json`
- Question files: `questions/<question_id>/question.md`
- Output schemas:
  - `schemas/exam_answer.schema.json`
  - `schemas/exam_summary.schema.json`
- Judge handoff reference:
  - `../custom-judge/README.md`
  - `../custom-judge/examples/`

## Workflow

1. Read the exam config file and use the ordered `question_ids` list exactly as written.
2. For each question ID:
   - Read `question.md`.
   - Ask the agent to produce an answer in the required format.
   - Write one answer artifact JSON to `artifacts/exam_answers/<run_id>__<question_id>.json`.
3. After all five answers are written, write a summary JSON to `artifacts/exam_runs/<run_id>__summary.json`.
4. Ensure artifacts conform to the schemas.
5. Stop after writing exam artifacts. Do not score them in-band.
6. Hand off to a separate judge orchestration step that:
   - builds a minimal `judge_input/` bundle for one answer artifact
   - calls `sessions_spawn`
   - targets agent ID `custom-judge-agent`
   - sets `sandbox: "require"`
   - passes only the `judge_input/` bundle through attachments

## Guardrails

- Do not randomize question selection.
- Do not score or evaluate answers.
- Do not merge judge instructions into this skill.
- Do not assume the judge can read arbitrary files from the main workspace.
- Do not treat the judge as part of the main agent's in-band context.
- Do not embed full question content in this skill file.
- Keep question/rubric/reference content editable in their own files.

## Artifacts

- Per-question answer artifact fields should match `exam_answer.schema.json`.
- Exam summary artifact fields should match `exam_summary.schema.json`.
- Judge input bundles are derived by a separate orchestration step from:
  - one answer artifact
  - the matching `question.md`
  - the matching `rubric.md`
  - optional `reference.md`
  - a small manifest containing scoring config and output expectations

See `README.md` in this skill directory for usage details.
