---
source: SPEC-RETIRE-TRIG-12-003
timestamp: '2026-11-05T00:22:00.675188+00:00'
title: Retired requirement TRIG-12-003
type: implementation
---

Retired TRIG-12-003 from `specs/triggerable-behaviors.yaml` (#4190).

Why: The golden OpenAPI snapshot the rule names is deleted. It was a gating scaffold for the ADR-0110 trigger-stack collapse, that migration landed on 2026-10-01, and the frozen file also pinned FastAPI's own error schemas, so every FastAPI or Pydantic bump turned red until an agent regenerated it (#4190). The trigger contract is now held by the route-to-registry bijection (TRIG-12-007) and the exact-response-key test (TRIG-12-002).

Final text: `plan/retired-specs/TRIG-12-003.md`.
