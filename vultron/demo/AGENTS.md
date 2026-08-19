# AGENTS.md — vultron/demo/

> For project-wide conventions see the root [AGENTS.md](../../AGENTS.md).
> This file covers rules specific to demo scripts and multi-actor scenario code.

---

## Common Pitfalls — demo layer

### Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

When building multi-actor demo scripts, always drive actor behavior through
**real HTTP trigger endpoints** (e.g., `POST /{actor_id}/trigger/accept-actor-recommendation`).
Never construct and POST activities directly to actor inboxes to fake an
approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that exercise the wrong code path. The distinction:

- **Puppeteering** = sending a trigger that causes the actor to decide and act
  (validates the behavior tree path)
- **Spoofing** = forging the resulting activity as if the actor had already
  decided (skips the BT entirely)

**How to apply:** Before writing any demo step where one actor "responds" to
another, check whether the trigger endpoint for that response exists. If it
doesn't, implement the full hexagonal stack (trigger endpoint → service layer
→ BT) first, then write the demo step. Working around a missing endpoint by
injecting the response directly means the demo proves nothing about the
actual behavior tree path.

<!-- Source: ISSUE-1535 -->

---

### BT Demo `main()` Must Be Callable With No Arguments (Console-Script Entry Points)

`[project.scripts]` entry points invoke `main()` with **no arguments**. Demo
modules that define `def main(args):` — where `args` is a required positional
parsed by an `if __name__ == "__main__"` block — will fail immediately with
`TypeError: main() missing 1 required positional argument` when invoked via
`uv run <script>`.

**Fix:** give `main` an `args=None` default and fall back to `_parse_args()`:

```python
def main(args=None) -> None:
    if args is None:
        args = _parse_args()
    ...
```

This preserves the path used by `vultron/demo/cli.py`'s click sub-group (which
passes a `SimpleNamespace` via `_bt_args()`) while also being callable with
zero arguments from a console script.

**Always test the actual console script** (`PYTHONPATH= uv run <script>`) — not
just the module import — and clear `PYTHONPATH=/app` devcontainer contamination
(see root `AGENTS.md` § "PYTHONPATH=/app contaminates imports").

<!-- Source: ISSUE-1568 -->

---

### Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before writing a **second use** of a pattern from an existing scenario file,
extract it to `vultron/demo/helpers/` first. Do not copy-paste a function body,
a polling loop, a verification block, or any other logical unit from an
existing scenario file into a new one.

**Why:** Every demo scenario written by copying the previous one propagates
latent bugs alongside valid patterns. Issue #1632 documented residual
duplication remaining after PR #1629 reactively extracted five helper modules.
Copy-paste is the root cause; extraction-first prevents the problem from
recurring.

**How to apply:**

1. Before writing a new scenario step, grep `vultron/demo/helpers/` for an
   existing helper that covers the same pattern.
2. If one exists, import and call it. Do not inline a copy.
3. If none exists and this is the second occurrence of the pattern, extract it
   to the appropriate `helpers/` module first, then call it from both places.
4. A pattern that appears only once may stay inline, but add a comment marking
   it as a candidate for extraction when a second use arises.

This rule applies to scenario files in `vultron/demo/scenario/`. Exchange demos
under `vultron/demo/exchange/` are lower-level and may duplicate less when a
full helper would add more abstraction than value.

See `specs/multi-actor-demo.yaml` DEMOMA-17-001 for the normative requirement
(a MUST-level specialisation of the project-wide SHOULD rule CS-22-001 in
`specs/code-style.yaml`).

<!-- Source: ISSUE-1652 -->

---

### Ownership-Transfer Trigger: Always Self-Deliver the Accept to the Accepting Actor's Inbox

When the accepting actor triggers `accept-case-ownership-transfer`, the
trigger-side BT (`AcceptCaseOwnershipTransferTriggerBT`) queues the
`Accept(Offer(VulnerabilityCase))` activity addressed only to the **offering**
actor. The accepting actor's own DataLayer replica is therefore **not** updated
by that path.

