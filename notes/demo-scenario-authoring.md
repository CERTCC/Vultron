---
title: Demo Scenario Authoring Rules
status: active
kind: guidance
description: >
  How to write a multi-actor demo scenario without faking the protocol:
  puppeteer actors through trigger endpoints rather than spoofing via inbox
  injection, never carry one actor's mail to another's inbox, extract helpers
  before the second use, call triggers through `ActorSession`, keep
  console-script entry points callable with no arguments, run every scenario on
  one fixed cast of role-neutral container slots, keep raising waits inside a
  demo context, give two milestones in a row two different assertions, share the
  replica-sync phase, and close every case with the Case Owner leaving last.
related_specs:
  - specs/case-bootstrap-trust.yaml
  - specs/cs-behavior.yaml
  - specs/demo-ci.yaml
  - specs/multi-actor-demo.yaml
  - specs/event-driven-control-flow.yaml
  - specs/code-style.yaml
  - specs/case-management.yaml
related_notes:
  - notes/event-driven-control-flow.md
  - notes/demo-ci-diagnostics.md
  - notes/demo-ci-invariants.md
  - notes/demo-scenario-registry.md
  - notes/case-proposal.md
  - notes/ownership-transfer.md
  - notes/devcontainer-tooling.md
  - notes/activitystreams-semantics.md
  - notes/architecture-ratchet-corpus.md
relevant_packages:
  - vultron/demo
---

# Demo Scenario Authoring Rules

`vultron/demo/AGENTS.md` keeps the one-line rules; this note holds the reasons
and the application details. The through-line: a demo exists to prove the
protocol works, so any shortcut that does the protocol's job *for* it turns the
demo from evidence into decoration.

The scope is `vultron/demo/scenario/` and the `vultron/demo/helpers/` code a
scenario calls. Exchange demos under `vultron/demo/exchange/` drive one backend
directly and are exempt where noted.

---

## Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

Drive actor behavior only through real trigger endpoints
(`POST /actors/{id}/trigger/{behavior}`, or `.../demo/{behavior}`). Never build
an activity and POST it to an inbox to fake a decision or state change.

**Why:** **puppeteering** makes the actor decide and act, which exercises the
behavior tree; **spoofing** forges the result and skips the tree, so the demo
proves nothing about it (DEMOMA-05-001).

**How to apply:** before writing a step where one actor responds to another,
check the trigger endpoint exists. If it does not, build the full stack
(endpoint → service → BT) first, then the step.

**Report submissions too, in every demo.** Submit a report only through
`reporter_submits_report` (`helpers/workflow/report.py`), exchange demos included, and
never build a `Create(VulnerabilityCase)` for the receiver.

