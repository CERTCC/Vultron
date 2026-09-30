---
title: Demo Scenario Authoring Rules
status: active
description: >
  How to write a multi-actor demo scenario without faking the protocol:
  puppeteer actors through trigger endpoints rather than spoofing via inbox
  injection, never carry one actor's mail to another's inbox, extract helpers
  before the second use, keep console-script entry points callable with no
  arguments, and treat docker service names as routing labels rather than actor
  identities.
related_specs:
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/event-driven-control-flow.yaml
  - specs/code-style.yaml
related_notes:
  - notes/event-driven-control-flow.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-invariants.md
  - notes/demo-scenario-registry.md
  - notes/fv-demo.md
  - notes/case-proposal.md
  - notes/ownership-transfer.md
  - notes/devcontainer-tooling.md
relevant_packages:
  - vultron/demo
---

# Demo Scenario Authoring Rules

Migrated out of `vultron/demo/AGENTS.md`, which keeps the one-line rules and
points here for the reasoning and examples.

The through-line: a demo exists to prove the protocol works. Every shortcut that
makes a scenario pass by doing the protocol's job *for* it converts the demo from
evidence into decoration.

---

## Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

Always drive actor behavior through **real HTTP trigger endpoints** (e.g.
`POST /{actor_id}/trigger/accept-actor-recommendation`). Never construct and POST
activities directly to actor inboxes to fake an approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that exercise the wrong code path. The distinction:

- **Puppeteering** = sending a trigger that causes the actor to decide and act
  (validates the behavior tree path)
- **Spoofing** = forging the resulting activity as if the actor had already
  decided (skips the BT entirely)

**How to apply:** Before writing any demo step where one actor "responds" to
another, check whether the trigger endpoint for that response exists. If it
doesn't, implement the full hexagonal stack (trigger endpoint → service layer →
BT) first, then write the demo step. Working around a missing endpoint by
injecting the response directly means the demo proves nothing about the actual
behavior tree path.

See also [notes/fv-demo.md](fv-demo.md) § "Puppeteering Constraint".

Source: ISSUE-1535

---

## Never Carry One Actor's Mail to Another Actor's Inbox

Scenario demos MUST NOT POST an activity to an actor's inbox on behalf of another
actor. This includes helper functions such as `post_to_inbox_and_wait`.

**Why:** Delivering an activity to an inbox is the transport layer's job, not the
demo's. When a demo calls
`post_to_inbox_and_wait(vendor_client, vendor_id, invite)` it is acting as a
surrogate mail carrier — putting a message into Vendor's inbox as if it arrived
from the network. This is a form of spoofing: the real
outbox→delivery→inbox path is never exercised, so demo CI proves nothing about
whether the protocol actually works end-to-end.

The distinction that matters:

- **Triggering** = POST to an actor's *trigger endpoint* to cause it to emit an
  activity (`POST /actors/{id}/trigger/invite-actor-to-case`). The actor decides
  and sends. Correct.
- **Mail-carrying** = POST an activity directly to another actor's *inbox* from
  outside that actor's own delivery path (`POST /actors/{id}/inbox/`). The demo
  bypasses the real transport. Wrong.

**Root cause of the pattern:** The inbox endpoint returns 202 immediately
(`BackgroundTasks`) before the activity is fully processed. Naive polling after a
trigger timed out, so mail-carrying was added as a workaround.

The fix is not a longer timeout — it is observing the *right thing*. Choose the
observable per EDF-06-002 and EDF-06-003 (the committed state of the actor that
produces the effect, read from its own container) and express it with
`demo_gate`. See [notes/event-driven-control-flow.md](event-driven-control-flow.md)
§ "Temporal Sequence vs. Causal Sequence".

**How to apply:**

1. After triggering an actor to emit an activity, do **not** manually deliver
   that activity to any inbox. Poll the expected side-effect directly:
   - `wait_for_case_on_container` — a case replica arrived.
   - `find_case_invite_for_actor` — an invite arrived.
   - `wait_for_object_stored` — an arbitrary object arrived in a DataLayer.
2. If a poll times out reliably in CI, the underlying delivery path needs
   investigation (retry parameters, health checks, container startup order) — not
   a workaround in the demo script.

**Scope — scenario demos, not exchange demos.** `vultron/demo/exchange/` drives a
single backend directly and uses `post_to_inbox_and_wait` as its normal
mechanism; there is no second container for the transport to cross. This rule
governs `vultron/demo/scenario/`, where actors live in separate containers and
the delivery path is the thing under test.

