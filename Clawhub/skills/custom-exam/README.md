# custom-exam

`custom-exam` runs a fixed, config-driven 5-question exam and writes answer artifacts.

## What It Does

- Reads `configs/exam_v1.json`.
- Iterates a fixed ordered list of 5 question IDs.
- Loads question content from `questions/<question_id>/question.md`.
- Writes one answer JSON per question.
- Writes one exam summary JSON for the run.
- Does not judge or score answers.

## Edit Questions

Edit these files:

- `questions/d1_reasoning_v1/question.md`
- `questions/d2_retrieval_v1/question.md`
- `questions/d3_creation_v1/question.md`
- `questions/d4_execution_v1/question.md`
- `questions/d5_orchestration_v1/question.md`

## Run Exam Flow

Ask the agent to run `custom-exam` using `configs/exam_v1.json`.

Expected outputs:

- `artifacts/exam_answers/<run_id>__<question_id>.json`
- `artifacts/exam_runs/<run_id>__summary.json`

## Schemas

- `schemas/exam_answer.schema.json`
- `schemas/exam_summary.schema.json`

## Packaging Readiness

- This folder is self-contained and portable for manual packaging/upload.
- All required runtime files live inside this directory (`configs/`, `questions/`, `schemas/`, `artifacts/`).
- No runtime path in this skill needs `evals/custom-exam/...`.

## Edit First

1. `configs/exam_v1.json` for scoring weights and cap rules
2. `questions/*/question.md` for exam prompts
3. `questions/*/rubric.md` and `questions/*/reference.md` for judge criteria/context
