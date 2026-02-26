# Project Roadmap

## Current Milestone
- ID: M1
- Name: API Parity with Committed OpenAPI Spec
- Status: In Progress
- Target Version: v0.5.0
- Last Updated: 2026-02-26
- Summary: Bring the running FastAPI implementation into behavioral and schema parity with `openapi/openapi.yaml` by adding missing endpoints and models, aligning request/response contracts, preserving backward compatibility for existing clients, and shipping validation tests plus docs updates.

## Milestones
| ID | Name | Target Version | Status | Target Date | Notes |
| --- | --- | --- | --- | --- | --- |
| M1 | API Parity with Committed OpenAPI Spec | v0.5.0 | In Progress | 2026-03-20 | Align runtime and HTTP surface to spec without breaking current `/synthesize` clients |

## Plan History
### 2026-02-26 - Accepted Plan (v0.5.0 / M1)
- Scope:
  - Align API surface to spec:
    - Add `GET /model/inventory`
    - Add `GET /custom-voice/speakers`
    - Add `POST /synthesize/voice-design`
    - Add `POST /synthesize/custom-voice`
    - Add `POST /synthesize/voice-clone`
    - Keep legacy `POST /synthesize` and `POST /synthesize/stream` as compatibility routes during transition
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
    - `scripts/export_openapi.py` output is unchanged when run after implementation (or spec is intentionally revised in same PR).
  - Runtime parity:
    - VoiceDesign, CustomVoice, and VoiceClone flows execute through unified runtime controls with deterministic 4xx/5xx mapping.
    - `GET /custom-voice/speakers` returns supported speakers for selected model or a documented 4xx/5xx failure.
  - Backward compatibility:
    - Existing `/synthesize` clients still function for VoiceDesign flow.
    - Deprecation note exists in README for legacy endpoints, with migration examples.
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
| M1-T01 | 1 | Produce frozen parity matrix (`spec route/schema` -> `code route/schema`) and lock gap list | Gale | 0.5d | - | In Progress |
| M1-T02 | 1 | Define compatibility contract for legacy `/synthesize` and `/synthesize/stream` (deprecation behavior + headers/docs) | Gale | 0.5d | M1-T01 | Planned |
| M1-T03 | 1 | Finalize canonical mode/model enums and error mapping table (`400/503/500`) | Gale | 0.5d | M1-T01 | Planned |
| M1-T04 | 2 | Implement mode-aware runtime state and model load request handling (`voice_design/custom_voice/voice_clone`) | Gale | 1.0d | M1-T03 | Planned |
| M1-T05 | 2 | Add runtime wrappers for `generate_custom_voice` and `generate_voice_clone` with uniform exception mapping | Gale | 1.0d | M1-T04 | Planned |
| M1-T06 | 2 | Add runtime helpers for `model inventory` and `supported speakers` queries | Gale | 0.5d | M1-T04 | Planned |
| M1-T07 | 3 | Add HTTP endpoints: `GET /model/inventory`, `GET /custom-voice/speakers` | Gale | 0.5d | M1-T06 | Planned |
| M1-T08 | 3 | Add HTTP endpoints: `POST /synthesize/voice-design`, `POST /synthesize/custom-voice`, `POST /synthesize/voice-clone` | Gale | 1.0d | M1-T05 | Planned |
| M1-T09 | 3 | Introduce new Pydantic schemas for load/inventory/speaker/custom/clone and align status payload shapes | Gale | 0.75d | M1-T03 | Planned |
| M1-T10 | 3 | Preserve legacy endpoints by delegating to new handlers with migration-safe behavior | Gale | 0.5d | M1-T08 | Planned |
| M1-T11 | 4 | Add endpoint tests for happy paths and key errors (invalid model/mode, loading state, invalid clone input) | Gale | 1.5d | M1-T07, M1-T08, M1-T09 | Planned |
| M1-T12 | 4 | Add parity test/assertion: `openapi/openapi.yaml` == exported schema (or intentional diff gate) | Gale | 0.5d | M1-T07, M1-T08, M1-T09 | Planned |
| M1-T13 | 4 | Update README with new endpoints + migration examples and deprecation note | Gale | 0.5d | M1-T10 | Planned |
| M1-T14 | 5 | Run smoke suite, finalize changelog entry, and mark milestone complete if acceptance criteria pass | Gale | 0.5d | M1-T11, M1-T12, M1-T13 | Planned |

### Live Progress Board (M1)
#### In Progress
- M1-T01 (Phase 1): Produce frozen parity matrix and lock gap list.

#### Planned
- M1-T02, M1-T03
- M1-T04, M1-T05, M1-T06
- M1-T07, M1-T08, M1-T09, M1-T10
- M1-T11, M1-T12, M1-T13
- M1-T14

#### Done
- None yet.

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
- Add unit tests for `/model/load`, `/synthesize`, and `/synthesize/stream` error paths.
- Add integration test that writes and validates returned WAV header.
- Add graceful startup warm-load option (env-controlled).
- Add response metadata headers for generation latency.
- Add `GET /adapters/{id}/voices` for discoverable voice/speaker options.
- Add generalized `POST /adapters/{id}/load` and `POST /adapters/{id}/unload` endpoints.
- Add async synthesis job APIs: `POST /synthesize/jobs`, `GET /synthesize/jobs/{job_id}`, and `GET /synthesize/jobs/{job_id}/audio`.
- Add an example Swift client snippet directly in this repo.

## Change Log
- 2026-02-26: Initialized roadmap and set M1 for v0.5.0 API parity with committed OpenAPI spec.
- 2026-02-26: Updated M1 status to In Progress and added ticket-level execution plan with owners, estimates, and dependencies.
- 2026-02-26: Added live progress board and started execution with M1-T01 in progress.
- 2026-02-26: Consolidated README `Roadmap` and `TODO` lists into `ROADMAP.md` under `Product Backlog`.
