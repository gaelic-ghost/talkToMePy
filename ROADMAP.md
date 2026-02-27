# Project Roadmap

## Current Milestone
- ID: M1
- Name: API Parity with Committed OpenAPI Spec
- Status: In Progress
- Target Version: v0.5.0
- Last Updated: 2026-02-26
- Summary: Bring the running FastAPI implementation into behavioral and schema parity with `openapi/openapi.yaml` by adding missing endpoints and models, aligning request/response contracts, and shipping validation tests plus docs updates.

## Milestones
| ID | Name | Target Version | Status | Target Date | Notes |
| --- | --- | --- | --- | --- | --- |
| M1 | API Parity with Committed OpenAPI Spec | v0.5.0 | In Progress | 2026-03-20 | Align runtime and HTTP surface to committed target spec |

## Plan History
### 2026-02-26 - Accepted Plan (v0.5.0 / M1)
- Scope:
  - Align API surface to spec:
    - Add `GET /model/inventory`
    - Add `GET /custom-voice/speakers`
    - Add `POST /synthesize/voice-design`
    - Add `POST /synthesize/custom-voice`
    - Add `POST /synthesize/voice-clone`
    - Remove legacy `POST /synthesize` and `POST /synthesize/stream` in favor of mode-specific synthesis routes
  - Align model loading/control contract:
    - Introduce mode-aware load request (`voice_design`, `custom_voice`, `voice_clone`)
    - Add model-selection behavior that matches spec enums and error semantics
  - Align schema contracts:
    - Add new request/response models (`ModelLoadRequest`, inventory, speaker, custom voice, voice clone)
    - Reconcile status models to spec-required fields
  - Extend runtime adapter:
    - Support `generate_custom_voice` and `generate_voice_clone` pipelines in addition to voice design
    - Add speaker discovery passthrough and reference-audio handling for clone flow
  - Stabilize quality:
    - Add endpoint-level tests for success and error paths
    - Add parity checks against exported OpenAPI and update README examples
- Acceptance Criteria:
  - Route parity:
    - All routes declared in `openapi/openapi.yaml` are implemented and reachable.
    - Route/method mismatch report is empty for spec vs `app.openapi()`.
  - Schema parity:
    - Request/response payloads for parity endpoints validate exactly as documented in spec.
    - `scripts/export_openapi.py` output (`openapi/openapi.generated.yaml`) matches `openapi/openapi.yaml` after implementation (or target spec is intentionally revised in same PR).
  - Runtime parity:
    - VoiceDesign, CustomVoice, and VoiceClone flows execute through unified runtime controls with deterministic 4xx/5xx mapping.
    - `GET /custom-voice/speakers` returns supported speakers for selected model or a documented 4xx/5xx failure.
  - Compatibility and migration:
    - Legacy `/synthesize` and `/synthesize/stream` are intentionally removed and documented as a breaking change.
    - README includes migration examples for the new mode-specific routes.
  - Test bar:
    - Automated tests cover happy paths and key failures (invalid mode/model, loading in progress, unsupported format, invalid clone reference input).
    - CI test command for parity suite is documented in README.
- Risks/Dependencies:
  - qwen-tts model-type capability differences (`voice_design`, `custom_voice`, `base/voice_clone`) may require explicit guards and fallback behavior.
  - Performance variance without `flash-attn` can impact clone/custom endpoints under load.
  - OpenAPI spec may represent target behavior not yet finalized; unresolved ambiguities must be decided before final schema lock.
  - Additional model assets may be required for full custom/clone coverage in local and CI environments.

### Execution Breakdown (M1)
1. Phase 1 - Contract and Migration Design
   - Freeze endpoint and schema mapping from current code to target spec.
   - Decide compatibility behavior for legacy endpoints and response fields.
   - Produce migration notes for internal consumers.
2. Phase 2 - Runtime Core Expansion
   - Add mode-aware runtime state and load controls.
   - Implement custom voice and clone synthesis wrappers.
   - Add speaker inventory and model inventory primitives.
3. Phase 3 - HTTP Surface Parity
   - Implement missing routes and request/response models.
   - Map runtime exceptions to documented status codes.
   - Keep compatibility routes delegating to new handlers.
4. Phase 4 - Verification and Documentation
   - Add/expand tests for all parity endpoints and edge errors.
   - Re-export and verify OpenAPI parity.
   - Update README usage and deprecation path.
5. Phase 5 - Release Readiness
   - Run full smoke checks in local env.
   - Cut v0.5.0 changelog entry and finalize milestone status.

