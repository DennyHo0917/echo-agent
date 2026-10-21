# Server review and remediation

This page records the server review of 2026-10-21, the resulting behavior, and reproducible checks. It covers the current source and packages built from that source. External integrations still require their own live qualification.

## Resulting behavior

| Scenario | Observable behavior |
| --- | --- |
| Save configuration | Merge and validate editable leaves, then save atomically. The current Runtime keeps its values; pending restart settings survive page refresh. |
| Environment/startup managed setting | Preserve startup precedence and lock the setting in the UI. API edits return `409/config_managed` instead of saving an ineffective value. |
| Invalid saved configuration | Starting or restarting a channel requires repair; an existing channel can still be stopped immediately. |
| Retry after step timeout | Previous attempt outcomes and questions cannot modify the new attempt. A question and BLOCKED status are saved in one CAS operation. |
| Persistence failure before scheduler dispatch | Publish no work, release execution capacity and record failure. An unfired one-shot remains retryable. |
| Isolated multi-provider evaluation | Reuse available model clients with independent routing/fallback health, sessions, files and SQLite databases. |
| Typed approval/clarification commands | Display success, permission, usage and expired-request feedback without settling the active business turn. |
| Failed/cooling-down summary | Preserve original history without repeated archive copies. Archive only after obtaining a usable replacement. |

Stopping a channel affects the current process. Service startup still follows saved settings, environment variables and startup arguments. To permanently disable a startup-managed channel, change its service environment or arguments.

## Reproducible checks

After installing development dependencies, run:

```bash
python -m pytest tests/ -q
ruff check . --extend-exclude client
pnpm --dir web test --run
pnpm --dir web build
mkdocs build --strict
```

Regression coverage lives in `tests/test_review_remediation.py`, `tests/test_gateway_review_regressions.py`, `tests/test_server_state_regressions.py`, `tests/test_scheduler_run_identity.py`, `tests/test_evaluation_runtime_isolation.py`, `tests/test_compression.py` and `tests/cli/tui/test_typed_control_integrity.py`. Frontend tests cover managed settings, immediate channel stopping and saved configuration feedback.

Run `scripts/validate-server-process.py --output /tmp/echo-process-check` using the installed release wheel's interpreter to check HTTP/WS, controlled model/tool calls, artifact delivery, duplicate requests, restart, port conflicts and SIGTERM in disposable workspaces. It uses a local controlled OpenAI-compatible endpoint, not a real external model.

`scripts/validate-gateway-web.mjs` checks authenticated playground HTTP/WS and Dashboard configuration saving. Install Playwright separately and supply a test Gateway address/token as described in the script. Do not run acceptance scripts against a production workspace.

## Verification results (2026-10-21)

| Check | Result |
| --- | --- |
| Full backend suite | 7,638 passed, 100 skipped |
| Final startup-argument and Gateway regressions | 147 passed; overlaps with the full suite, not an additional total |
| Frontend suite | 235 passed |
| TypeScript, production frontend build and bundle budget | Passed |
| Ruff, Git diff formatting and strict documentation build | Passed |
| Final wheel installation and process acceptance | Three scenario groups passed against a controlled local model endpoint |
| Browser acceptance | Login, HTTP/WS, configuration saving, unchanged running values and pending-restart state after refresh passed |

Local process and browser checks used separate temporary workspaces. Real external models, IM accounts and other operating systems were not exercised during this acceptance run. Skipped tests are excluded from the pass count.

## Compatibility and limits

- Gemini uses `google-genai>=2.32,<3`. Local real-SDK contract tests cover serialization, tool responses and stream closure; they are not live Google API qualification.
- Implemented MCP versions and the inbound A2A subset are listed in [compatibility](../reference/compatibility.md). Unimplemented revisions carry no conformance claim.
- FastEmbed source, license and patches are documented in the repository's `echo_agent/_vendor/fastembed/VENDOR.md`. PyMuPDF is currently restricted to `<2`; `pyproject.toml` defines actual dependencies.
- Isolated evaluation permits confined file operations and skill metadata reads. External/process tools and unreproduced required runtime extensions make measurements inconclusive, not promotion evidence.
- Timeouts, interruption and rollback do not undo committed external effects. Inspect results before re-executing, and enable automatic retries only for safely repeatable steps.
- Local qualification runs on macOS. Linux wheel-process qualification belongs to CI; a Linux host or Docker image must not be described as tested without actual results.

Back up configuration, databases, skills, scheduler state and credential keys before upgrading. Keep code, dependencies and restored backups consistent when rolling back; follow [upgrade and migrations](../operations/upgrade-migrations.md). Readiness checks local prerequisites only; verify actual model availability with a real tool task.