**No self-delivery exception.** An actor does not need to POST to its own inbox
to update its own replica either — activities route through the CASE_MANAGER, which
broadcasts the `Announce` that every replica consumes. See
[notes/ownership-transfer.md](ownership-transfer.md) § "The Accepting Actor's
Replica Updates via the CASE_MANAGER's Announce".

Source: CONCERN-1635, amended by CONCERN-2181

---

## Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before writing a **second use** of a pattern from an existing scenario file,
extract it to `vultron/demo/helpers/` first. Do not copy-paste a function body, a
polling loop, a verification block, or any other logical unit from an existing
scenario file into a new one.

**Why:** Every demo scenario written by copying the previous one propagates
latent bugs alongside valid patterns. Issue #1632 documented residual duplication
remaining after PR #1629 reactively extracted five helper modules. Copy-paste is
the root cause; extraction-first prevents the problem from recurring.

**How to apply:**

1. Before writing a new scenario step, grep `vultron/demo/helpers/` for an
   existing helper that covers the same pattern.
2. If one exists, import and call it. Do not inline a copy.
3. If none exists and this is the second occurrence of the pattern, extract it to
   the appropriate `helpers/` module first, then call it from both places.
4. A pattern that appears only once may stay inline, but add a comment marking it
   as a candidate for extraction when a second use arises.

This rule applies to scenario files in `vultron/demo/scenario/`. Exchange demos
under `vultron/demo/exchange/` are lower-level and may duplicate less when a full
helper would add more abstraction than value.

Normative: `specs/multi-actor-demo.yaml` DEMOMA-17-001 — a MUST-level
specialisation of the project-wide SHOULD rule CS-22-001 in
`specs/code-style.yaml`.

Source: ISSUE-1652

---

## BT Demo `main()` Must Be Callable With No Arguments

`[project.scripts]` entry points invoke `main()` with **no arguments**. Demo
modules that define `def main(args):` — where `args` is a required positional
parsed by an `if __name__ == "__main__"` block — fail immediately with
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
passes a `SimpleNamespace` via `_bt_args()`) while also being callable with zero
arguments from a console script.

**Always test the actual console script** (`PYTHONPATH= uv run <script>`) — not
just the module import — and clear the devcontainer's `PYTHONPATH=/app`
contamination. See [notes/devcontainer-tooling.md](devcontainer-tooling.md).

Source: ISSUE-1568

---

## Docker Compose Service Names Are Not Actor Names

The service names in `docker/docker-compose-multi-actor.yml` (`vendor`,
`coordinator`, `vendor2`, `case-actor`) were chosen to match the roles in the
first demo scenarios and do not need to match the CVD actor roles housed within
them. When designing a new multi-actor scenario:

- The **service name** is a docker-compose routing label. Reuse existing service
  names by remapping them to new semantic roles via `--env-file` or environment
  variable overrides — there is no requirement that a service named `vendor`
  contains a Vendor actor.
- The **actor name** (`VULTRON_*_BASE_URL` env var bindings, actor IDs seeded at
  startup) is the meaningful identity. Choose actor names to reflect their CVD
  role in the scenario, not the docker service name.
- Avoid adding new services just to get a new actor name. In multi-actor
  scenarios (FCCV, FVCV-handoff), the existing four services are reused with
  role-alias environment variable bindings; this keeps the CI service startup
  count constant.

**Future direction**: the service names may eventually be renamed to neutral
labels (`actor1`–`actor4`) so the compose file is scenario-agnostic (ISSUE-1786).
Until then, use the existing services with role-alias bindings.

Source: ISSUE-1216, plan/incoming/learnings/20260722-fccv-handoff-container-remapping.md

---

## A Helper That Extracts a Result Inside `demo_step` Must Return `Optional[T]`

`demo_step` (`vultron/demo/utils.py`) is a context manager that **suppresses
exceptions** so one failed step records itself without crashing the whole
scenario. Any demo helper that both wraps a `post_to_trigger` call in `demo_step`
*and* extracts a result ID from it therefore cannot promise a value — on failure
the `demo_step` swallows the error and control falls through with nothing
extracted. Such a helper MUST be typed `-> Optional[T]`, not `-> T`.

