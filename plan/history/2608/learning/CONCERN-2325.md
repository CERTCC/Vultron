---
source: CONCERN-2325
timestamp: '2026-08-19T14:34:34.227166+00:00'
title: demo_check vs demo_gate — causal precondition gating in fv-demo
type: learning
---

## Concern

Async race windows in `fv_demo.py` beyond the genesis ordering guard (ADR-0059).
Several `wait_for_*` calls that are causal preconditions for subsequent steps were
wrapped in `demo_check` (records failure and continues) instead of `demo_gate`
(blocks dependent steps on failure). One call was a bare unwrapped call.

## Investigation findings

- `demo_check` wrapping a causal wait lets the dependent step run on unestablished
  state, producing confusing secondary failures (422s from triggers, invalid
  snapshot comparisons) that mask the root cause.
- A bare `wait_for_*` call raises `AssertionError` directly, bypassing the harness
  failure accumulator — earlier `demo_check` failures are lost.
- Investigation of `wait_for_case_participants` (L509) revealed that `fv_demo.py`
  was bypassing the real CaseProposal round-trip entirely: it called
  `post_to_trigger(create-case)` and `seed_case_participants_for_demo` directly,
  making the wait a no-op poll on already-committed state. The real CaseProposal
  dance (vendor → CaseActor → Accept + Create(VulnerabilityCase)) is exercised by
  `fvcv_handoff_demo` via `run_direct_path_rm_triage` and the vendor's own
  case-actor service at port 7999.
- `LedgerGapBuffer` already handles out-of-order `Announce(CaseLedgerEntry)`
  deliveries (both pre-genesis and non-genesis), so the concern's first bullet
  was already mitigated at the actor level.

## Outcome

**Docs PR**: <https://github.com/CERTCC/Vultron/pull/2374> (`Closes #2325`)

New spec entries:

- `EDF-06-008`: temporal wait timeouts MUST be justified at the call site
- `DEMOMA-22-007`: every `wait_for_*` call MUST be wrapped in `demo_gate` or
  `demo_check`; bare calls prohibited

New notes section: `notes/demo-ci-diagnostics.md` § "Async Race Window Patterns"

New AGENTS.md pitfall: `vultron/demo/AGENTS.md` § "Never Wrap a Causal Wait in
`demo_check`" — before/after code examples for all three anti-patterns.

**Implementation issues spawned**:

- #2372: fix fv-demo to use real CaseProposal round-trip (prerequisite)
- #2375: migrate `demo_check`-wrapped causal waits to `demo_gate` in
  `fv_demo.py` and `fvcv_handoff_demo.py` (blocked-by #2372)
