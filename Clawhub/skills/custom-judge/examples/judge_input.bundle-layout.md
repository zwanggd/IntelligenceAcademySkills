# judge_input Bundle Layout

Use a minimal attachment bundle with only the files needed to evaluate one answer through the external judge API:

```text
judge_input/
  manifest.json
  answer.json
  question.md
  rubric.md
  reference.md
```

Notes:

- `reference.md` is optional.
- `manifest.json` carries run metadata, scoring weights, score-cap rules, and expected output paths.
- `answer.json` is copied from `custom-exam` output for one `run_id` plus `question_id`.
- `question.md`, `rubric.md`, and optional `reference.md` are copied from the matching question folder.
- The recommended judge path attaches this directory to the child judge workspace and avoids arbitrary reads from the main workspace.
- The expected adapter command is `python3 runner.py --workspace-root . --bundle-root judge_input`.
- The adapter posts the bundle to the external judge API and writes:
  - `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.json`
  - `artifacts/judge_results/<run_id>__<question_id>__<judge_version>.md`
- The request includes `request_id`, `idempotency_key`, `run_id`, `question_id`, and `bundle_hash`.
