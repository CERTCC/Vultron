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

**Likely root cause:** The demo scenario still has the **finder** and
**vendor** call the `accept-embargo` trigger, but never has the **case owner**
accept.

(Except note that as the case creator, the vendor in the scenario *is* the
case owner, so there's a logic gap here that will need to be resolved in the
fix.)

After the recent owner-gated embargo trigger change,
`SvcAcceptEmbargoUseCase` only advances the shared case EM state when the
triggering actor is the case owner (`_is_case_owner()` in
`vultron/core/use_cases/triggers/embargo.py`). Non-owner accepts now record
participant consent without changing `case.current_status.em_state`, so the
scenario can finish with the authoritative case still in `PROPOSED`.

**Likely components involved:**

- `vultron/demo/scenario/three_actor_demo.py`
- `vultron/core/use_cases/triggers/embargo.py`
- `test/demo/test_three_actor_demo.py`

**Brief description:** The three-actor demo orchestration appears to be out of
sync with the new embargo-accept semantics. It still expects participant
acceptances alone to drive the authoritative case into `EM.ACTIVE`.

Status: NEW — added 2026-04-22.
