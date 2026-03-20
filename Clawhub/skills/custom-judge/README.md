# custom-judge

`custom-judge` scores one answer artifact from `custom-exam` and writes structured judge outputs.
It is intended to be the isolated evaluator in a continuous optimization loop.

## What It Does

- Prefers a minimal attachment bundle rooted at `judge_input/`.
- Reads `answer.json`, `question.md`, `rubric.md`, and optional `reference.md` from that bundle.
- Reads scoring weights, cap rules, output expectations, and run metadata from `judge_input/manifest.json`.
- Runs hard checks and soft checks.
- Applies score capping logic from the manifest on the isolated path.
- Writes JSON and markdown judge outputs inside the dedicated judge workspace.
- Keeps the older `exam_package_path` flow only as a secondary compatibility path.

## Judge Runtime Config

If the judge run needs to call an external API, keep that configuration in the judge workspace, not in the exam bundle.

Preferred local config path:

- `configs/judge_provider.local.json`

Tracked template:

- `configs/judge_provider.example.json`

Expected fields:

- `base_url`
- `api_key`
- `model` when you want a judge-specific model override
- `timeout_ms`

Recommended usage:

- Create `configs/judge_provider.local.json` inside the dedicated judge workspace.
- Copy the structure from `configs/judge_provider.example.json`.
- Put the real external API address and key only in the local file.
- Do not place secrets in `judge_input/manifest.json` or other attachments.

## Runtime Input

Recommended input:

- An attached `judge_input/` bundle delivered into the judge workspace

Recommended bundle contents:

- `judge_input/manifest.json`
- `judge_input/answer.json`
- `judge_input/question.md`
- `judge_input/rubric.md`
- `judge_input/reference.md` when present

Secondary compatibility input:

- An unpacked `custom-exam` package provided as `exam_package_path`

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
- This is the intended place to configure a different judge model later.

## Recommended Isolated Flow

1. Main agent runs `custom-exam`.
2. `custom-exam` writes one answer artifact.
3. A judge orchestration step creates a minimal `judge_input/` bundle for that answer.
4. The orchestration step calls `sessions_spawn`.
5. `sessions_spawn` targets `custom-judge-agent`.
6. `sessions_spawn` sets `sandbox: "require"`.
7. The bundle is passed as attachments.
8. The judge run reads only the attachment bundle plus its own local skill files and local judge runtime config.
9. `custom-judge` writes structured outputs.

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

The manifest should include at least:

- `exam_id`
- `run_id`
- `question_id`
- `dimension`
- `source_answer_artifact`
- `expected_output_paths`
- `judge_version`
- scoring weights for the isolated path
- score-cap rules for the isolated path

See:

- `configs/judge_provider.example.json`
- `schemas/judge_input_manifest.schema.json`
- `examples/judge_input.manifest.example.json`
- `examples/judge-spawn.example.json`
- `examples/judge-agent.example.json`
- `examples/README.md`

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

Recommended isolated path:

- Spawn a dedicated judge run with `custom-judge-agent`
- Require sandboxing
- Pass only the `judge_input/` bundle as attachments
- Let the judge read `base_url` and `api_key` from `configs/judge_provider.local.json` in its own workspace
- Write judge outputs inside the child workspace

Legacy-compatible path:

- If needed, provide `exam_package_path` and let `custom-judge` resolve answer/question/rubric/reference/config from there
- Prefer the attachment path whenever possible

## Schema

- `schemas/judge_result.schema.json`
- `schemas/exam_answer.schema.json`
- `schemas/judge_input_manifest.schema.json`

## Packaging Readiness

- This folder is self-contained for manual packaging/upload.
- It ships its own schemas and output artifact location.
- It is intended to be installed in a dedicated judge workspace.
- The recommended runtime path does not depend on arbitrary access to the main exam workspace.
- External API credentials are intended to be supplied through judge-local config, not through shared workspace reads or attachments.
- Legacy compatibility can still read question/rubric/reference/config from a provided `exam_package_path`.
