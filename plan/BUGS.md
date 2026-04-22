# Bugs to fix

Items in this file supersede IMPLEMENTATION_PLAN.md.

Use format `BUG-YYMMDDXX` for bug IDs, where `YYMMDD` is the date the bug
was identified and `XX` is a sequential number for that day. For example,
the first bug identified on March 26, 2026 would be `BUG-26032601`.
Include a brief description in the title, and provide detailed reproduction
steps, root cause analysis, and resolution steps in the body.

---

## BUG-26042204 — three-actor demo never activates the case embargo after owner-gated accept flow — NEW

**Symptoms:** The full test suite with integration tests enabled
(`uv run pytest -m "" --tb=short`) currently fails with:

```text
FAILED test/demo/test_three_actor_demo.py::TestRunThreeActorDemo::test_full_workflow_succeeds
E   AssertionError: Expected ACTIVE embargo state, found PROPOSED
```

The failure is raised from
`vultron/demo/scenario/three_actor_demo.py:447` inside
`verify_case_actor_case_state()`.

**Root cause:** The demo scenario still had the **finder** and **vendor** call
the `accept-embargo` trigger, but never had the **case owner** accept. Because
the coordinator creates the case in this scenario, the coordinator remains the
authoritative case owner and is the actor that must drive the shared case EM
state from `PROPOSED` to `ACTIVE`.

After the recent owner-gated embargo trigger change,
`SvcAcceptEmbargoUseCase` only advances the shared case EM state when the
triggering actor is the case owner (`_is_case_owner()` in
`vultron/core/use_cases/triggers/embargo.py`). Non-owner accepts now record
participant consent without changing `case.current_status.em_state`, so the
scenario can finish with the authoritative case still in `PROPOSED`.

**Components involved:**

- `vultron/demo/scenario/three_actor_demo.py`
- `vultron/core/use_cases/triggers/embargo.py`
- `test/demo/test_three_actor_demo.py`

**Brief description:** The three-actor demo orchestration was out of sync with
the owner-gated embargo-accept semantics. It expected participant acceptances
alone to drive the authoritative case into `EM.ACTIVE`.

**Resolution:** The three-actor scenario now has the coordinator-owned case
accept the embargo proposal on the authoritative CaseActor before the other
participant acceptances are recorded. Final-state verification and integration
coverage now require all three participants, including the coordinator owner,
to record acceptance of the active embargo.

Status: FIXED — 2026-04-22.