- **Why:** the reporter's `submit-report` trigger writes the pending
  `ReportCaseLink` naming the receiver (CBT-01-005). An Offer posted straight
  to the receiver's inbox leaves the reporter no anchor, so it refuses the
  receiver's case introduction (CBT-01-011). The demo still passes when the
  reporter gets a case another way, so the defect stays hidden (#4675).
- **How to apply:** once the case exists, call
  `verify_reporter_trusts_introduction`, passing `case_id` when the demo
  knows which case the receiver opened, or the check cannot tell that case
  from any other. Its test wraps the run in
  `expect_trusted_introductions` (`test/demo/_helpers.py`).
  `test/architecture/test_demo_reports_submitted_through_trigger.py` fails on
  any reference to `rm_submit_report_activity` or `create_case_activity` under
  `vultron/demo/`.

---

## Never Carry One Actor's Mail to Another Actor's Inbox

A scenario MUST NOT POST an activity to any actor's inbox on another actor's
behalf, directly or through a helper such as `post_to_inbox_and_wait`.

**Why:** delivery is the transport's job. Hand delivery skips the
outbox → delivery → inbox path, which is the thing a multi-container demo tests.
It also double-delivers when the real delivery succeeds too (#3980).

**How to apply:**

1. After a trigger, wait on the effect, never re-deliver the activity. Choose the
   observable per EDF-06-002/003 — the committed state of the actor that produces
   the effect, read from its own container — and gate on it with `demo_gate`
   (see [event-driven-control-flow.md](event-driven-control-flow.md)
   § "Temporal Sequence vs. Causal Sequence"). The polling helpers are in
   `vultron/demo/helpers/polling/`, `invite_chain/` and `milestones/`.
2. A wait that times out reliably in CI points at the delivery path (retries,
   health checks, startup order), not at the demo script.
3. There is no self-delivery exception: an actor's own replica updates from the
   CASE_MANAGER's `Announce` like everyone else's (see
   [ownership-transfer.md](ownership-transfer.md) § "The Accepting Actor's
   Replica Updates via the CASE_MANAGER's Announce").

Exchange demos use `post_to_inbox_and_wait` as their normal mechanism: they have
no second container for the transport to cross. It hands each activity to the
sender's own outbox on the backend, which signs it as its owner (SIG-05-004) and
delivers it, so demo code never signs.

---

## Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before the **second** use of a pattern from an existing scenario — a function
body, polling loop or verification block — extract it to `vultron/demo/helpers/`
and call it from both places (DEMOMA-17-001, the MUST-level form of CS-22-001).

**Why:** a scenario written by copying the previous one copies its latent bugs.

**How to apply:**

1. Grep `vultron/demo/helpers/` for a helper before writing a step.
2. If the second use differs, parameterize the helper; differing variants are a
   design task, not a reason to skip. `run_case_invite_chain`
   (`helpers/invite_chain/`) is the model: the variants are parameters and what
   follows is a `then` callback. It is a callback, not a `with` block, because
   `demo_gate` suppresses an exception before a generator-based context manager
   could yield. `test_demo_scenarios_use_invite_chain_helper.py` enforces it.
3. A consolidation must not change what a demo reports as pass or fail (#4192).

---

## Call Triggers Through `ActorSession`

Scenario and exchange demos make every trigger call through `ActorSession`
(`vultron/demo/actor_session/`) typed methods, never `post_to_trigger`
(DEMOMA-26-001, DEMOMA-26-007).

**Why:** `post_to_trigger` takes a bare behavior string and an untyped body. A
misspelled behavior is a runtime 404, and a misspelled body key is silently
dropped by the `extra="ignore"` request models (TRIG-03-002), so the call is an
undetectable no-op.

---

## BT Demo `main()` Must Be Callable With No Arguments

`[project.scripts]` entry points call `main()` with no arguments, so a BT demo's
`main` takes `args=None` and falls back to `_parse_args()`. That keeps both the
console script and `vultron/demo/cli/`'s click group (which passes a
`SimpleNamespace` from `_bt_args()`) working.

**Why:** `def main(args):` fails with `TypeError` under `uv run <script>` while
every import-level test passes. Test the real console script with
`PYTHONPATH= uv run <script>` (see
[devcontainer-tooling.md](devcontainer-tooling.md)).

---

## Every Scenario Runs on the Fixed Cast

The containers in `docker/docker-compose-multi-actor.yml` are the cast:
role-neutral slots declared once in `vultron/demo/helpers/cast.py`, with one
address and one actor id per slot in every scenario (DEMOCI-11-020).

- **Seat an actor, do not add a container.** A new part takes a free cast slot
  through its `ActorRole(name, slot, title)`; a new service would change the CI
  startup count and give the tree a second set of addresses.
- **Slots 0, 1 and 2 are the first Reporter, Vendor and Coordinator**, and a
  scenario that seats none of one leaves that slot idle. Slots 3 and up are
  character actors: their CVD role comes from the act that seats them, so their
  container declares no `VULTRON_ACTOR__DEFAULT_CASE_ROLES` (DEMOCI-11-021).
- **Name actors for the part they play here, not for the slot.** `rcv`'s
  `coordinator` and `rcvcv`'s `c1` are the same container. A devlog directory
  is a separate choice and not always the part: the `rccv-*` scenarios keep
  RVCV-legacy directory names (`vendor` is C1, `coordinator` is C2), which the
  invariant harness pins — see
  [demo-ci-invariants.md](demo-ci-invariants.md) § "Harness File Conventions"
  before renaming one.
- **A scenario declares no URL, port or actor id.** They are the slot's; a
  scenario that needs a different id passes `--<name>-id`. Growing the cast is
  a `CAST_SIZE` change, and `test/demo_unit/test_cast.py` fails until the
  compose file and seed configs follow.

---

## A Helper That Extracts a Result Inside `demo_step` Must Return `Optional[T]`

`demo_step` (`vultron/demo/utils/failures.py`) suppresses exceptions so a failed step
records itself without ending the run. A helper that wraps a trigger call in
`demo_step` and extracts a result from it cannot promise a value, so it is typed
`-> T | None` (e.g. `participant_adds_note_to_case` in `helpers/notes.py`).

**How to apply:**

- **Prefer nesting over a sentinel.** Put every step that reads the value inside
  the `demo_step` / `demo_gate` body that produces it (ADR-0058), so a failed
  block skips its dependents. Do not pre-set the name to `None` and read it after
  the block: that satisfies the unbound-variable ratchet but hands `None` to the
  next step, which then fails for the wrong reason (#3887). A step that reads
  nothing but must run *between* two that do nests with them: nesting changes
  execution order, so leaving it outside would move it after the whole group.
- **Give each nested statement its own `demo_check` or `demo_step` — unless the
  callee already opens its own block.** A bare call records its failure under
  the producer's name, which is the mis-blame the rule above exists to remove.
  A helper that wraps its own body in a `demo_check` already names and records
  that failure, and `demo_check` suppresses, so an outer block around it can
  never fail: it logs ✅ beside the callee's ❌ for the same act. Check the
  callee before wrapping (`verify_reporter_trusts_introduction` in
  `helpers/workflow/report.py` is one that opens its own). **This bullet is a
  convention; no check enforces it** — read the callee, do not rely on CI.
- Where the reader cannot be nested (the value crosses a story fragment
  boundary), treat `None` as "already recorded as failed": do not raise,
  guard each attribute access, and skip the dependent steps.

`test/architecture/test_demo_step_no_unbound_ratchet.py` enforces the first
bullet over **all** of `vultron/demo/`, `exchange/` included — the scope line
above bounds this note's other rules, not this ratchet. Its unbound check
reports a name assigned only inside a demo block and read after it (#2308);
its sentinel check reports a name pre-initialised to `None` or `""`, assigned
inside a demo block, then read after it with no guard before that first read
(#3038). A **read** is the name passed to a call — inside a `dict`, `list` or
f-string argument counts — an attribute or subscript of it, or iterating or
calling it. A **guard** is any test that is false for a placeholder: `is None`,
`is not None`, `== ""`, `== "ok"` and `is True` (equality with any constant
proves the name is neither `None` nor `""`, while `!= "ok"` proves nothing), a
truthiness test, or a rebinding. The first guard in evaluation order defends
every read after it, so the `if x is None: raise` shape this section asks for
satisfies the check without enclosing the reads. Dropping the guard means
nesting the reader.

---

## A Raising `wait_for_*` Must Never Run Bare in a Scenario

Every `wait_for_*` helper raises `AssertionError` on timeout; that contract is
right for unit tests. In scenario code, call one only inside `demo_step`,
`demo_check` or `demo_gate` (DEMOCI-01-011).

**Why:** demo failures accumulate through the demo contexts and surface together
in `assert_demo_success()` (DEMOCI-01-003). A bare raise ends the run at the
first failure and hides every co-occurring one.

**How to apply:**

1. Use `demo_gate` when dependent steps follow in the block, `demo_check` for an
   independent check.
2. Prefer putting the wrap inside a shared scenario-facing helper so every caller
   inherits it, as `wait_for_replica_ledger_coverage` (`helpers/sync/ledger.py`) and
   `wait_for_participants_on_replicas` (`helpers/polling/case.py`) do.
3. Keep the low-level primitives raising; their unit tests depend on it.

`test/architecture/test_demo_scenario_waits_in_demo_context.py` enforces the rule
for scenario-level code, which is a composed story's fragments: the callables
taking a `StoryState`, wherever they live. It keeps a `_phase_*` arm and
asserts no scenario has one, so a hand-written phase is reported rather than
silently exempt (#5536).

---

## Two Milestones in a Row Assert Two Different Things

A scenario that reports two milestone labels back to back owes each of them its
own assertion, and each label describes only what its own block reads.

**Why:** every vendor-first scenario reported two fix-ready milestones whose
bodies were identical, so the second proved nothing the first had not, and
wherever the label said "both vendors" the body read Vendor1 twice (#5602). A
green run then says less than its labels do, which is how a demo stops being
evidence.

**How to apply:**

1. Pass each label as its own named argument, not as a sequence a loop walks:
   `the_fix_ready_milestones(state, reached=…, stopped=…)` cannot be handed one
   body twice.
2. Say what the second one adds. "Stops at VFd" is a claim about the d→D
   transition that never happens, so it reads the absence of `D`
   (`verify_stops_at_fix_ready`), not the VF state its sibling already read.
   State the absence, not `d_state == d`: a participant holding no DEPLOYER
   role carries no `d` dimension at all, so pinning the expected set to `d`
   fails on the very shape the claim is about. A negative assertion needs no
   polling wait either — what holds it is the role guard the DEPLOYER gate
   rests on (CSB-15-002, DEMOMA-15-004), not a timeout.
3. Read every participant the label names. A label naming both vendors reads
   both, because each vendor's fix path is its own (DEMOMA-09-009).
4. Hold it with a test that compares the two halves' reads *each way*: a half
   whose reads are a **subset** of the other's asserts nothing new even though
   the two lists are unequal. Key each read on the helper, the container read
   and the actor read about — the name alone lets a rewrite read the right
   thing about the wrong actor (`recorded_milestone_reads` in
   `test/demo/_helpers.py`, used by both families' continuation tests). The
   key names the helper, so what each helper's own body asserts is held one
   level down, by `test/demo/test_milestones_vendor_guard.py`.

---

## Replica Sync Verification Is One Shared Helper, Not a Per-Scenario Phase Body

Every multi-actor scenario guards its notes phase on the Reporter holding the case
replica and every replica holding contiguous ledger coverage. That logic exists
once.

- `wait_for_replica_ledger_coverage` (`helpers/sync/ledger.py`) is the only
  read-authority-tail-then-poll-replicas loop, the `demo_gate` before the notes
  phase and the Phase 1 drain. It returns the replicas whose wait passed, so
  later steps can gate per replica. It is never used after closure: a closed
  participant is sent nothing after the entries recording its own closure
  (CM-23-004), so no replica covers the authority's tail then.
- A scenario's sync-verification step — a story fragment named
  `replicas_converge_with_vendor`, `every_replica_converges` or
  `the_reporter_replica_converges` — is a thin call to
  `run_sync_verification_phase`,
  declaring only its authority, Reporter, replicas, late joiners, expected
  participants and the replica pairs to state-check (DEMOMA-23-007). A replica
  whose coverage gate failed is not state-checked, and an authority with no
  entries is one failure naming the authority — the comparison would only
  cascade or misattribute the fault (EDF-06-005).
- No module under `vultron/demo/` except the `helpers/sync/` package calls
  `wait_for_contiguous_ledger_coverage` or `_get_log_entries_for_case`
  (DEMOMA-23-006, enforced by
  `test/architecture/test_demo_scenario_coverage_via_shared_helper.py`).
- Timeouts are the named constants in `helpers/polling/_poll.py`
  (`LEDGER_COVERAGE_TIMEOUT`, `LATE_JOINER_COVERAGE_TIMEOUT`), passed as
  parameters, never literals in a scenario. Each is a stall budget, not a
  total: every newly arrived entry restarts it, up to
  `BACKFILL_PROGRESS_CEILING`, so a long backfill under CI load is waited for
  and a stalled one fails (#4424).

**Why:** one copy per scenario module is how the timeouts drifted apart and why
one race fix had to touch most modules (DEMOMA-23-005).

---

## Close a Case Through `close_case_owner_last`, Owner Last

The Case Owner's `Leave(VulnerabilityCase)` closes the case for everyone
(CM-23-002), and the CASE_MANAGER records nothing a participant sends after its
own `RM.CLOSED` status entry (CM-23-013). So the owner leaves last (CM-23-015).

Every closure phase calls `close_case_owner_last` (`helpers/closure.py`). The
other participants leave first; the owner's `Leave` waits until the
CASE_MANAGER's store shows each of them at `RM.CLOSED`, because a trigger returns
202 before its effect commits (EDF-06-002). It also waits until the owner's own
replica reads the CASE_MANAGER's EM state: `leave-case` refuses the owner while
its replica records an active embargo (TRIG-13-003). The helper then runs the whole
closure milestone, each part in its own `demo_check` and read where the
CASE_MANAGER lives: `verify_case_closure_recorded` and `verify_case_closed`
(`helpers/milestones/closure.py`), and, for each leaver, that its own replica ends
at the last entry recording its own closure (`wait_for_replica_ledger_ending_at`).
Pass the scenario's milestone label; the scenario adds no closure checks of its own.

- Do not write the `leave_case()` steps inline.
- Do not add an "every participant `RM.CLOSED` on every replica" check or a
  close-phase coverage wait on the CASE_MANAGER's tail: a closed replica is
  never sent the later closures (CM-23-004).
- Name the participant that holds `CASE_OWNER` at closure; after a handoff it is
  not the case's creator.
- Each narrative under `docs/topics/scenarios/` declares a
  `close_case → close_case` causal edge whose `consequent_actor` is the owner;
  `test/ci/invariants/test_narrative_edges.py` checks that it rejects an
  owner-first closure.
