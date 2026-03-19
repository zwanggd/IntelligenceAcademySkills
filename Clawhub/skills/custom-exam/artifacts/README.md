# Artifacts

This folder stores generated outputs from the exam and judge flows.

## Output paths

- Exam answer artifacts:
  - `exam_answers/<run_id>__<question_id>.json`
- Exam summary artifacts:
  - `exam_runs/<run_id>__summary.json`
- Judge outputs:
  - `judge_results/<run_id>__<question_id>.json`
  - `judge_results/<run_id>__<question_id>.md`

## Notes

- Paths above are naming conventions used by skill instructions.
- Keep `run_id` stable across one full exam + judge cycle.
