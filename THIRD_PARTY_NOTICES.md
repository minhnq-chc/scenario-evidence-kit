# Third-party notices

The repository's own source, tests, documentation and synthetic examples are provided under MIT. It does not bundle simulator executables/maps, external datasets, proprietary schemas, photographs or brand assets.

Runtime/build dependencies are installed from their public package registries and retain their own licenses:

| Dependency | License |
|---|---|
| Python | PSF license |
| FastAPI, Pydantic | MIT |
| Uvicorn, Starlette | BSD-3-Clause |
| React, React DOM, Vite and its React plugin | MIT |
| TypeScript | Apache-2.0 |
| OpenAI Python SDK (optional) | Apache-2.0 |
| pytest, Ruff | MIT |
| HTTPX | BSD-3-Clause |

Transitive dependencies have their own licenses; inspect installed package metadata and the frontend lockfile before redistributing a bundled artifact. The packaging helper copies the bundled React/React DOM/Scheduler upstream notices into `assets/THIRD_PARTY_LICENSES.txt` in the prebuilt UI. Dependency manifests/lockfiles record selected packages; this list is not a replacement for upstream notices.

ASAM OpenSCENARIO is a standard and CARLA/ScenarioRunner are separate software projects. Their names describe interoperability targets and do not imply endorsement. No code from those repositories is vendored here.