After queuing the trigger, the demo script **MUST** also POST the Accept
activity to the accepting actor's own inbox so that
`AcceptCaseOwnershipTransferReceivedUseCase` runs locally and updates
`case.attributed_to` on the accepting actor's replica.

```python
# ✅ Correct — trigger first, then self-deliver
accept_result = post_to_trigger(
    client=accepting_client,
    actor_id=accepting_actor_id,
    behavior="accept-case-ownership-transfer",
    body={"offer_id": offer_id},
)
accept_activity = as_TransitiveActivity.model_validate(accept_result["activity"])
post_to_inbox_and_wait(accepting_client, accepting_participant_id, accept_activity)

# ❌ Wrong — skips local replica update; attributed_to never changes on accepting actor
accept_result = post_to_trigger(
    client=accepting_client,
    actor_id=accepting_actor_id,
    behavior="accept-case-ownership-transfer",
    body={"offer_id": offer_id},
)
# missing: extract accept_activity and post_to_inbox_and_wait(...)
```

**Why:** PR #1590 silently deleted this self-delivery step in a commit that
appeared to only change a field accessor. The omission only surfaced under
the CI integration test — functional tests passed because the offering actor's
replica updated correctly via the normal outbox delivery path. The demo CI
integration tests (`test/ci/invariants/`) are the authoritative runtime
enforcement for this invariant.

See `vultron/demo/scenario/fvcv_handoff_demo.py` and
`vultron/demo/scenario/fccv_handoff_demo.py` for the correct pattern.

<!-- Source: CONCERN-1653 -->

---

### Never Carry One Actor's Mail to Another Actor's Inbox

Demo scripts MUST NOT POST an activity to an actor's inbox on behalf of
another actor. This includes helper functions such as `post_to_inbox_and_wait`.

