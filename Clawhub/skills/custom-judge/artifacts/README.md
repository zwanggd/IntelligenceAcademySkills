# Artifacts

This folder stores outputs from `custom-judge`.
These outputs are intended to be produced inside the dedicated judge workspace.

## Output paths

- Judge JSON result:
  - `judge_results/<run_id>__<question_id>.json`
- Judge markdown summary:
  - `judge_results/<run_id>__<question_id>.md`

## Notes

- Keep the same `run_id` used by the corresponding exam run.
- In the recommended isolated path, outputs are written by `custom-judge-agent` after reading the attached `judge_input/` bundle.
- If the main workflow needs these results, export or collect them explicitly after the child judge run completes.
