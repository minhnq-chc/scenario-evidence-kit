# Scenario Evidence Kit

A local-first driving-scenario workbench. Generate a bounded scenario, inspect its trajectory, review a revision, and collect evidence that says exactly what was checked.

**Current release: 0.1.0.** The offline workflow is usable without a GPU, API key or simulator. Real CARLA execution and live OpenAI generation are optional integrations and have not been exercised in this release's validation environment.

## What you can do

- Generate reproducible cut-in, lead-braking and pedestrian-crossing scenarios from English or Vietnamese keywords, or optionally request a structured plan from OpenAI.
- Inspect a 2D kinematic preview, edit JSON into a new revision, approve/reject with role checks, and export XML or evidence JSON/HTML.
- Organize projects and immutable, approved revision snapshots into suites. Run offline checks without accidentally claiming a simulator pass.
- Track runs, explicit failure states, input/export SHA-256, seeds, generator version and project activity.
- Keep local accounts with owner/author/reviewer roles. Data stays in SQLite; there are no default accounts or passwords.

## Quick start from source

Requires Python 3.11+ and Node.js 22.12+ or 24+ for building the web interface.

```bash
git clone https://github.com/minhnq-chc/scenario-evidence-kit.git
cd scenario-evidence-kit
python -m venv .venv
```

Activate the environment (`.venv\Scripts\Activate.ps1` on Windows PowerShell; `source .venv/bin/activate` on Linux/macOS), then:

```bash
python -m pip install -e ".[dev]"
cd frontend
npm ci
npm run build
cd ..
python scripts/build_web.py
sek serve
```

Open **http://127.0.0.1:8765**, create your owner account, then create a project. The service binds to loopback. It is a single-process personal workbench, not a multi-tenant public hosting service. Do not use multiple server workers against the same database.

The default database is `~/.scenario-evidence-kit/workbench.db`. Set `SEK_DATABASE` before startup to choose a separate database. Do not commit it. There is no account reset command; retain a secure backup if you need to preserve your workspace.

A prebuilt wheel from GitHub Releases contains the UI and does not require Node.js. Install that downloaded wheel with `python -m pip install /path/to/scenario_evidence_kit-0.1.0-py3-none-any.whl`, then run `sek serve`. The project is not currently published on PyPI.

## First complete workflow

1. Create a project and open **Generate**. Start with `A car cuts in ahead during rain` or `Người đi bộ băng qua đường lúc trời mưa`.
2. Choose a synthetic map, count and seed. The default engine is deterministic templates; it does not call a model.
3. Open **Case library**, inspect **Overview**, **Validation**, **JSON**, and **Review**. Editing creates a new draft revision.
4. Approve a revision as owner/reviewer. Open **Suites & runs**, select approved cases and create a suite.
5. Create an **offline** run. It records offline checks and simulation **NOT_RUN**, never a CARLA result.
6. Export evidence or XML. Reload the app: projects, revisions, suite snapshots and runs remain available.

Review is a workflow decision, not a safety certification. A previously created suite stays pinned to its original approved revision even after you edit the case.

## CLI

```bash
sek generate examples/generate-request.json -o variants.json
sek validate examples/pedestrian-fog.json
sek export examples/pedestrian-fog.json -o crossing.xosc
sek report examples/pedestrian-fog.json -o evidence.json
sek report examples/pedestrian-fog.json --html -o evidence.html
```

`generate` writes a JSON array. The other commands accept one scenario object. `-` reads standard input. A failing validation exits1; malformed/unsupported CLI input exits2. Files are bounded and XML declarations/entities are rejected on import.

## Exactly what validation means

| Layer | Current behavior |
|---|---|
| JSON/parameter checks | Finite bounded values, supported fields, actor references, durations and maneuver constraints |
| Kinematic preview | Illustrative straight-road motion at 5Hz; one ego and one challenger |
| XML export | An independently implemented OpenSCENARIO XML1.0 subset; no bundled ASAM schema |
| XML import | Only this writer's supported semantic tree; unknown/edited foreign features are rejected, never silently discarded |
| XSD validation | **NOT_RUN**; export is not a claim of full schema conformance |
| Map existence / lane topology | Not checked offline; Demo maps are synthetic |
| Simulator result | **NOT_RUN** unless the explicitly configured process adapter returns recognized evidence |
| ADS safety | Not established by any offline check or ordinary process exit code |

Do not use this tool to make road-vehicle safety decisions. See [supported scope](docs/SCOPE.md) for version boundaries and known limitations.

## Optional OpenAI planning

Install `python -m pip install ".[ai]"`, then configure environment variables before startup:

```text
SEK_ENABLE_OPENAI=1
OPENAI_API_KEY=<your own key, never commit it>
SEK_OPENAI_MODEL=<a model available to you that supports Responses structured output>
SEK_OPENAI_DAILY_CALLS=5
```

Select the OpenAI engine as owner. This sends the scenario description to OpenAI. It uses a bounded structured plan, rechecks the result locally, disables automatic retries and limits output to1200tokens. A persistent daily call counter uses UTC days and counts failed attempts too; this is a call cap, not a dollar budget. API keys are read from the server environment and never stored in SQLite. The model output snapshot is reproducible; model generation itself is **not seeded or guaranteed deterministic**. No paid request was made during release verification.

## Optional CARLA / ScenarioRunner

Use a separate, compatible CARLA/ScenarioRunner installation. This repository does not bundle simulator binaries, maps, vehicles or third-party schema assets.

Configure `SEK_SCENARIO_RUNNER` as the absolute path to your installed `scenario_runner.py`; `SEK_CARLA_PYTHON` can select that installation's Python executable. Configure real map names in `SEK_CARLA_MAPS` and verified spawn origins in `SEK_CARLA_MAP_ORIGINS`, for example the **shape** `{"Town01":[x,y,z,yaw_degrees]}` with your own measured values.

The adapter adds LogicFile, explicit vehicle/pedestrian blueprints and ego role, then translates relative trajectories to that origin. Override `SEK_CARLA_EGO`, `SEK_CARLA_VEHICLE`, `SEK_CARLA_PEDESTRIAN` for blueprints installed on your server. Host/port default to127.0.0.1:2000; timeout defaults120seconds. Synthetic Demo maps are rejected. Missing configuration, timeout, cancellation, nonzero exit or unrecognized verdict produces an error, never a pass.

**Integration status:** XML adapter and dispatch-state contracts are unit tested; an actual CARLA run is not verified. Supplied origins/blueprints must be checked against your own simulator. Runner process termination is best effort; inspect/reset the simulator after a cancellation or crash. The adapter is a local process integration, not a remote agent bridge.

## Development

```bash
python -m pytest -q
python -m ruff check src tests scripts
cd frontend
npm run typecheck
npm run build
```

For hot reload, run `sek serve` in one terminal and `npm run dev` from `frontend/` in another. The Vite proxy forwards API requests to8765. API schema: http://127.0.0.1:8765/openapi.json.

See [verification](docs/VERIFICATION.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md), and [dependency notices](THIRD_PARTY_NOTICES.md).

## License and maintenance

MIT ©2026 Ninh Quang Minh. Public dependencies keep their own licenses. OpenSCENARIO is an ASAM standard; CARLA and ScenarioRunner are separate projects. This workbench is not an official ASAM implementation or a certified ADAS validation tool.

Issues and reproducible examples are welcome. Please use synthetic data and include the tool version, input hash, expected behavior and the layer that failed.
