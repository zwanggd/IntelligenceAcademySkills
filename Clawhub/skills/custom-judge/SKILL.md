---
name: custom-judge
description: Separate judge skill for scoring custom-exam outputs with hard and soft checks.
user-invocable: true
---

# Custom Judge

## Purpose

Score one answer artifact from `custom-exam` using editable rubric rules.

## Inputs

- Answer artifact path (input):
  - `<exam_package_path>/artifacts/exam_answers/<run_id>__<question_id>.json`
- Matching question file (resolved from input `exam_package_path`):
  - `<exam_package_path>/questions/<question_id>/question.md`
- Matching rubric file:
  - `<exam_package_path>/questions/<question_id>/rubric.md`
- Optional reference file:
  - `<exam_package_path>/questions/<question_id>/reference.md`
- Exam config (weights and scoring caps):
  - `<exam_package_path>/configs/exam_v1.json`
- Output schema:
  - `schemas/judge_result.schema.json`

## Workflow

1. Read the answer artifact and extract `question_id`.
2. Load matching `question.md`, `rubric.md`, and optional `reference.md`.
3. Run hard checks and soft checks from the rubric.
4. Apply cap logic from exam config when hard checks fail.
5. Write outputs:
   - JSON result: `artifacts/judge_results/<run_id>__<question_id>.json`
   - Markdown summary: `artifacts/judge_results/<run_id>__<question_id>.md`
6. Ensure JSON result conforms to the schema.

## Guardrails

- Judge is separate from exam flow.
- Judge never edits question text or rubrics.
- Keep scoring logic simple and config-driven.

See `README.md` in this skill directory for usage details.