**Why:** The alternative — re-raising outside `demo_step` — would crash the
scenario even when the failure is non-fatal, defeating the whole point of the
context manager. So the suppression contract propagates outward: every caller
now has to treat the return as possibly-absent.

**How to apply:**

- Type any such helper `-> Optional[T]` (e.g. `participant_adds_note_to_case` in
  `vultron/demo/helpers/notes.py` returns `Optional[as_Note]`).
- In callers, treat `None` as "this step failed and `demo_step` already recorded
  it" — do not raise. Guard every `.id_` (or other attribute) access on the
  returned value.
- Skip dependent steps when the value is `None`, e.g. by making the next step's
  `in_reply_to` conditional on the prior result being present.

Source: ISSUE-2390

---

## A Raising `wait_for_*` Must Never Run Bare in a Scenario

Every `wait_for_*` (and equivalent verification) helper in `vultron/demo/`
raises `AssertionError` on timeout — that is the primitive's contract, and it is
correct for unit tests that assert the timeout. But inside a scenario a bare
raising call **crashes the whole run at the first failure**, which contradicts
the demo failure-accumulation model (DEMOCI-01-003 / DEMOCI-01-004,
DEMOCI-01-011): failures are supposed to accumulate through
`demo_step` / `demo_check` / `demo_gate` and surface together at the end via
`assert_demo_success()`. A bare raise stops the run before later checks execute,
burying any co-occurring failures behind a single misleading signal.

**Why this keeps happening:** the raising primitive and the accumulating
scenario are two different execution contexts, and it is easy to call the former
directly from the latter. It has now bitten the project twice:

