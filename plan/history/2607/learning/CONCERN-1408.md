---
source: CONCERN-1408
timestamp: '2026-07-14T16:44:25.587410+00:00'
title: spec gaps — 42 codebase invariants not captured in YAML spec corpus
type: learning
---

## Summary

A broad spec-gap analysis identified 42 invariants that are clear in code,
`notes/`, and `AGENTS.md` but absent from the machine-readable YAML spec corpus
surfaced by `spec-dump`. A developer reproducing Vultron from specs alone would
miss or misimplement these.

Full analysis: `wip_outputs/spec-gap-analysis.md` (on branch
`task/1374-fix-identify-vendors-coordinators-exhaustion`).

## Gaps by Target Spec

### Critical Protocol Gaps — VP / SM

1. CS forced transitions (`pX→PX`, `vP→VP`) not in SM or VP
2. Only 40 of 64 CS states reachable (`vF*`, `*fD*` invalid) — not in SM or VP
3. Single-writer regime not stated as a protocol axiom in VP/SM
4. Routing topology absent from VP
5. PEC 5-state machine (pocket veto) lives only in `notes/participant-embargo-consent.md`
6. EM counter-revision (`REVISE→REVISE`) MUST NOT cascade PEC — not in EP or CM

### Domain Invariants — CM / SM / EP

1. `actor_participant_index` is a derived cache; `case_participants` is the authority; divergence MUST be a hard error
2. Participant-specific (RM/VFD) vs. participant-agnostic (EM/PXA) state scoping
3. RM terminal guard must precede same-state idempotency node in BT composition
4. Do-not-downgrade embargo consent on idempotent retries

### Behavior Tree Patterns — BTND / BT

1. BT-HELPER-01: helper methods raise; `update()` is the sole try/except boundary
2. Blackboard no-slash rule + `{noun}_{id_segment}` naming convention
3. BTBridge requires `threading.RLock`, not plain `Lock`
4. BT result channel for domain errors: write exception to `result_out["error"]`, re-raise in `execute()`
5. `memory=False` Sequence partial-write is non-transactional
6. `behaviors/` MUST NOT import from `use_cases/`
7. Decomposed leaf nodes must convert `KeyError` to explicit `FAILURE`

### Wire / AS2 Patterns — SE / VM / AF / RF

1. `_validate_registry_order()` import-time guard + `RegistryOrderError`
2. `serialize_as_any=True` required at both persistence and delivery boundaries
3. Vocabulary override must preserve at least one base-module registration
4. Activity Translator port (correct replacement for `from_core()` calls in core)
5. `VulnerabilityCase.case_activity` cannot store typed activities
6. `inReplyTo` must be enforced at model level via `model_validator`
7. Actor subtype-aware pattern matching open design question
8. Recursive rehydration of `Accept(Invite)` + `VulnerabilityCaseStub` expansion rule

### Architecture / Hexagonal — ARCH

1. `create_app()` MUST NOT mutate module-level singletons
2. ASGIEmitter scheme+netloc-only base URL + reentrancy guard
3. Production adapters MUST NOT import from `vultron/demo/`
4. Port interfaces MUST NOT use bare `BaseModel` — contradiction with CS-10-001 (resolved: CS-10-001 updated)
5. Outbound delivery three-stage pipeline
6. `validate-at-edge` as a driving adapter boundary obligation
7. Architecture ratchet test discipline (`actual == KNOWN_VIOLATIONS` bidirectional)

### Testing Patterns — TB

1. `BTTestScenario` deep-module harness
2. BT factory determinism: explicit always-succeed factory required when default is probabilistic
3. Operational test rules (one-run rule, 5-second timeout policy, `SUBFAILED` caveat)
4. Integration test per-actor DataLayer isolation
5. Helper enums MUST NOT use `Test*` names
6. Vocabulary side-effect imports required in subdirectory `conftest.py`

### Demo / Simulation — DC / DEMOMA / DEMOCI

1. `demo_step` vs. `demo_check` semantic distinction
2. Exchange demos permitted to use direct inbox injection (spec/code contradiction resolved by DEMOMA-05-003)
3. `reset_demo_failures`/`assert_demo_success` bookend contract
4. Fuzzer node replacement lifecycle has no process spec

## Most Surprising Single Gap

Gap 29: direct contradiction between `notes/architecture-hexagonal.md` and `specs/code-style.yaml`.
CS-10-001 updated to "named domain-typed Pydantic classes" (kind: language); ARCH-08-002 adds
the port-specific enforcement.

**Resolved**: 2026-07-14 — all 42 gaps backfilled directly into existing YAML spec files
(no new files, no new impl issues). Docs PR: <https://github.com/CERTCC/Vultron/pull/1412>.
