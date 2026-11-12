---
title: One Clock Read per Act
status: active
kind: plan
tracks:
  - "#5676"   # epic: a re-recorded scenario equals the committed one
  - "#5848"   # follow-on: drift limit, after the call-out budget (#3423)
description: >
  The rules of ADR-0176, now that no code below an act's edge reads the
  clock: an act reads it once at its edge, a received message at its
  arrival, and carries it as /at; tree nodes read that instant from the tree
  run, core code takes time as an argument, and a recording supplies its
  clock through the port. Follow-on: the drift limit.
related_specs:
  - specs/code-style.yaml
  - specs/case-ledger-processing.yaml
  - specs/architecture.yaml
  - specs/case-bootstrap-trust.yaml
---

# One Clock Read per Act

ADR-0176 decides that an act (a trigger, the processing of one inbound delivery, or
a sweep) reads the clock once, at its entry point, and that everything below that
point takes the instant instead of reading the clock. The act entry points, the
clock port and the tree-run instant exist, and no code below an act's edge reads
the clock. This note holds the rules new code keeps and the follow-ons the epic
(#5676) still tracks.

## Rules new code keeps

- **Lock, then read — except a received message.** A trigger or sweep takes the
  tree lock before it reads its instant and holds the lock until it commits, so
  queueing for the lock is not decision time. A trigger's checks before its tree
  run inside that lock. A received message's instant is its arrival stamp,
  read before it queues (next rule).
- **A received message is judged at its arrival stamp.** The
  inbox route reads the act clock once on arrival (`stamp_arrival`, through the
  `get_act_clock` dependency), before any lock, and every act that processes the
  message runs at that stamp (`process_payload(..., arrived_at=)`,
  `open_received_act`), because a backlog the sender cannot see must not make an
  on-time answer late. The stamp is the record's `received_at`: intake, every
  hold and a receipt stub write it, a hold of a released record keeps it, and a
  replay, retry or restart re-run runs at it. Never re-stamp a held message, and
  never use the releasing act's instant for its replay.
- **Queue expiry is judged by the act that releases or sweeps.** The
  pre-bootstrap window opens at the first waiter's arrival stamp and has expired
  once that plus the interval is not after the judging act's instant (a later
  delivery or the bootstrap, at its arrival stamp; a sweep, at its own), so a
  bootstrap that arrived inside the window releases the queue however late it
  runs; a released message is not judged again at its replay (CBT-03-003).
- **A stopwatch is not the clock.** Elapsed-time limits read a separate
  monotonic port at named sites; a stopwatch reading never reaches a decision
  about the case or a record, so the architecture test allows it.
- **Bookkeeping has its own clock.** Adapter bookkeeping times (queued,
  dead-lettered) read a separate bookkeeping port, never the act clock, so the
  recording clock steps once per act and a bookkeeping read moves no recording.
- **No model defaults a time.** An object's author times are required, and
  whatever builds it states the act's instant: a node through
  `_require_act_instant()`, anything else through a required argument; every
  outbound factory and port method that builds an activity takes `at` (#5758,
  `notes/datalayer-design.md` § "A Time Is Stated by Its Author").
- **No fallback to the clock.** A parameter that carries the act's instant is
  required, never `datetime | None` with an `or now_utc()` default, because that
  fallback is the defect being removed (ARCH-10-001).
- **A tree node reads the instant from the tree run.** Builders and node
  constructors take no time; a node that ticks without the instant fails, because
  a time passed at build would be read before the lock, not at decision time.
  Only the outermost run of an act takes the instant; a nested run inherits it.
- **Ordered stamps keep the microsecond bump.** Stamps written by one act share
  its instant, so the smallest step past the previous stamp is what orders them
  (ADR-0167, CM-29-005).
- **A verdict does not change.** Each migrated decision gives the same answer for
  the same instant as before; a change that moves a verdict is a behavior change
  and needs its own issue.
- **A CS-13 rule is restated with the change that meets it.** CS-13-004 and
  CS-13-008 name the current clock helpers; each is rewritten in the PR whose test
  verifies the new form, not before, as CS-13-002 was with the port (#5757).

## How to build on it

- **Read the instant in a node with `self._require_act_instant()`**, in
  `update()`, never at build. Both ports bases declare the optional `at` port
  remapped to `/at` (BTND-03-001); code outside a ports node calls
  `read_act_instant()` (`vultron/core/behaviors/bridge/act_instant.py`). Both
  raise `VultronMissingActInstantError` when the run carries no `/at`, which the
  bridge reports as an internal error, so a missing instant is never answered by
  a clock read (ARCH-10-001).
- **A test runs a use case or a tree through `test/support/act_runner.py`**:
  `run_in_act(use_case, at=...)`, `run_tree(bridge, tree, ..., at=...)` or
  `run_dispatch(dispatcher, event, dl, at=...)`, and a trigger takes
  `FixedClock(at)` because it opens its own act. A direct `.execute()`,
  `execute_with_setup` or `.dispatch(event, dl)` call skips the act, so a node
  that reads the instant fails; `test_tests_run_acts_through_the_runner.py`
  refuses one. A nested run takes no `at`; one that passes a different instant
  fails.
- **No clock read is left below an act's edge.**
  `test/architecture/test_clock_reads_at_act_edge.py` lists each permitted
  read as `(path, scope, read)` in `CLOCK_EDGE_EXEMPTIONS`, a pinned exemption
  set, and fails on any other; a new module that holds a clock goes in
  `CLOCK_HOLDER_EXEMPTIONS`, because it is an act's entry point or the
  composition root that wires one.
- **A trigger or sweep entry point opens the act with `open_act(clock)`** and
  takes the `ClockPort` from its composition root (`vultron/core/ports/clock.py`),
  which gets it from `act_clock()` in `vultron/adapters/driven/clock.py`: the
  system clock, or the clock a recorded run installed with
  `install_act_clock` (#5760). A demo client's step reads the same clock
  through `vultron.demo.wall_clock.now`. Today's:
  `SvcBTTriggerBase.execute`, the participant-role trigger,
  `state_ledger_positions_trigger` and the sender-sequence hold sweep. A
  received message's act opens with `open_received_act(arrived_at)` instead:
  `process_payload` and `handle_inbox_item`.

## Follow-ons

- **Drift limit** (#5848, after the call-out budget #3423): an act whose
  stopwatch time since it took the lock exceeds a budget aborts before it
  commits and reruns, so a long call-out cannot leave a stale instant.

Generated ids are not part of this plan. ADR-0185 decides them differently: the one
minter draws from an id-source port, and ids are not threaded to the act's edge
(`notes/id-source.md`).