### Ticket Plan (M1)
| Ticket | Phase | Deliverable | Owner | Estimate | Depends On | Status |
| --- | --- | --- | --- | --- | --- | --- |
| M1-T01 | 1 | Produce frozen parity matrix (`spec route/schema` -> `code route/schema`) and lock gap list | Gale | 0.5d | - | Done |
| M1-T02 | 1 | Define compatibility contract for legacy `/synthesize` and `/synthesize/stream` (breaking-change removal + docs) | Gale | 0.5d | M1-T01 | Done |
| M1-T03 | 1 | Finalize canonical mode/model enums and error mapping table (`400/503/500`) | Gale | 0.5d | M1-T01 | Done |
| M1-T04 | 2 | Implement mode-aware runtime state and model load request handling (`voice_design/custom_voice/voice_clone`) | Gale | 1.0d | M1-T03 | Done |
| M1-T05 | 2 | Add runtime wrappers for `generate_custom_voice` and `generate_voice_clone` with uniform exception mapping | Gale | 1.0d | M1-T04 | Done |
| M1-T06 | 2 | Add runtime helpers for `model inventory` and `supported speakers` queries | Gale | 0.5d | M1-T04 | Done |
| M1-T07 | 3 | Add HTTP endpoints: `GET /model/inventory`, `GET /custom-voice/speakers` | Gale | 0.5d | M1-T06 | Done |
| M1-T08 | 3 | Add HTTP endpoints: `POST /synthesize/voice-design`, `POST /synthesize/custom-voice`, `POST /synthesize/voice-clone` | Gale | 1.0d | M1-T05 | Done |
| M1-T09 | 3 | Introduce new Pydantic schemas for load/inventory/speaker/custom/clone and align status payload shapes | Gale | 0.75d | M1-T03 | Done |
| M1-T10 | 3 | Remove legacy `/synthesize` and `/synthesize/stream` routes and finalize migration-safe docs | Gale | 0.5d | M1-T08 | Done |
| M1-T11 | 4 | Add endpoint tests for happy paths and key errors (invalid model/mode, loading state, invalid clone input) | Gale | 1.5d | M1-T07, M1-T08, M1-T09 | Done |
| M1-T12 | 4 | Add parity test/assertion: `openapi/openapi.yaml` == `openapi/openapi.generated.yaml` (or intentional diff gate) | Gale | 0.5d | M1-T07, M1-T08, M1-T09 | Done |
| M1-T13 | 4 | Update README with new endpoints + migration examples and breaking-change note | Gale | 0.5d | M1-T10 | Done |
| M1-T14 | 5 | Run smoke suite, finalize changelog entry, and mark milestone complete if acceptance criteria pass | Gale | 0.5d | M1-T11, M1-T12, M1-T13 | Planned |

### Live Progress Board (M1)
#### In Progress
- None.

#### Planned
- M1-T14

#### Done
- M1-T01 (Phase 1): Frozen parity matrix and locked gap list completed.
- M1-T02 (Phase 1): Legacy synth compatibility contract finalized as intentional breaking-change removal.
- M1-T03 (Phase 1): Mode/model enums and error mapping finalized.
- M1-T04 (Phase 2): Mode-aware runtime state and load request handling implemented.
- M1-T05 (Phase 2): Runtime wrappers added for custom-voice and voice-clone synthesis.
- M1-T06 (Phase 2): Inventory and speaker discovery runtime helpers added.
- M1-T07 (Phase 3): HTTP endpoints added for model inventory and custom-voice speakers.
- M1-T08 (Phase 3): HTTP endpoints added for voice-design/custom-voice/voice-clone synthesis.
- M1-T09 (Phase 3): Pydantic schema set aligned to target contract.
- M1-T10 (Phase 3): Legacy `/synthesize` and `/synthesize/stream` routes removed.
- M1-T11 (Phase 4): Endpoint tests expanded for happy/error parity scenarios.
- M1-T12 (Phase 4): OpenAPI parity assertion added with CI export+test gate.
- M1-T13 (Phase 4): README migration and breaking-change updates completed.

