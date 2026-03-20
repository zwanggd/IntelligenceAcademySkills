# Examples

These files are repo-level templates for wiring `custom-judge` into an isolated evaluation loop.

They are examples, not live machine config.
Adapt field names to the runtime that calls `sessions_spawn`.

## Files

- `judge-agent.example.json`
  - Example dedicated judge agent identity and isolated workspace expectations
- `../configs/judge_provider.example.json`
  - Template for judge-local external API `base_url` and `api_key`
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
4. Spawn `custom-judge-agent` with `sandbox` required.
5. Pass only the bundle as attachments.
6. Let `custom-judge` score inside the child workspace.
