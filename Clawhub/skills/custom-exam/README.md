# custom-exam

`custom-exam` runs a fixed, config-driven 5-question exam and writes answer artifacts.
It is the answer-producing side of a two-skill exam-plus-judge system.

## What It Does

- Reads `configs/exam_v1.json`.
- Iterates a fixed ordered list of 5 question IDs.
- Loads question content from `questions/<question_id>/question.md`.
- Writes one answer JSON per question.
- Writes one exam summary JSON for the run.
- Does not judge or score answers.
- Ends before evaluation. Judge execution happens later in a separate run.

## Recommended Runtime Boundary

- Main agent runs `custom-exam` in the main workspace.
- `custom-exam` writes answer artifacts under `artifacts/exam_answers/`.
- A separate orchestration step prepares one minimal `judge_input/` bundle per answer.
- The orchestration step calls `sessions_spawn`.
- `sessions_spawn` targets agent ID `custom-judge-agent`.
- The recommended judge path sets `sandbox: "require"`.
- The judge run receives only the `judge_input/` bundle through attachments.
- `custom-judge` runs inside the dedicated judge workspace and scores from that bundle.

This keeps scoring out of the main exam context and makes the judge path usable as a stable evaluation boundary for optimization loops.

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

Recommended next step after the exam run:

1. Build `artifacts/judge_inputs/<run_id>__<question_id>/judge_input/`
2. Include:
   - `manifest.json`
   - `answer.json`
   - `question.md`
   - `rubric.md`
   - `reference.md` when present
   - copy the matching scoring weights and cap rules from `configs/exam_v1.json` into `manifest.json`
3. Spawn a dedicated judge run using `custom-judge-agent`
4. Require sandboxing and pass only that bundle as attachments
5. Let `custom-judge` write its own structured outputs in the child workspace

See `../custom-judge/README.md` and `../custom-judge/examples/` for the isolated judge contract and example spawn payloads.

## Schemas

- `schemas/exam_answer.schema.json`
- `schemas/exam_summary.schema.json`

## Packaging Readiness

- This folder is self-contained and portable for manual packaging/upload.
- All required runtime files live inside this directory (`configs/`, `questions/`, `schemas/`, `artifacts/`).
- No runtime path in this skill needs `evals/custom-exam/...`.
- Judge execution is intentionally out-of-band and is not merged into this skill.

## Edit First

1. `configs/exam_v1.json` for scoring weights and cap rules
2. `questions/*/question.md` for exam prompts
3. `questions/*/rubric.md` and `questions/*/reference.md` for judge criteria/context

## Isolation Notes

- `custom-exam` and `custom-judge` remain separate skills.
- The main agent should not need direct read access to the judge workspace.
- The judge agent should not rely on arbitrary reads from the main workspace.
- The dedicated judge agent is the intended place to configure a different model later.
