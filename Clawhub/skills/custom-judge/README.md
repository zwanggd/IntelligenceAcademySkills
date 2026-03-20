# custom-judge

`custom-judge` is a thin, isolated HTTP adapter for the exam-plus-judge loop.
It reads one attachment-delivered judge bundle, forwards it to an external judge API, validates the response, and writes stable local artifacts.

The recommended path is external HTTP evaluation.
Local in-skill scoring is not the default path.

## What It Does

- Prefers a minimal attachment bundle rooted at `judge_input/`.
- Reads `manifest.json`, `answer.json`, `question.md`, `rubric.md`, and optional `reference.md`.
- Validates the bundle locally before any network call.
- Sends one explicit HTTP POST request to the external judge service.
- Validates and normalizes the response shape.
- Writes JSON and markdown judge artifacts inside the dedicated judge workspace.
- Keeps the older `exam_package_path` file-resolution flow only as a secondary compatibility input mode.

## Recommended Runtime Flow

1. Main agent runs `custom-exam`.
2. `custom-exam` writes one answer artifact.
3. Orchestration prepares one minimal `judge_input/` bundle.
4. Orchestration spawns `custom-judge-agent`.
5. The child judge workspace receives the bundle as attachments.
6. `custom-judge` runs `python3 runner.py --workspace-root . --bundle-root judge_input`.
7. The adapter POSTs the bundle to the external judge API.
8. The adapter writes local JSON and markdown artifacts.

This keeps evaluation isolated from the main exam agent and preserves a stable judge boundary for future optimization loops.

## Bundle Contract

Use a minimal directory bundle:

```text
judge_input/
  manifest.json
  answer.json
  question.md
  rubric.md
  reference.md
```

`reference.md` is optional.

Expected file roles:

- `manifest.json`: run metadata, scoring weights, score-cap rules, and expected output paths
- `answer.json`: one `custom-exam` answer artifact
- `question.md`: question prompt for the matching `question_id`
- `rubric.md`: rubric text to send to the external evaluator
- `reference.md`: optional reference material for the same question

The manifest should include at least:

- `manifest_version`
- `judge_version`
- `exam_id`
- `run_id`
- `question_id`
- `dimension`
- `source_answer_artifact`
- `weights`
- `expected_output_paths`

See:

- `schemas/judge_input_manifest.schema.json`
- `schemas/exam_answer.schema.json`
- `examples/judge_input.manifest.example.json`
- `examples/judge_input.bundle-layout.md`

## Adapter Runtime

Primary command:

```bash
python3 runner.py --workspace-root . --bundle-root judge_input
```

What the adapter does:

1. Reads the bundle from `judge_input/`.
2. Validates required files exist.
3. Validates `manifest.json` and `answer.json`.
4. Cross-checks `exam_id`, `run_id`, and `question_id`.
5. Loads HTTP settings from local config plus environment variables.
6. Sends a POST request to the external judge API.
7. Validates and normalizes the response.
8. Writes local artifacts.
9. Writes local error artifacts on failure.

Legacy-compatible fallback input:

```bash
python3 runner.py \
  --workspace-root . \
  --exam-package-path /path/to/custom-exam \
  --run-id <run_id> \
  --question-id <question_id>
```

This fallback still uses the external HTTP judge API.
It only changes how input files are located.

## Judge Runtime Config

Keep external API configuration in the dedicated judge workspace, not in the attachment bundle.

Preferred local config path:

- `configs/judge_provider.local.json`

Tracked template:

- `configs/judge_provider.example.json`

Configuration precedence:

1. Explicit environment variables
2. `configs/judge_provider.local.json`
3. Safe built-in defaults for non-secret fields only

Supported environment variables:

- `JUDGE_API_BASE_URL`
- `JUDGE_API_PATH`
- `JUDGE_API_TIMEOUT_MS`
- `JUDGE_API_AUTH_HEADER`
- `JUDGE_API_TOKEN`
- `JUDGE_API_TOKEN_ENV_VAR`
- `JUDGE_API_RETRY_COUNT`
- `JUDGE_API_RETRY_BACKOFF_MS`
- `JUDGE_API_VERIFY_TLS`

Tracked config fields:

- `base_url`
- `path`
- `timeout_ms`
- `auth_header_name`
- `auth_token_env_var`
- `retry_count`
- `retry_backoff_ms`
- `verify_tls`

Recommended usage:

- Create `configs/judge_provider.local.json` inside the dedicated judge workspace.
- Copy the structure from `configs/judge_provider.example.json`.
- Put secrets in environment variables or the local untracked config file only.
- Do not place secrets in `judge_input/manifest.json` or any attached file.

## HTTP Request Contract

The adapter sends a single JSON request with this shape:

```json
{
  "judge_version": "v1",
  "request_id": "5a4b0df6-4f40-4ca6-a4a4-0eb2a61c5b08",
  "idempotency_key": "8b7f...",
  "source_skill": "custom-judge",
  "generated_at": "2026-03-20T00:00:00Z",
  "run_id": "run_2026_03_19_001",
  "question_id": "d1_reasoning_v1",
  "bundle_hash": "1d5a...",
  "bundle": {
    "manifest": {},
    "answer": {},
    "question_markdown": "...",
    "rubric_markdown": "...",
    "reference_markdown": "..."
  }
}
```

