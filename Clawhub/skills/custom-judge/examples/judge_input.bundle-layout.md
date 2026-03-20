# judge_input Bundle Layout

Use a minimal attachment bundle with only the files needed to score one answer:

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
