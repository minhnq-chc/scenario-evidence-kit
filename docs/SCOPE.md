# Release scope and feature status

## Implemented

English/Vietnamese keyword templates, optional structured model planning, parameter checks, deterministic scenario snapshots and preview, supported XML roundtrip, JSON/HTML evidence, local auth/roles, projects, immutable revisions, review, revision-pinned suites, idempotent runs, metrics and activity. SQLite persists the workflow. Browser UI and CLI share the core.

## Deliberate boundaries

- Three maneuver families; exactly one challenger. Multi-actor scenes, intersections with real lane graphs and arbitrary OpenSCENARIO imports are unsupported.
- Synthetic DemoStraight/DemoIntersection share a straight-road coordinate model; the latter is a label for organizing fixtures, not a verified intersection topology.
- Templates are deterministic for the same inputs. Optional live model planning is not deterministic; its output is saved and revalidated.
- The XML writer uses a narrow1.0 format. The importer only accepts the semantic tree this writer supports. It is not a general XML editor, converter or parser for third-party exports.
- Static XML/parameter validity is distinct from map/blueprint compatibility, simulator execution, collision metrics and ADS safety. No XSD validator is bundled or implicitly marked as run.
- Preview is illustrative kinematics, not perception, sensor simulation or vehicle dynamics. It does not supply TTC/collision verdicts.
- Local roles share one workspace; there is no tenant isolation, remote pairing, websocket Bridge, production deployment, reset-password email or external identity provider.
- ScenarioRunner integration needs user-configured real map origin/blueprints and has not been run against a simulator here. It is not a confirmed end-to-end CARLA feature.
- API call caps are not financial budget guarantees. Provider errors do not silently fall back to offline generation.

## Next compatibility work

Validate a named simulator version on real hardware; record adapted XML/input hashes and runner version; add road-relative placement and a catalog read adapter; integrate external XSD/checker validation with explicit version/redistribution rules; add multi-actor imports only with tests that prevent unsupported features from being dropped.

## Public references used

- ASAM model reference: https://releases.asam.net/OpenSCENARIO/1.0.0/Model-Documentation/RenderedXsdOutput.html
- ScenarioRunner behavior: https://scenario-runner.readthedocs.io/en/latest/openscenario_support/
- ScenarioRunner CLI/configuration: https://github.com/carla-simulator/scenario_runner
- OpenAI structured outputs: https://developers.openai.com/api/docs/guides/structured-outputs

These are specifications/integration references, not claims of endorsement or inherited project history.
