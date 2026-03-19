---
name: custom-exam
description: Fixed 5-dimension exam skill for agent evaluation.
user-invocable: true
---

# Custom Exam

## Purpose

Run a fixed exam from editable files inside this folder and write machine-readable answer artifacts.

This skill must not judge or score answers.

## Inputs

- Exam config: `configs/exam_v1.json`
- Question files: `questions/<question_id>/question.md`
- Output schemas:
  - `schemas/exam_answer.schema.json`
  - `schemas/exam_summary.schema.json`

## Workflow

1. Read the exam config file and use the ordered `question_ids` list exactly as written.
2. For each question ID:
   - Read `question.md`.
   - Ask the agent to produce an answer in the required format.
   - Write one answer artifact JSON to `artifacts/exam_answers/<run_id>__<question_id>.json`.
3. After all five answers are written, write a summary JSON to `artifacts/exam_runs/<run_id>__summary.json`.
4. Ensure artifacts conform to the schemas.

## Guardrails

- Do not randomize question selection.
- Do not score or evaluate answers.
- Do not embed full question content in this skill file.
- Keep question/rubric/reference content editable in their own files.

## Artifacts

- Per-question answer artifact fields should match `exam_answer.schema.json`.
- Exam summary artifact fields should match `exam_summary.schema.json`.

See `README.md` in this skill directory for usage details.
