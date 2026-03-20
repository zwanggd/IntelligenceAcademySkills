# Artifacts

This folder stores generated outputs from the exam flow and any optional local staging files created before an isolated judge handoff.

## Output paths

- Exam answer artifacts:
  - `exam_answers/<run_id>__<question_id>.json`
- Exam summary artifacts:
  - `exam_runs/<run_id>__summary.json`
- Recommended local staging bundle before `sessions_spawn`:
  - `judge_inputs/<run_id>__<question_id>/judge_input/manifest.json`
  - `judge_inputs/<run_id>__<question_id>/judge_input/answer.json`
  - `judge_inputs/<run_id>__<question_id>/judge_input/question.md`
  - `judge_inputs/<run_id>__<question_id>/judge_input/rubric.md`
  - `judge_inputs/<run_id>__<question_id>/judge_input/reference.md` when present

## Notes

- Paths above are naming conventions used by skill instructions.
- Keep `run_id` stable across one full exam + judge cycle.
- The `judge_input/` bundle should contain only the minimum files required for scoring.
- The bundle manifest should copy only the per-question weights and score-cap settings needed for isolated judging.
- Recommended judge outputs are written by the dedicated judge agent inside its own workspace, not by the main exam run.
