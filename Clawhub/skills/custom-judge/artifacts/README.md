# Artifacts

This folder stores outputs from `custom-judge`.
These outputs are intended to be produced inside the dedicated judge workspace.

## Output paths

- Judge JSON result:
  - `judge_results/<run_id>__<question_id>__<judge_version>.json`
- Judge markdown summary:
  - `judge_results/<run_id>__<question_id>__<judge_version>.md`

## Notes

- Keep the same `run_id` used by the corresponding exam run.
- In the recommended isolated path, outputs are written by `custom-judge-agent` after reading the attached `judge_input/` bundle and posting it to the external judge API.
- On success, the JSON artifact contains the normalized judge result fields returned by the external API.
- Success artifacts include a `trace` block with `request_id`, `idempotency_key`, `bundle_hash`, adapter version, and timestamps.
- On failure, `custom-judge` still writes JSON and markdown artifacts at the expected paths when possible.
- Error artifacts use `status: "error"`, zero scores, `failure_tags` that include `adapter_error`, and a structured `error` object with `code`, `stage`, `retryable`, and `message`.
- If the main workflow needs these results, export or collect them explicitly after the child judge run completes.