### Frozen Parity Matrix (M1-T01)
#### Route/Method Parity Snapshot (2026-02-26)
| Spec Route | Method | Runtime Route Exists | Notes |
| --- | --- | --- | --- |
| `/health` | GET | Yes | Parity |
| `/version` | GET | Yes | Parity |
| `/adapters` | GET | Yes | Parity |
| `/adapters/{adapter_id}/status` | GET | Yes | Parity |
| `/model/status` | GET | Yes | Parity |
| `/model/load` | POST | Yes | Runtime currently has no request body; spec expects `ModelLoadRequest` |
| `/model/unload` | POST | Yes | Parity (pending schema-field alignment under M1-T09) |
| `/model/inventory` | GET | No | Missing in runtime (`M1-T07`) |
| `/custom-voice/speakers` | GET | No | Missing in runtime (`M1-T07`) |
| `/synthesize/voice-design` | POST | No | Missing in runtime (`M1-T08`) |
| `/synthesize/custom-voice` | POST | No | Missing in runtime (`M1-T08`) |
| `/synthesize/voice-clone` | POST | No | Missing in runtime (`M1-T08`) |

#### Code-Only Compatibility Routes (Not in Target Spec)
- `POST /synthesize`
- `POST /synthesize/stream`

#### Locked Gap List
- Implement missing parity endpoints (`M1-T07`, `M1-T08`).
- Add mode-aware `ModelLoadRequest` and canonical mode/model mapping (`M1-T03`, `M1-T04`, `M1-T09`).
- Expand runtime for `custom_voice` and `voice_clone` execution paths (`M1-T05`, `M1-T06`).
- Remove legacy `/synthesize` and `/synthesize/stream` and document migration path (`M1-T02`, `M1-T10`, `M1-T13`).
- Add OpenAPI parity assertion tests and CI guardrails (`M1-T11`, `M1-T12`).

### Sequencing Notes
- Critical path: M1-T01 -> M1-T03 -> M1-T04 -> M1-T05 -> M1-T08 -> M1-T11 -> M1-T14.
- Parallelizable work:
  - M1-T06 can run after M1-T04 while M1-T05 is in progress.
  - M1-T09 can be developed in parallel with early runtime work once enums/error mapping are frozen.
  - M1-T13 can begin once endpoint behavior stabilizes; it does not block tests.
- Total estimate: ~9.25 engineering days (single-owner throughput).

## Product Backlog
### Near-Term Roadmap Items
- Add optional on-disk audio caching.
- Add structured request/response logging and timing metrics.
- Add Docker setup for self-hosting on a local machine (for example Mac mini).
- Add a small auth layer for non-local deployments.

### TODO Queue
- Add deeper unit tests for `/model/load`, `/synthesize/voice-design`, `/synthesize/custom-voice`, and `/synthesize/voice-clone` error paths.
- Add integration test that writes and validates returned WAV header.
- Add graceful startup warm-load option (env-controlled).
- Add response metadata headers for generation latency.
- Add `GET /adapters/{id}/voices` for discoverable voice/speaker options.
- Add generalized `POST /adapters/{id}/load` and `POST /adapters/{id}/unload` endpoints.
- Add async synthesis job APIs: `POST /synthesize/jobs`, `GET /synthesize/jobs/{job_id}`, and `GET /synthesize/jobs/{job_id}/audio`.
- Add an example Swift client snippet directly in this repo.
- Add branch protection policy note for required `pytest` vs optional `smoke-e2e` status checks.
- Add optional `ref_text` support for voice clone requests/runtime (toggle between x-vector-only and ICL clone modes).

## Change Log
- 2026-02-26: Initialized roadmap and set M1 for v0.5.0 API parity with committed OpenAPI spec.
- 2026-02-26: Updated M1 status to In Progress and added ticket-level execution plan with owners, estimates, and dependencies.
- 2026-02-26: Added live progress board and started execution with M1-T01 in progress.
- 2026-02-26: Consolidated README `Roadmap` and `TODO` lists into `ROADMAP.md` under `Product Backlog`.
- 2026-02-26: Completed M1-T01 by freezing a route/method parity matrix and locking the gap list for Phase 2/3 implementation.
- 2026-02-26: Split OpenAPI artifacts to protect target spec (`openapi/openapi.yaml`) from export overwrite; generator now writes `openapi/openapi.generated.yaml`.
- 2026-02-26: Added OpenAPI parity test and CI gate (`export_openapi` + pytest) to enforce target vs generated spec drift detection.
- 2026-02-26: Implemented M1 parity runtime/API/schema/test updates (M1-T02 through M1-T13), including mode-aware model loading and removal of legacy synth routes.
- 2026-02-26: Expanded CI with uv-aligned setup and separate model-backed `smoke-e2e` lane, including custom-voice and voice-clone API end-to-end smoke scripts.