Notes:

- `reference_markdown` is omitted when `reference.md` is not present.
- `judge_version` is required and forwarded from the bundle manifest.
- `request_id` is generated per request.
- `idempotency_key` is derived from `judge_version`, `run_id`, `question_id`, and `bundle_hash`.
- `run_id`, `question_id`, and `bundle_hash` are sent as explicit top-level fields for tracing and dedupe.
- The client keeps the request shape explicit and minimal.

## HTTP Response Contract

The expected response shape is:

```json
{
  "question_id": "d1_reasoning_v1",
  "run_id": "run_2026_03_19_001",
  "judge_version": "v1",
  "hard_score": 3,
  "soft_score": 9,
  "total_score": 12,
  "hard_checks": [
    {
      "name": "Required output present",
      "passed": true,
      "score": 1,
      "max_score": 1,
      "note": "Found"
    }
  ],
  "soft_checks": [
    {
      "name": "Explanation quality",
      "score": 4,
      "max_score": 5,
      "note": "Mostly clear"
    }
  ],
  "failure_tags": [],
  "judge_summary": "Meets the minimum bar with some quality gaps.",
  "report_markdown": "# Judge Report\\n..."
}
```

Minimum required response fields:

- `question_id`
- `judge_version`
- `hard_score`
- `soft_score`
- `total_score`
- `hard_checks`
- `soft_checks`
- `failure_tags`
- `judge_summary`

Validation rules:

- `question_id` must match the request bundle.
- `judge_version` is required.
- `judge_version` must exactly match the request `judge_version`.
- `total_score`, `cap_applied`, and `failure_tags` are not recomputed locally.
- If required fields are missing, the adapter fails and writes an error artifact instead of filling them in locally.

If `report_markdown` is absent, the adapter generates a minimal markdown summary locally.

## Output Artifacts

Recommended artifact paths:

- `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.json`
- `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.md`

Notes:

- The adapter still respects explicit paths provided in `manifest.expected_output_paths` for compatibility.
- If it has to fall back to internally generated paths, it includes `judge_version` in the filename.

The JSON artifact is intended for machine consumption in future optimization loops.
The markdown artifact is intended for human review.

The JSON artifact contains at least:

- `exam_id`
- `run_id`
- `question_id`
- `judge_version`
- `status`
- `hard_score`
- `soft_score`
- `total_score`
- `hard_checks`
- `soft_checks`
- `failure_tags`
- `judge_summary`
- `trace`

The `trace` object includes:

- `request_id`
- `idempotency_key`
- `bundle_hash`
- `adapter_version`
- request timestamps

## Error Handling

On failure, the adapter writes local error artifacts instead of failing silently.

Handled failure cases include:

- missing bundle files
- invalid manifest content
- invalid answer content
- manifest and answer ID mismatch
- HTTP timeout
- non-200 HTTP response
- malformed JSON response
- response missing required fields

Error artifacts keep the normal result paths when possible and include:

- `status: "error"`
- zeroed scores
- `failure_tags` including `adapter_error`
- a readable `judge_summary`
- an `error` object with:
  - `code`
  - `stage`
  - `retryable`
  - `message`
  - optional `details`
- a `trace` object for request and adapter-level debugging

## Dedicated Judge Agent

Recommended default agent ID:

- `custom-judge-agent`

Runtime expectations:

- `custom-judge-agent` is a separate OpenClaw agent identity.
- It runs in its own workspace.
- `custom-judge` is installed in that judge workspace.
- External API config is also expected to live in that judge workspace.
- The main agent does not need read access to the judge workspace.
- The judge path should rely on attachments, not arbitrary reads from the main workspace.
- The recommended judge path requires outbound HTTP access.

## Edit Rubrics

Edit these files:

- `<exam_package_path>/questions/d1_reasoning_v1/rubric.md`
- `<exam_package_path>/questions/d2_retrieval_v1/rubric.md`
- `<exam_package_path>/questions/d3_creation_v1/rubric.md`
- `<exam_package_path>/questions/d4_execution_v1/rubric.md`
- `<exam_package_path>/questions/d5_orchestration_v1/rubric.md`

Optional reference material:

- `<exam_package_path>/questions/<question_id>/reference.md`

## Schema

- `schemas/judge_result.schema.json`
- `schemas/exam_answer.schema.json`
- `schemas/judge_input_manifest.schema.json`

## Packaging Readiness

- This folder is self-contained for manual packaging or upload.
- It ships its own adapter runtime, schemas, config template, and examples.
- It is intended to be installed in a dedicated judge workspace.
- The recommended runtime path does not depend on arbitrary access to the main exam workspace.
- External evaluation logic is expected to live outside OpenClaw.
- The OpenClaw-side responsibility of `custom-judge` is the HTTP adapter boundary.
