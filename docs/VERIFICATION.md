# Verification — 0.1.0

Executed 2026-10-22 on Windows, Python3.13. Local checks are distinct from the GitHub CI status.

| Check | Result |
|---|---|
| Python tests | 69passed; one upstream AnyIO/Starlette deprecation warning |
| Ruff | All checks passed |
| Frontend TypeScript | Passed |
| Vite production build | Passed;38modules, JS259.33kB /80.02kB gzip at final build |
| npm install audit | 0reported vulnerabilities at install; not a security guarantee |
| Wheel | Builds successfully; contains web UI, own MIT license and bundled dependency notices |
| Clean virtual environment | Wheel installed and CLI scenario validation passed |
| Source publication audit | Fresh Git history; no private source markers, database, credentials or development artifacts in staged source set |

## Browser evidence

The built application was exercised in an in-app browser against an isolated SQLite test database:

1. Create a local fixture owner and a project.
2. Generate3pedestrian-crossing variants from a Vietnamese description.
3. Review and approve revision1; create an approved suite and an offline run.
4. Inspect the recorded run: offline completed; simulation and XSD both NOT_RUN.
5. Edit JSON, download evidence, return to JSON: unsaved title preserved.
6. Save revision2, reload application and confirm it persists.
7. Approve with keyboard: focus lands on the success status and reviewed decision buttons become disabled.
8. Console error/warning log inspection returned an empty array for that browser session.

Screenshots and the test database are retained outside the committed source/release. The fixture account is not a default application credential.

## Independent review and corrections

- API review: Host/origin bootstrap boundary fixed and regression tested; cancellation before worker claim fixed and regression tested; explicit CARLA XML map/blueprint/origin translation added and contract tested.
- React review: download-induced draft loss and stale generation navigation fixed, source-rechecked. Download preservation was also verified in the browser.
- Accessibility review: hidden mobile navigation made non-focusable in CSS; menu Escape/focus handoff implemented; post-action focus explicitly moved to status and verified on desktop.

## Not established

No real CARLA run, live OpenAI request, full OpenSCENARIO XSD conformance, arbitrary external XML import, safety certification, external users or broad OS/version compatibility was demonstrated. Provider tests use mocks; adapter tests use fixtures. Mobile rendered/keyboard behavior and screen-reader output remain unverified because the available browser surface did not expose viewport resizing. Responsive source was reviewed; no mobile pass is claimed.

The public CI workflow covers Windows/Linux and Python3.11/3.13 plus web build. Its actual result must be checked on GitHub after publication; the existence of a workflow file alone is not a passed build.
