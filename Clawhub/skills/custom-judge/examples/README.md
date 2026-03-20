# Examples

These files are repo-level templates for wiring `custom-judge` into an isolated evaluation loop.

They are examples, not live machine config.
Adapt field names to the runtime that calls `sessions_spawn`.

## Files

- `judge-agent.example.json`
  - Example dedicated judge agent identity, isolated workspace expectations, and adapter entry command
- `../configs/judge_provider.example.json`
  - Template for judge-local external API settings
- `judge-spawn.example.json`
  - Example `sessions_spawn` payload using `agentId`, `model`, `sandbox`, and `attachments`
- `judge_input.manifest.example.json`
  - Example `judge_input/manifest.json` for one answer artifact
- `judge_input.bundle-layout.md`
  - Minimal attachment bundle tree for the isolated judge path

## Recommended Usage

1. Run `custom-exam` in the main workspace.
2. Build one `judge_input/` bundle for one answer artifact.
3. Create `configs/judge_provider.local.json` in the judge workspace from `../configs/judge_provider.example.json`.
4. Set `JUDGE_API_TOKEN` or the token env var referenced by the local config.
5. Spawn `custom-judge-agent` with `sandbox` required.
6. Pass only the bundle as attachments.
7. Run `python3 runner.py --workspace-root . --bundle-root judge_input` inside the child workspace.
8. Let `custom-judge` forward the bundle to the external judge API and write local artifacts.
