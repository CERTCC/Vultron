---
title: One Clock Read per Act — Migration Plan
status: active
kind: plan
tracks:
  - "#5676"   # epic: a re-recorded scenario equals the committed one
  - "#5757"   # slice 1: clock port, act entry points, tree-run instant, ratchet
  - "#5649"   # slice 2: tree builders and guard nodes (absorbed #5650)
  - "#5651"   # sync rate-limit checks and the replication-state key
  - "#5758"   # slice 4: core models and time helpers
  - "#5652"   # slice 5: the parse edge reads no clock
  - "#5760"   # slice 6: recordings through the port
  - "#5761"   # follow-on: generated ids through an id source
  - "#5848"   # follow-on: drift limit, after the call-out budget (#3423)
description: >
  The unbuilt migration to ADR-0174: each act reads the clock once at its edge,
  tree nodes read that instant from the tree run, and core code takes time as an
  argument and never reads or defaults it.
related_specs:
  - specs/code-style.yaml
  - specs/case-ledger-processing.yaml
---

# One Clock Read per Act — Migration Plan

ADR-0174 decides that an act (a trigger, the processing of one inbound delivery, or
a sweep) reads the clock once, at its entry point, and that everything below that
point takes the instant instead of reading the clock. The code does not do this
yet. This note holds the order of the work and the rules each slice keeps.

## Rules every slice keeps

- **Lock, then read.** An act takes the tree lock before it reads its instant
  and holds the lock until it commits, so queueing for the lock is not decision
  time. A trigger's checks before its tree run inside that lock.
- **A stopwatch is not the clock.** Elapsed-time limits read a separate
  monotonic port at named sites; a stopwatch reading never reaches a decision
  about the case or a record, so the architecture test allows it.
- **No fallback to the clock.** A parameter that carries the act's instant is
  required, never `datetime | None` with an `or now_utc()` default, because that
  fallback is the defect being removed (ARCH-10-001).
- **A tree node reads the instant from the tree run.** Builders and node
  constructors take no time; a node that ticks without the instant fails.
- **A received activity is judged at processing time.** A held activity replayed
  later gets its replay's instant; its arrival time stays its own recorded fact.
- **Ordered stamps keep the microsecond bump.** Stamps written by one act share
  its instant, so the smallest step past the previous stamp is what orders them
  (ADR-0167).
- **A verdict does not change.** Each migrated decision gives the same answer for
  the same instant as before; a slice that changes a verdict is a behavior change
  and needs its own issue.
- **A CS-13 rule is restated with the slice that meets it.** CS-13-002 and
  CS-13-004 name the current clock helpers; each is rewritten in the PR whose test
  verifies the new form, not before.

## Slices, in order

1. **Foundation** (#5757). The clock port, the act entry points, the tree-run instant, and
   the architecture test with today's clock reads recorded item by item as the
   list to burn down.
2. **Tree builders and guard nodes** (#5649). Mostly
   deletions of time parameters and their fallbacks.
3. **Sync checks** (#5651). Cooldown and resend predicates take the instant; the
   replication-state key is derived without building a stamped model.
4. **Core models** (#5758). No core model field defaults to the clock; the ordered-stamp
   and deadline helpers take the instant. The widest change, because test fixtures
   need an explicit time.
5. **Parse edge** (#5652). The RSVP computation takes `published` as required
   (CLP-15-008 already refuses an inbound activity without it), and the
   past-deadline warning moves to the handler. The pre-bootstrap queue sweep moves
   to the reap trigger (#2887).
6. **Recordings** (#5760). The recording clock goes through the port and steps once per
   act; the clock patch in the recording harness is removed; every recording is
   regenerated once.

Generated ids follow the same pattern in a later decision (#5761); they are not
part of this plan.
