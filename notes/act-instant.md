---
title: One Clock Read per Act — Migration Plan
status: active
kind: plan
tracks:
  - "#5676"   # epic: a re-recorded scenario equals the committed one
  - "#5649"   # slice 2: tree builders and guard nodes (absorbed #5650)
  - "#5651"   # slice 3: sync rate-limit checks and the replication-state key
  - "#5758"   # slice 4: core models and time helpers
  - "#5652"   # slice 5: the parse edge reads no clock
  - "#5760"   # slice 6: recordings through the port
  - "#5761"   # follow-on: generated ids, decided in ADR-0185
  - "#5848"   # follow-on: drift limit, after the call-out budget (#3423)
  - "#6191"   # a received message's instant is its arrival stamp
description: >
  The remaining migration to ADR-0176: acts already read the clock once at
  their edge, a received message at its arrival, and carry it
  as /at; tree nodes still to move read that instant from
  the tree run, and core code takes time as an argument and never reads or
  defaults it.
related_specs:
  - specs/code-style.yaml
  - specs/case-ledger-processing.yaml
  - specs/architecture.yaml
  - specs/case-bootstrap-trust.yaml
---

# One Clock Read per Act — Migration Plan

ADR-0176 decides that an act (a trigger, the processing of one inbound delivery, or
a sweep) reads the clock once, at its entry point, and that everything below that
point takes the instant instead of reading the clock. The act entry points, the
clock port and the tree-run instant exist (#5757); the reads below the edge do
not use them yet. This note holds the order of the work and the rules each slice
keeps.

## Rules every slice keeps

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
  the same instant as before; a slice that changes a verdict is a behavior change
  and needs its own issue.
- **A CS-13 rule is restated with the slice that meets it.** CS-13-004 and
  CS-13-008 name the current clock helpers; each is rewritten in the PR whose test
  verifies the new form, not before, as CS-13-002 was with the port (#5757).

## What the later slices build on

- **Read the instant in a node with `self._require_act_instant()`**, in
  `update()`, never at build. Both ports bases declare the optional `at` port
  remapped to `/at` (BTND-03-001); code outside a ports node calls
  `read_act_instant()` (`vultron/core/behaviors/bridge/act_instant.py`). Both
  raise `VultronMissingActInstantError` when the run carries no `/at`, which the
  bridge reports as an internal error, so a missing instant is never answered by
  a clock read (ARCH-10-001).
- **A test runs a use case or a tree through `test/support/act_runner.py`**:
  `run_in_act(use_case, at=...)` or `run_tree(bridge, tree, ..., at=...)`, and
  a trigger takes `FixedClock(at)` because it opens its own act. A direct
  `.execute()` or `execute_with_setup` call skips the act, so a node that reads
  the instant fails; `test_tests_run_acts_through_the_runner.py` refuses one. A
  nested run takes no `at`; one that passes a different instant fails.
- **Delete your own lines from the ratchet.**
  `test/architecture/test_clock_reads_at_act_edge.py` lists each read as
  `(path, scope, read)` under the constant whose `# owner:` is your slice; a read
  no slice names is under `KNOWN_UNSLICED_CLOCK_READS` (`# owner: #5676`) until
  the epic routes it. A permitted edge read goes in `CLOCK_EDGE_EXEMPTIONS`, and
  a new module that holds a clock in `CLOCK_HOLDER_EXEMPTIONS`.
- **A trigger or sweep entry point opens the act with `open_act(clock)`** and
  takes the `ClockPort` from its composition root (`vultron/core/ports/clock.py`;
  the system clock is `vultron/adapters/driven/clock.py`). Today's:
  `SvcBTTriggerBase.execute`, the participant-role trigger,
  `state_ledger_positions_trigger` and the sender-sequence hold sweep. A
  received message's act opens with `open_received_act(arrived_at)` instead:
  `process_payload` and `handle_inbox_item`.

## Slices, in order

1. **Foundation** (#5757). The clock and bookkeeping-clock ports, the act entry
   points, the tree-run instant, and the architecture test with today's clock
   reads recorded item by item as the list to burn down.
2. **Tree builders and guard nodes** (#5649). Mostly deletions of time parameters
   and their fallbacks.
3. **Sync checks** (#5651). Cooldown and resend predicates take the instant; the
   replication-state key is derived without building a stamped model.
4. **Core models** (#5758). No core model field defaults to the clock; the
   ordered-stamp and deadline helpers take the instant. The widest change, because
   test fixtures need an explicit time. Update `notes/datalayer-design.md`
   § "A Clock-Minted Default Cannot Round-Trip" in the same PR.
5. **Parse edge** (#5652). The RSVP computation takes `published` as required
   (CLP-15-008 already refuses an inbound activity without it), and the
   past-deadline warning moves to the handler. The pre-bootstrap queue sweep moves
   to the reap trigger (#2887), judging at its own instant; the queue's two clock
   reads already moved to the act's instant (#6191).
6. **Recordings** (#5760). The recording clock goes through the port and steps
   once per act; the clock patch in the recording harness is removed; every
   recording is regenerated once. Update the recording-clock paragraph in
   `notes/demo-scenario-tree.md` in the same PR.

Generated ids are not part of this plan. ADR-0185 decides them differently: the one
minter draws from an id-source port, and ids are not threaded to the act's edge
(`notes/id-source.md`).