**Why:** Delivering an activity to an inbox is the transport layer's job, not
the demo's. When a demo calls `post_to_inbox_and_wait(vendor_client, vendor_id,
invite)` it is acting as a surrogate mail carrier — putting a message into
Vendor's inbox as if it arrived from the network. This is a form of spoofing:
the real outbox→delivery→inbox path is never exercised, so demo CI proves
nothing about whether the protocol actually works end-to-end.

The distinction that matters:

- **Triggering** = POST to an actor's *trigger endpoint* to cause it to emit
  an activity (`POST /actors/{id}/trigger/invite-actor-to-case`). The actor
  decides and sends. Correct.
- **Mail-carrying** = POST an activity directly to another actor's *inbox*
  from outside that actor's own delivery path (`POST /actors/{id}/inbox/`).
  The demo bypasses the real transport. Wrong.

**Root cause of the pattern:** The inbox endpoint returns 202 immediately
(`BackgroundTasks`) before the activity is fully processed. Naive polling
after a trigger timed out, so mail-carrying was added as a workaround. The
correct fix is to gate on the effect the delivery causes — the real HTTP
delivery path (`HttpDeliveryAdapter`) with its retry/backoff will complete.

> **Amended (CONCERN-2181):** this section previously ended "the demo just needs
> to wait long enough." That framing is what the causal-gating rule corrects. A
> long-enough timeout is not the fix; observing the *right thing* is. Choose the
> observable per EDF-06-002 and EDF-06-003 — the committed state of the actor
> that produces the effect, read from its own container — and express it with
> `demo_gate`, not a raised timeout. See the next section.

**How to apply:**

1. After triggering an actor to emit an activity, do **not** manually deliver
   that activity to any inbox. Instead, poll the expected side-effect directly:
   - Use `wait_for_case_on_container` to verify a case replica arrived.
   - Use `find_case_invite_for_actor` to verify an invite arrived.
   - Use `wait_for_object_stored` to verify an arbitrary object arrived in a DataLayer.
2. If a poll times out reliably in CI, the underlying delivery path needs
   investigation (retry parameters, health checks, container startup order)
   — not a workaround in the demo script.

**Exception — self-delivery (CONCERN-1653):** A demo script MAY call
`post_to_inbox_and_wait` when an actor needs to deliver an activity to its
*own* inbox to update its own replica — for example, after triggering
`accept-case-ownership-transfer`, the accepting actor must self-deliver the
resulting `Accept` activity so that `AcceptCaseOwnershipTransferReceivedUseCase`
runs locally. This is not mail-carrying: the actor is posting to its own inbox,
not acting as a surrogate for the transport layer.

The rule this section prohibits is **cross-actor delivery**: a demo using
*Actor A's* credentials to POST a message into *Actor B's* inbox. That is the
pattern to eliminate; CONCERN-1653's self-delivery pattern is orthogonal and
remains correct.

<!-- Source: CONCERN-1635 -->

---

### Gate Each Step on Its Cause, Not on Its Position in the Script

A scenario is a list of steps, so it is tempting to write it as "A, and then B."
The protocol is causal: "A, **therefore** B." Where those differ you have a race,
because triggers return HTTP 202 and the effect commits later, in a background
task, on another container.

**Why:** Seven of the nineteen sub-issues of Epic #2136 were this same defect in
a different scenario — a step ran before the event enabling it had propagated.
Fixing them one at a time does not stop the next scenario from reintroducing it.

**How to apply:**

1. **Gate on the committed effect, read where it commits.** The predicate must be
   a property of the actor that commits the effect, fetched from *that actor's own
   client*. Observing it on the sender proves only that the sender emitted
   something (EDF-06-002).
2. **Never gate on a synchronously-available proxy.** If the observable resolves
   during the triggering request while the effect commits after the 202, it proves
   the cause *started*, not that it finished. Bug #2134: `engage-case` gated on
   "case exists" instead of the receiver's own `RM.VALID` (EDF-06-003).
3. **Discover a caused object by its properties, not its cause's ID.** When a
   received-side use case forwards a *new* activity, the consequent has a new
   identity. Use a discriminator scan — `find_case_invite_for_actor`,
   `find_cp_offer_for_case`, and (arriving with the `fix/demo-ci` branch)
   `find_ownership_transfer_offer_for_actor` — not
   `wait_for_object_stored(obj_id=<sender's original id>)`, which silently times
   out. Bug #2178 (EDF-06-004).
4. **Use `demo_gate`, not `demo_check`, for a precondition.** `demo_check` records
   the failure and returns, so the dependent step runs anyway on state that was
   never established. `demo_gate` accumulates identically but stops the dependent
   steps (DEMOCI-01-007, EDF-06-005).
5. **Put the gate in `vultron/demo/helpers/`.** Scenario modules MUST NOT define
   their own polling loops — that is how the #2178 fix landed in
   `fvcv_handoff_demo.py` but not `fccv_handoff_demo.py` (DEMOMA-22-002,
   DEMOMA-17-001).
6. **Label irreducibly temporal waits as such.** Liveness probes, embargo
   deadlines, and transport backoff are legitimately time-based; say so at the
   call site so they are not mistaken for causal gates (EDF-06-006).
7. **Raising a timeout is not a fix.** If a gate times out reliably, either the
   observable is wrong (see 1–3) or the effect can be *lost* rather than delayed —
   in which case the protocol must buffer it (ADR-0037, ADR-0059) and a demo guard
   would be papering over a production bug.

**Testing gates:** exercise the real context manager. A test that patches
`demo_check`/`demo_gate` out with `contextlib.nullcontext` makes the assertion
propagate and passes while proving nothing — that is precisely how the missing
gate before `engage-case` escaped notice.

See `specs/event-driven-control-flow.yaml` EDF-06, `specs/multi-actor-demo.yaml`
DEMOMA-22, ADR-0058, and
[notes/event-driven-control-flow.md](../../notes/event-driven-control-flow.md)
§ "Temporal Sequence vs. Causal Sequence".

<!-- Source: CONCERN-2181 -->

---

### Never Wrap a Causal Wait in `demo_check` (and Never Leave One Bare)

A `wait_for_*` call that is a precondition for the next step MUST be
wrapped in `demo_gate`, not `demo_check` and not left as a bare call.

**Why `demo_check` is wrong here:** `demo_check` records the timeout as a
failure and then **continues**. The next step runs on state that was never
established — producing a confusing secondary failure (a 422 from a
trigger, a wrong snapshot comparison, a ledger assertion on a partial
replica) that obscures the root cause.

**Why a bare call is also wrong:** a bare `wait_for_*` call raises
`AssertionError` directly on timeout, bypassing the harness's failure
accumulator. Earlier `demo_check` failures are lost. Downstream steps get
no structured skip — the exception terminates the scenario. Bare calls look
like gates but are not.

```python
# ❌ Wrong — demo_check lets the next step run on uncommitted RM.VALID state
with demo_check(f"{actor.id_} reached RM.VALID before engage-case"):
    wait_for_participant_rm_state(
        client=vendor_client, case_id=case.id_,
        actor_id=actor.id_, expected_states={RM.VALID, RM.ACCEPTED},
    )
vendor_engages_case(...)  # may 422 if RM.VALID not yet committed

# ❌ Wrong — bare call raises AssertionError directly, bypasses accumulator
wait_for_contiguous_ledger_coverage(
    client=finder_client, case_id=case.id_,
    expected_tail_index=vendor_tail_index,
)
compare_replica_state(...)  # runs on partial replica if wait timed out

# ✅ Correct — demo_gate blocks dependent steps when precondition is unmet
with demo_gate(f"{actor.id_} reached RM.VALID before engage-case"):
    wait_for_participant_rm_state(
        client=vendor_client, case_id=case.id_,
        actor_id=actor.id_, expected_states={RM.VALID, RM.ACCEPTED},
    )
vendor_engages_case(...)  # skipped (not run) if gate failed
```

**How to decide `demo_gate` vs `demo_check`:** ask whether the next step
would operate on wrong or incomplete state if this wait timed out.

- **Yes** → `demo_gate`. The wait is a causal precondition.
- **No** → `demo_check`. The wait is temporal or a post-hoc verification.
  Label it as temporal at the call site (EDF-06-006) so it is not mistaken
  for a causal gate in a future edit.

See `notes/demo-ci-diagnostics.md` § "Async Race Window Patterns" for the
full diagnostic workflow, and `specs/event-driven-control-flow.yaml`
EDF-06-005 and EDF-06-006 for the normative rules.

<!-- Source: CONCERN-2325 -->

---

### Event-Phrase Lookups MUST Use `lookup_entry()`, Not a Local Phrase Dict

Any display-layer code that maps a `MessageSemantics` value to a human-readable
phrase MUST use `lookup_entry(semantics).phrase` from
`vultron.semantic_registry`, not a local `dict[str, str]` parallel table.

**Why:** A local dict keyed by `MessageSemantics` values will silently drift
as new semantics are added to the enum. `SemanticEntry.phrase` is mandatory
(SE-07-003), so a missing phrase is a `TypeError` at registry construction
time — not a silent fallback at render time.

**How to apply:** Import `from vultron.semantic_registry import lookup_entry`
and render with `lookup_entry(semantics).phrase.format_map(defaultdict(lambda: "—", slots))`.
Use the fallback humanizer (`event_type.replace("_", " ")`) only for event
types not in the registry (e.g., data from a future protocol version).

<!-- Source: CONCERN-1675 -->

---

### Docker Compose Service Names Are Not Actor Names

The service names in `docker/docker-compose-multi-actor.yml` (`vendor`,
`coordinator`, `vendor2`, `case-actor`) were chosen to match the roles in the
first demo scenarios and do not need to match the CVD actor roles housed
within them. When designing a new multi-actor scenario:

- The **service name** is a docker-compose routing label. Reuse existing
  service names by remapping them to new semantic roles via `--env-file` or
  environment variable overrides — there is no requirement that a service
  named `vendor` contains a Vendor actor.
- The **actor name** (`VULTRON_*_BASE_URL` env var bindings, actor IDs seeded
  at startup) is the meaningful identity. Choose actor names to reflect their
  CVD role in the scenario, not the docker service name.
- Avoid adding new services just to get a new actor name. In multi-actor
  scenarios (FCCV, FVCV-handoff), the existing four services are reused with
  role-alias environment variable bindings; this keeps the CI service
  startup count constant.

**Future direction**: the service names may eventually be renamed to neutral
labels (`actor1`–`actor4`) so the compose file is scenario-agnostic. Until
then, use the existing services with role-alias bindings.

<!-- Source: ISSUE-1216, plan/incoming/learnings/20260722-fccv-handoff-container-remapping.md -->

---

### The Ledger Dump Belongs in the Failure Path, Not After the Last Phase

A scenario's forensic artifacts are worth the most in exactly the run that
fails. Code placed *after* the last phase runs only when nothing went wrong.
Before #2239, every `run_<name>_demo()` called `_phase_dump_case_ledgers()` as
its final statement, so any assertion escaping a `demo_check`/`demo_gate` block
skipped the dump entirely — `main()`'s `finally: assert_demo_success()` still
raised, CI still failed, but `devlogs/` was empty and the `invariant-harness`
job died on artifact download instead of reporting an invariant result.

**Why:** A demo that fails without artifacts is indistinguishable from a demo
that never ran. Worse, the invariant harness *skipped* on a missing directory,
so the pipeline read green for the wrong reason.

**How to apply:**

1. **Run the scenario inside `scenario_harness()`.** Wrap the whole body of
   `run_<name>_demo()` in `with scenario_harness("<demo-name>") as harness:`.
   The harness resets the failure accumulator on entry, always dumps on the way
   out (success or exception), and calls `assert_demo_success()` last
   (DEMOMA-23-001).
2. **Register the dump the moment a case exists.** Immediately after the phase
   that creates the case, call `harness.dump_with(lambda: _phase_dump_case_ledgers(...))`.
   Every phase below that line can then fail without costing the ledgers
   (DEMOMA-23-003).
3. **Do not re-add `try/finally: assert_demo_success()` in `main()`.** The
   harness owns the accumulator; a second owner reintroduces the bug by
   asserting before the dump has run (DEMOMA-23-001).
4. **Keep `_phase_dump_case_ledgers` thin.** It builds
   `LedgerDumpTarget`s and delegates to
   `vultron.demo.helpers.ledger_dump.dump_case_ledgers()`. No per-scenario
   fetch/write loops (DEMOMA-23-002, DEMOMA-17-001).
5. **The manifest is not optional.** `dump_case_ledgers()` writes
   `devlogs/<demo>/dump-manifest.json` from a `finally`, recording the case ID,
   how many ledger files were captured, and for each missing actor *why*. That
   file is what lets the invariant harness fail on a real "no ledger entries"
   assertion rather than on a download error (DEMOCI-10-002, DEMOCI-10-003).
6. **A dump failure must never replace the scenario's exception.** The harness
   swallows dump errors into the manifest's `reason` field and re-raises the
   original failure with the accumulated `demo_check` failures attached as
   exception notes (DEMOCI-10-004, DEMOMA-23-004).

**Testing this:** patch a mid-scenario phase to raise, point `DEVLOGS_DIR` at a
`tmp_path`, and assert the manifest exists. See
`test/demo/test_issue_2239_ledger_dump_in_finally.py`.

See `specs/demo-ci.yaml` DEMOCI-10, `specs/multi-actor-demo.yaml` DEMOMA-23,
and [notes/demo-ci-invariants.md](../../notes/demo-ci-invariants.md).

<!-- Source: ISSUE-2239 -->
