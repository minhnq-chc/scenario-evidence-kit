# Application contract

Version 0.1.0. Local-first scenario workbench, Python FastAPI + SQLite and React/Vite. Offline deterministic generation is the default. Simulator runs are optional and must never be fabricated.

## Scenario JSON

```json
{"id":"case-generated-id","title":"Rainy cut-in","description":"A vehicle cuts in ahead","map_name":"DemoStraight","kind":"cut_in","seed":42,"duration_s":12,"weather":"rain","ego_speed_mps":12,"actors":[{"id":"challenger","kind":"car","speed_mps":9,"start_x_m":18,"start_y_m":3.5}],"parameters":{"trigger_s":3,"lane_width_m":3.5}}
```

Kinds: cut_in, lead_brake, pedestrian_crossing. Weather: clear, rain, fog, night. Actor kinds: car, motorcycle, pedestrian. Offline maps DemoStraight and DemoIntersection are synthetic, not CARLA towns. Actual CARLA map names are supplied by its own catalog.

## Core Python interface (module `scenario_evidence.core`)

- `generate(description: str, count: int = 3, seed: int = 42, map_name: str = 'DemoStraight', kind: str | None = None) -> list[dict]`: reproducible bounded template generation; supports Vietnamese and English keywords, does not pretend to be an LLM.
- `validate(scenario: dict) -> dict`: `{status:'PASS'|'FAIL'|'UNSUPPORTED', checks:[{name,status,message}], fingerprint:str}`. PASS is an offline subset check, not XSD conformance, map existence or ADS safety. Validate nonfinite numbers, ranges, actor refs, input size/types.
- `fingerprint(scenario: dict) -> str`: canonical SHA256.
- `export_xosc(scenario: dict) -> str`: documented OpenSCENARIO XML 1.0 subset, self-created exporter, no bundled proprietary schemas. No guarantee arbitrary map compatibility.
- `import_xosc(xml: str) -> dict`: import the supported export subset; reject DTD/entity declarations, oversized and unsupported input. Do not silently discard unknown features.
- `preview(scenario: dict) -> list[dict]`: deterministic kinematic samples `{t,ego_x,ego_y,actor_x,actor_y}`; illustrative 2D, not a CARLA result.
- `build_report(scenario: dict, execution: dict | None = None) -> dict`: input_hash, seed, generator_version, checks and simulation verdict; simulation NOT_RUN when absent. Include export digest, no claim schema validation ran.

CLI executable `sek`: generate, validate, export, report, serve. JSON input, no untrusted code execution. Core owner creates core modules, CLI, examples and core tests only.

## API (`/api`), API owner may add independent auth endpoints

All workbench endpoints use a local bearer token, supplied via Authorization header. GET /health is public. Initial bootstrap POST /api/auth/bootstrap accepts `{name,password}` only on an empty database, returns `{token,user:{id,name,role:'owner'}}`. POST /api/auth/login accepts `{name,password}`. No default account/password. CLI `sek serve` binds loopback by default.

- GET /auth/me -> user; POST /auth/users {name,password,role:'author'|'reviewer'} owner only.
- GET /catalog -> `{maps:[{name,synthetic:true}],kinds:string[],weather:string[]}`.
- GET /projects -> array; POST /projects {name} -> project `{id,name,created_at}`.
- GET /cases?project_id= -> array of latest case revisions.
- POST /generate {project_id,description,count,seed,map_name,kind?} -> array of newly persisted cases.
- POST /cases/import {project_id,xml} -> new case.
- GET /cases/{id} -> latest case, includes scenario and validation.
- POST /cases/{id}/revisions {scenario} -> new draft revision. Never mutate a previous revision.
- POST /cases/{id}/review {decision:'approved'|'rejected',note:string} -> reviewed latest revision; owner/reviewer only; every decision stored in audit.
- GET /cases/{id}/xosc -> text XML; GET /cases/{id}/report -> evidence JSON; GET /cases/{id}/preview -> sample array.
- GET /suites?project_id= -> array; POST /suites {project_id,name,case_ids:string[]} -> snapshots APPROVED case revisions only.
- GET /runs?project_id= -> array; POST /runs {suite_id,mode:'offline'|'carla',idempotency_key:string} -> run. Offline finishes immediately and reports simulation NOT_RUN; CARLA dispatch only through explicitly configured executable, otherwise ERROR with clear message. Repeated keys return same run, mismatched payload 409.
- POST /runs/{id}/cancel -> cancel running or queued run; completed runs are unchanged.
- GET /runs/{id} -> run including results array with per-case reports and simulation statuses.
- GET /metrics?project_id= -> `{cases,approved,rejected,suites,runs,offline_pass,simulation_pass,simulation_not_run}`.
- GET /audit?project_id= -> bounded recent array of actions, no credentials.

Case object `{id,project_id,revision,title,status:'draft'|'approved'|'rejected',scenario,validation,created_at}`.
Suite `{id,project_id,name,items:[{case_id,revision,fingerprint}],created_at}`.
Run `{id,project_id,suite_id,mode,status:'completed'|'running'|'queued'|'error'|'cancelled',created_at,results:[{case_id,revision,report}],error?:string}`.

## UI acceptance

Accessible login/bootstrap, project selector and creation, generate form, case library with detail/2D preview/validation/revision/review/XOSC/evidence downloads, suite creation from approved cases, runs and metrics. Clear synthetic/offline badges, empty/loading/error states, responsive keyboard-friendly controls. No fake traction, partnerships or simulator results.

## Source policy

All source/examples/tests/docs are new for this repository. Public dependencies retain their licenses. No third-party images, brand assets, private data or inherited repository history. Standard and simulator compatibility are explicit subsets, not certification.
