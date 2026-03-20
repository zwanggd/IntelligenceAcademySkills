---
name: custom-judge
description: Separate judge skill for scoring isolated custom-exam bundles with hard and soft checks.
user-invocable: true
---

# Custom Judge

## Purpose

Score one answer artifact from `custom-exam` using editable rubric rules.
The primary runtime path is an isolated judge run under a dedicated judge agent.

## Inputs

Primary input path:

- Attachment bundle path in the dedicated judge workspace:
  - `judge_input/manifest.json`
  - `judge_input/answer.json`
  - `judge_input/question.md`
  - `judge_input/rubric.md`
  - `judge_input/reference.md` when present
- Local schemas:
  - `schemas/judge_result.schema.json`
  - `schemas/judge_input_manifest.schema.json`
- Judge-local runtime config for external API access:
  - `configs/judge_provider.local.json`
  - template: `configs/judge_provider.example.json`

Legacy-compatible fallback path:

- `<exam_package_path>/artifacts/exam_answers/<run_id>__<question_id>.json`
- `<exam_package_path>/questions/<question_id>/question.md`
- `<exam_package_path>/questions/<question_id>/rubric.md`
- `<exam_package_path>/questions/<question_id>/reference.md`
- `<exam_package_path>/configs/exam_v1.json`

## Workflow

1. Prefer the attachment bundle path. Read `judge_input/manifest.json` first.
2. If external judge API access is needed, read `configs/judge_provider.local.json` from the judge workspace to resolve `base_url` and `api_key`.
3. Read `answer.json`, `question.md`, `rubric.md`, and optional `reference.md` from the same `judge_input/` directory.
4. Validate that `exam_id`, `run_id`, and `question_id` are consistent between the manifest and answer artifact.
5. Use scoring weights and cap rules from the manifest for the primary isolated path.
6. Run hard checks and soft checks from the rubric.
7. Apply score-cap logic when hard checks fall below the configured threshold.
8. Write outputs:
   - JSON result: `artifacts/judge_results/<run_id>__<question_id>.json`
   - Markdown summary: `artifacts/judge_results/<run_id>__<question_id>.md`
9. Ensure the JSON result conforms to the schema.
10. Use the legacy `exam_package_path` path only when the isolated bundle is unavailable.

## Guardrails

- Judge is separate from exam flow.
- Judge is intended to run under agent ID `custom-judge-agent`.
- Judge is intended to run inside its own workspace.
- Judge should prefer attachment-delivered inputs over shared-path reads.
- Judge should not assume arbitrary access to the main exam workspace.
- Recommended judge execution requires `sandbox: "require"`.
- External API secrets should live in judge-local config, not in the exam bundle.
- Judge never edits question text or rubrics.
- Keep scoring logic simple and config-driven.

See `README.md` in this skill directory for usage details.