- **Ledger coverage (#1772 / #1802):** bare `wait_for_contiguous_ledger_coverage`
  calls crashed sync-verification; fixed by wrapping them at the call site in
  `demo_gate` (see `test/demo/test_fvv_demo.py::TestCoverageWaitInsideDemoCheck`).
- **Participant waits (#3384):** the `wait_for_participants_on_replicas` calls in
  every replica-sync scenario's `_phase_sync_verification` were bare, so a
  replica participant-index propagation timeout aborted the entire run.

**How to apply:**

1. A raising wait invoked directly from scenario code MUST sit inside a
   `demo_step`, `demo_check`, or `demo_gate` — use `demo_gate` when dependent
   steps follow inside the block, `demo_check` for an independent bounded check.
2. **Prefer wrapping inside the shared helper** when one exists, so all callers
   inherit the fix (DRY). `drain_phase1_ledger` in
   `vultron/demo/helpers/polling.py` is the reference pattern: it wraps each
   per-replica poll in a demo context internally (lazy-importing the context
   manager from `vultron.demo.utils` to avoid a circular import). Note that when
   the wrap lives in the helper and the dependent steps live in the scenario,
   `demo_check` and `demo_gate` behave identically — the block contains only the
   wait, so nothing is skipped either way; pick the label that reads true.
3. Keep the raising primitive raising for its unit tests — add the accumulation
   wrap in a scenario-facing helper, not in the low-level `_poll_until` /
   `wait_for_case_participants` primitives that tests depend on.

Normative: `specs/demo-ci.yaml` DEMOCI-01-011, refining DEMOCI-01-003. An
architecture ratchet enforces that scenario `_phase_*` functions do not call a
known raising wait outside a demo context.

Source: CONCERN-3384 (generalising the #1772/#1802 fix)

---

## Replica Sync Verification Is One Shared Helper, Not a Per-Scenario Phase Body

Every multi-actor scenario needs the same guard between its report-submission
and notes phases: the Finder must hold the case replica, and every replica must
have contiguous ledger coverage up to the authority's tail. All but the
fcv-reject scenario then go on to wait for every replica's participant index and
to compare a couple of replicas against the authority's state. Every scenario
also needs the coverage half of that again after case closure, before the
ledger dump.

**Why this matters:** the concern that filed #3042 believed the pre-notes race
guard existed in fcv-reject only. It was in fact present everywhere — as one
copy per scenario module of the `_phase_sync_verification` body, plus one copy
per module of the post-closure coverage wait. That is why the race-window fix
in #2756 had to touch most of those modules, why the timeouts drifted (literals
of 15 s or 45 s by replica label in most modules, 30 s or 45 s in fcvcv
after #2337, and no timeout at all — so the primitive's own default — in fv,
fvv and fcv-reject), and why every scenario test file except fcv-reject's
carries the same "skip the coverage wait when the Finder case never arrives"
unit test. The guard was never missing; the single place to fix it was.

**How to apply:**

1. The read-authority-tail-then-poll-each-replica loop lives once, as
   `wait_for_replica_ledger_coverage` in `vultron/demo/helpers/sync.py`. It
   takes the authority client, an ordered list of `(replica_client, label)`
   pairs, the case id and the late-joiner clients; it applies the named timeout
   constants from `vultron/demo/helpers/polling.py` (`LEDGER_COVERAGE_TIMEOUT`
   by default, `LATE_JOINER_COVERAGE_TIMEOUT` for a late joiner — the widest
   budgets any copy carried, so sharing the loop tightened nothing) and wraps
   each per-replica wait in a demo context itself, the same way
   `wait_for_participants_on_replicas` and `drain_phase1_ledger` do. Called
   with `causal=True` (the default) it is the `demo_gate` before the notes
   phase; with `causal=False` and `phase_label="close phase"` it is the
   `demo_check` after case closure, labelled temporal per EDF-06-006. It
   returns the replicas whose wait passed, so a dependent step can be gated on
   coverage per replica.
2. A scenario's `_phase_sync_verification` is a thin call to
   `run_sync_verification_phase`, declaring only its authority (client, label,
   actor id), the Finder, its replicas, late joiners, expected participant set,
   and which replica pairs to state-check. A replica whose coverage gate failed
   is not state-checked: the gate already recorded the failure and the
   comparison would only cascade (EDF-06-005, #1911). An authority with no
   entries to cover is likewise one recorded failure naming the authority, and
   no replica is state-checked — the writer is at fault, not the fan-out, so
   the failure must not be left for a replica-side check to misattribute.
   Scenario-specific extras
   — the two-actor fv scenario's check that the dedicated case-actor container
   stayed unused — follow the helper call as separate steps. A scenario with no
   participant expectation (fcv-reject) declares none and no participant wait
   runs.
3. A scenario module never calls `wait_for_contiguous_ledger_coverage` or
   `_get_log_entries_for_case` directly (DEMOMA-23-006). The architecture
   ratchet `test/architecture/test_demo_scenario_coverage_via_shared_helper.py`
   fails if one does, on a call or an import.
4. Timeouts are named constants passed as parameters, never literals in a
   scenario file. The shared defaults already carry the widest budget any
   scenario needed (fcvcv's non-late-joiner replicas, #2337, are covered by
   `LEDGER_COVERAGE_TIMEOUT`); a scenario that needs another budget passes a
   different constant, and its regression test asserts the parameter the helper
   applies, not a literal.

Normative: `specs/multi-actor-demo.yaml` DEMOMA-23-005 (the shared coverage
helper), DEMOMA-23-006 (no direct primitive call from a scenario module), and
DEMOMA-23-007 (the thin phase), refining DEMOMA-17-001, DEMOMA-22-002, and
DEMOCI-01-011.

Source: CONCERN-3042, #3846

---

## Use ActorSession Typed Methods, Not `post_to_trigger` Directly (DEMOMA-26)

Once `ActorSession` is available (#3398), demo scripts under
`vultron/demo/scenario/` and `vultron/demo/exchange/` MUST use its typed methods
for all trigger endpoint calls. Calling `post_to_trigger` directly is prohibited
at those call sites (DEMOMA-26-001).

**Why:** `post_to_trigger` accepts a bare `str` behavior name and an untyped
`dict` body. A misspelled behavior name is a 404 at runtime; a misspelled body
key is silently dropped because trigger request models use `extra="ignore"`
(TRIG-03-002), producing an undetectable no-op. `ActorSession` makes both
mistakes unrepresentable at the call site.

**What changes on migration:**

- `vultron/demo/helpers/actions.py` is deleted; its wrappers become
  `ActorSession` methods (DEMOMA-26-005).
- The architecture ratchet test
  `test/architecture/test_demo_trigger_client_matches_actor.py` is deleted only
  after the last `post_to_trigger` call site is removed — it is the migration's
  own safety net until then (DEMOMA-26-006).

**Until `ActorSession` lands**, the existing `post_to_trigger`-based helpers in
`vultron/demo/helpers/` remain correct. The `Optional[T]` return-type rule in the
section above still applies to any helper that extracts a result from a
`post_to_trigger` call wrapped in `demo_step`.

Source: #3356, DEMOMA-26
