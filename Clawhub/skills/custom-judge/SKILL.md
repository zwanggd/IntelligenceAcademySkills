---
name: custom-judge
description: Separate judge skill that forwards isolated custom-exam bundles to an external HTTP judge API and writes local artifacts.
user-invocable: true
---

# Custom Judge

## Purpose

Act as a thin HTTP adapter for one isolated `custom-exam` answer bundle.
The primary runtime path is an isolated judge run under a dedicated judge agent.

## Inputs

Primary input path:

- Attachment bundle path in the dedicated judge workspace:
  - `judge_input/manifest.json`
  - `judge_input/answer.json`
  - `judge_input/question.md`
  - `judge_input/rubric.md`
  - `judge_input/reference.md` when present
- Local adapter runtime:
  - `runner.py`
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
2. Run the local adapter:
   - `python3 runner.py --workspace-root . --bundle-root judge_input`
3. Let the adapter read `configs/judge_provider.local.json` plus environment variables to resolve:
   - `JUDGE_API_BASE_URL`
   - `JUDGE_API_PATH`
   - `JUDGE_API_TIMEOUT_MS`
   - `JUDGE_API_AUTH_HEADER`
   - `JUDGE_API_TOKEN`
   - `JUDGE_API_TOKEN_ENV_VAR`
   - `JUDGE_API_RETRY_COUNT`
   - `JUDGE_API_RETRY_BACKOFF_MS`
   - `JUDGE_API_VERIFY_TLS`
4. Let the adapter read `answer.json`, `question.md`, `rubric.md`, and optional `reference.md` from the same `judge_input/` directory.
5. Let the adapter validate that `exam_id`, `run_id`, and `question_id` are consistent between the manifest and answer artifact.
6. Let the adapter compute and send:
   - required `judge_version`
   - `request_id`
   - `idempotency_key`
   - `run_id`
   - `question_id`
   - `bundle_hash`
7. Let the adapter POST the bundle to the external judge API.
8. Let the adapter validate and normalize the response.
   - require response `judge_version`
   - require response `judge_version == request judge_version`
   - do not locally recompute `total_score`, `cap_applied`, or `failure_tags`
8. Let the adapter write outputs:
   - JSON result: `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.json`
   - Markdown summary: `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.md`
9. Persist a trace block in the result artifact with request identifiers, bundle hash, adapter version, and timestamps.
10. If the API response includes `report_markdown`, use it for the markdown artifact. Otherwise generate a minimal local report.
11. If the adapter fails, write a stable error artifact and markdown note instead of failing silently.
12. Use the legacy `exam_package_path` input path only when the isolated bundle is unavailable.

## Guardrails

- Judge is separate from exam flow.
- Judge is intended to run under agent ID `custom-judge-agent`.
- Judge is intended to run inside its own workspace.
- Judge should prefer attachment-delivered inputs over shared-path reads.
- Judge should not assume arbitrary access to the main exam workspace.
- Recommended judge execution requires `sandbox: "require"`.
- External API secrets should live in judge-local config, not in the exam bundle.
- The primary path is external HTTP evaluation, not local rubric-only scoring.
- Do not reintroduce self-scoring inside the main agent flow.
- Keep outbound HTTP behavior explicit and attachment-first.
- Treat the external response as the scoring source of truth.
- Judge never edits question text or rubrics.
- Keep the adapter small, explicit, and loop-friendly.

See `README.md` in this skill directory for usage details.
