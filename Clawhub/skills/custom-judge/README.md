# custom-judge

`custom-judge` scores one answer artifact from `custom-exam` and writes structured judge outputs.

## What It Does

- Reads one answer artifact from `<exam_package_path>/artifacts/exam_answers/` using `<run_id>__<question_id>.json`.
- Loads matching question and rubric files from `<exam_package_path>/questions/`.
- Optionally uses `reference.md` when present.
- Runs hard checks and soft checks.
- Applies score capping logic from `<exam_package_path>/configs/exam_v1.json`.
- Writes JSON and markdown judge outputs.

## Runtime Input

Provide the path to an unpacked `custom-exam` package as `exam_package_path`.

## Edit Rubrics

Edit these files:

- `<exam_package_path>/questions/d1_reasoning_v1/rubric.md`
- `<exam_package_path>/questions/d2_retrieval_v1/rubric.md`
- `<exam_package_path>/questions/d3_creation_v1/rubric.md`
- `<exam_package_path>/questions/d4_execution_v1/rubric.md`
- `<exam_package_path>/questions/d5_orchestration_v1/rubric.md`

Optional reference material:

- `<exam_package_path>/questions/<question_id>/reference.md`

## Run Judge Flow

Ask the agent to run `custom-judge` for one answer artifact.

Expected outputs:

- `artifacts/judge_results/<run_id>__<question_id>.json`
- `artifacts/judge_results/<run_id>__<question_id>.md`

## Schema

- `schemas/judge_result.schema.json`
- `schemas/exam_answer.schema.json`

## Packaging Readiness

- This folder is self-contained for manual packaging/upload.
- It ships its own schemas and output artifact location.
- It does not depend on `evals/custom-exam/...` at runtime.
- Judge reads question/rubric/reference/config from the provided `exam_package_path`.
