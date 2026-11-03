---
status: proposed
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-03
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #5676, #5591, #5649, #5650, #5651, #5652, #2887;
  ADR-0032, ADR-0103, ADR-0167; specs/code-style.yaml CS-13;
  specs/case-ledger-processing.yaml CLP-15
informed: []
stakeholder_type: [project-contributor]
---

# An Act Reads the Clock Once, at Its Edge

## Context and Problem Statement

Any code in the application may read the clock, and much of it does.
Decision nodes compare a deadline with a fresh clock read, tree builders read the clock when a caller passes no time, domain models stamp themselves at construction, and helpers that compute a deadline or an ordered stamp hide a clock read inside them.

Two problems follow from that one cause.

- **One act sees several "nows".** A guard decides at one instant that a deadline has not passed, and the commit that follows is stamped at a later one, which may be after the deadline.
  The decision and the record of it disagree about when the act happened.
- **A demo recording is not reproducible.** The recording clock (`SteppingClock`) steps on every read, so a read on a path that writes nothing still moves every later timestamp and hash.
  #5591 fixed one such read; its audit found the same shape in tree builders, guard nodes, sync rate-limit checks and the inbound parse (#5649–#5652).

Fixing each read where it is found leaves the cause in place, so the next node that reads the clock repeats the defect.
Where does time enter the application, and how does code below that point learn the time?

## Decision Drivers

- One act must decide and record against one instant, so its decisions and its stamps agree.
- A read that commits nothing must not change what a recording contains.
- A missing time must fail fast, never be filled in silently (ARCH-10-001), because a silent fallback is how the current defects arose.
- Several stamps written by one act must still sort in the order they were written (ADR-0167).
- A time a peer sent is carried, never minted (ADR-0103, CLP-15-007, CLP-15-008).
- The rule must be enforced by a test, not by audits.

## Considered Options

1. **Fix each read where it is found.** Give each site its own injected time, issue by issue.
2. **One instant per act, passed as an argument everywhere.** Every builder, node, helper and model that needs time takes a required argument.
3. **One instant per act, read at the act's edge; a tree's nodes read it from the tree run's shared state; everything else takes it as an argument.**

## Decision Outcome

Chosen option: "One instant per act, read at the act's edge", because it removes the cause rather than the symptoms and needs no signature change through every received handler and trigger.
Option 1 has already produced four issues, and nothing stops a fifth.
Option 2 meets every driver but threads a time through every tree builder and every nested tree run by hand, which is the change #5649 judged too wide to make.

The decision has six parts.

- **An act and its instant.** An act is one trigger invocation, the processing of one inbound delivery, or one scheduled sweep.
  Each act reads the clock exactly once, at its entry point, and that reading is the act's instant.
  Every decision the act takes compares against it, and every time the act records is derived from it.
- **A received activity is judged when it is processed.** The instant of a received activity's act is the time it is applied, not the time it arrived.
  A held activity replayed later gets the instant of its replay, so an expiry is judged at the moment its effect lands.
  The arrival time stays its own recorded fact.
  The held activity itself is replayed as it arrived; only the decision time is new.
- **Trees read the instant from the tree run.** The bridge that runs a tree will take the act's instant as a required argument and place it in the run's shared state, beside the data layer and the leadership check.
  A nested tree run will inherit it, as it inherits the leadership check, so a nested run sees the same instant as the act that started it.
  A node will read the instant when it ticks and fail if it is absent.
  Tree builders and node constructors take no time.
- **Core code takes time, never reads it.** Below the act's edge, a helper or model that needs time takes it as a required argument.
  A domain model has no field whose default reads the clock.
  An ordered stamp is computed from the act's instant and the previous stamp, and the smallest step past the previous stamp keeps two stamps of one act in order.
  A deadline is the act's instant plus a duration.
- **The parse edge reads no clock.** Parsing and extraction carry the times a peer sent and compute nothing from the clock.
  An inbound activity without `published` is already refused at parse (CLP-15-008), so a computation that measures from `published` will take it as required.
  A check that needs the current time, such as whether a deadline has already passed, belongs to the handler, which holds the act's instant.
  Clean-up of expired entries is an act of its own, not a step of receiving (#2887).
- **The clock is injected.** The clock is a port with one operation, the current time, that the composition root supplies: the system clock in production and a recording clock in a recorded run.
  Only act entry points and adapter bookkeeping will hold it.
  Adapter bookkeeping times, such as when a delivery was dead-lettered, are infrastructure times read through the same port; they do not enter the case ledger and are not an act's instant.

This decision covers time only.
Generated ids have the same shape, a global that the recording harness replaces, and are left to a follow-on decision.

### Consequences

- Good: one act's decisions and records agree on when it happened.
- Good: a read that commits nothing no longer moves a recording, and the recording clock steps once per act, so one tick means one act.
- Good: the per-site fallbacks and their time parameters are deleted rather than threaded, so most of the tree-node change is a removal.
- Good: a missing instant fails at the point it is needed rather than being replaced by a clock read.
- Neutral: two acts that race on two threads can still reach a recording in either order; that is real nondeterminism, and the demos still order their steps on their causes (EDF-06).
- Bad: every test that builds a core model without a time will need one, so the model change is wide and is done as its own step.
- Bad: one more value lives in a tree run's shared state, which is global to the process; it takes the same lock and inheritance rule as the leadership check.
- Bad: every committed recording changes once, when the recording clock moves to the port.

## Validation

- An architecture test will fail on a clock read in any module outside an explicit, per-item allow-list of act entry points and adapter bookkeeping.
- A model test will fail on a core model field whose default reads the clock.
- Under a counting clock, each act in a recorded run will read the clock exactly once.
- A node ticked without an instant in its tree run will fail rather than read the clock.
- Each migrated decision will give the same verdict for the same instant as before.

## More Information

The current time rules live in the CS-13 group of `specs/code-style.yaml` and the CLP-15 group of `specs/case-ledger-processing.yaml`.
The CS-13 rules that name the clock helper and the deadline helpers will be restated against this decision as the code that meets them lands.

The work is tracked under #5676, in slices by node shape: the clock port, act entry points, tree-run instant and the architecture test first; then tree builders and guard nodes (#5649); sync rate-limit checks (#5651); core models; the parse edge (#5652); and last, the recording clock through the port.
