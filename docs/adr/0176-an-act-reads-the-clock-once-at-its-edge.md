---
status: accepted-provisional
status_override: >-
  Rewritten in place before release to match the slice-1 build (user
  decision, 2026-11-09, PR #6137).
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-09
revision: 3
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; issues #5676, #5591, #5649, #5650, #5651, #5652, #5757,
  #5758, #5760, #5761, #5848, #2887, #3423;
  ADR-0032, ADR-0103, ADR-0167; specs/code-style.yaml CS-13;
  specs/case-ledger-processing.yaml CLP-15;
  specs/case-bootstrap-trust.yaml CBT-03-003
informed: []
partially_supersedes:
- 0103-object-time-is-carried-never-minted.md
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
- Several stamps written by one act must still sort in the order they were written (ADR-0167, CS-13-002).
- A time a peer sent is carried, never minted (ADR-0103, CLP-15-007, CLP-15-008).
- An act's instant must be the time it decides, not the time it queued for the tree lock.
- The rule must be enforced by a test, not by audits.

## Considered Options

1. **Fix each read where it is found.** Give each site its own injected time, issue by issue.
2. **One instant per act, passed as an argument everywhere.** Every builder, node, helper and model that needs time takes a required argument.
3. **One instant per act, read at the act's edge.** A tree's nodes read it from the tree run's shared state; everything else takes it as an argument.
4. **Re-read the clock where a decision needs it.** A tree with a time constraint reads the clock again at each decision, so a slow act decides against the current time.

## Decision Outcome

Chosen option: "One instant per act, read at the act's edge", because it removes the cause rather than the symptoms and needs no time parameter on any tree builder, node or nested tree run; only the act entry points and the bridge's outermost call take the instant.
Option 1 has already produced four issues, and nothing stops a fifth.
Option 2 meets every driver but threads a time through every tree builder and every nested tree run by hand, which #5649 found to be an architectural change rather than a defect fix.
Option 4 answers a slow act's staleness by bringing back the first problem: the guard decides at one instant and the commit is stamped at another.
Staleness is a separate problem, handled below by a stated assumption and a later drift limit, not by a second read of the clock.

The decision has seven parts.

- **An act and its instant.** An act is one trigger invocation, the processing of one inbound delivery, or one scheduled sweep.
  Each act takes the tree lock first, then reads the clock exactly once, and holds the lock until it commits; that reading is the act's instant.
  For a trigger the lock covers the whole invocation, including the checks it makes before running its tree, so no check of an act runs outside the lock or against an instant read before it.
  The lock is re-entrant, so the bridge taking it again inside the act is safe.
  Every decision the act takes compares against it, and every time the act records is derived from it.
- **A received activity is judged when it is processed.** The instant of a received activity's act is the time it is applied, not the time it arrived.
  A held activity replayed later gets the instant of its replay, so an expiry is judged at the moment its effect lands.
  The arrival time stays its own recorded fact.
  The held activity itself is replayed as it arrived; only the decision time is new.
  Each replayed activity is an act of its own, even when its replay runs inside the processing of the activity that released it: it reads its own instant, and a replay nested in another act does not inherit that act's instant.
- **Trees read the instant from the tree run.** The bridge's outermost run of an act takes the act's instant and places it in the run's shared state, beside the data layer and the leadership check.
  A nested tree run takes no instant and inherits it, as it inherits the leadership check, so a nested run sees the same instant as the act that started it; a nested run handed an instant of its own fails.
  A run with no instant to inherit carries none, and a node in it that reads the instant fails when it ticks, as an internal error; the run is never given a clock reading instead.
  The failure sits at the reader, not the bridge, because most trees read no time.
  Tree builders and node constructors take no time.
- **Core code takes time, never reads it.** Below the act's edge, a helper or model that needs time takes it as a required argument.
  A domain model has no field whose default reads the clock, including an object this process authors (see More Information for ADR-0103).
  An ordered stamp is computed from the act's instant and the previous stamp, and the smallest step past the previous stamp keeps two stamps of one act in order.
  A deadline is the act's instant plus a duration.
- **The parse edge reads no clock.** Parsing and extraction carry the times a peer sent and compute nothing from the clock.
  An inbound activity without `published` is already refused at parse (CLP-15-008), so a computation that measures from `published` will take it as required.
  A check that needs the current time, such as whether a deadline has already passed, belongs to the handler, which holds the act's instant.
  Clean-up of expired entries is an act of its own, not a step of receiving (#2887).
  A held activity whose queue interval has expired is still dropped when its replay is attempted, judged against the replay act's instant, so a release that comes before the clean-up never applies an expired activity (CBT-03-003).
- **The clock is injected.** The clock is a port with one operation, the current time, that the composition root supplies: the system clock in production and a recording clock in a recorded run.
  Only act entry points will hold it.
  Adapter bookkeeping times, such as when a delivery was queued or dead-lettered, are infrastructure times read through a separate bookkeeping clock port; they do not enter the case ledger and are not an act's instant.
  The composition root supplies that port too: the system clock in production and, in a recorded run, a clock the recording clock does not see, so a bookkeeping read never moves a recording.
- **Elapsed time is a stopwatch, not the clock.** A limit on how long work may take, such as a call-out's time budget (#3423), measures elapsed time on a separate monotonic port.
  A stopwatch reading feeds a limit and nothing else: it never enters a decision about the case or anything the act records, and the recording clock does not see it.
  The architecture test forbids clock reads below the act's edge and allows stopwatch reads only at named sites.

An act's instant is frozen on the assumption that an act runs for a short time compared with every window it decides on: trees run to completion without waiting (BT-01-002), make no network calls, and decide on windows of seconds to weeks.
A call-out that blocks on an external service can break that assumption.
When it can, a drift limit will close the gap without a second clock read: an act whose stopwatch time since its instant exceeds a budget aborts before committing and reruns with a fresh instant (#5848, after #3423).

This decision covers time only.
Generated ids have the same shape, a global that the recording harness replaces, and are decided in [ADR-0185](0185-the-one-id-minter-draws-from-an-id-source-not-a-patched-uuid4.md).

### Consequences

- Good: one act's decisions and records agree on when it happened.
- Good: a clock read inside an act no longer moves a recording; what a recording holds depends only on how many acts run, which the demos fix by ordering their steps on their causes (EDF-06).
- Good: the recording clock steps once per act, so one tick means one act; bookkeeping reads go to their own port and do not step it.
- Good: the per-site fallbacks and their time parameters are deleted rather than threaded, so most of the tree-node change is a removal.
- Good: a missing instant fails at the point it is needed rather than being replaced by a clock read.
- Neutral: an act's instant can be older than the wall clock by the time the act commits; the assumption above bounds the gap until the drift limit lands.
- Neutral: two acts that race on two threads can still reach a recording in either order; that is real nondeterminism, and the demos still order their steps on their causes (EDF-06).
- Bad: every test that builds a core model without a time will need one, so the model change is wide and is done as its own step.
- Bad: stamps written by one act share its instant, so the smallest-step bump past the previous stamp becomes the routine way they are ordered, where ADR-0167 expected a same-instant tie to be rare.
- Bad: adapters hold a second clock port beside the act clock, and the composition root wires both.
- Bad: one more value lives in a tree run's shared state, which is global to the process; it takes the same lock and inheritance rule as the leadership check.
- Bad: every committed recording changes once, when the recording clock moves to the port.

## Validation

- An architecture test will fail on a clock read in any module outside an explicit, per-item allow-list of act entry points, and on a bookkeeping clock read outside named adapter sites.
- A model test will fail on a core model field whose default reads the clock.
- Under a counting clock, each act in a recorded run will read the clock exactly once.
- A node ticked without an instant in its tree run will fail rather than read the clock.
- An act's instant will be read after the act takes the tree lock, and a trigger's checks before its tree will run inside that lock.
- Each migrated decision will give the same verdict for the same instant as before.

## More Information

The current time rules live in the CS-13 group of `specs/code-style.yaml` and the CLP-15 group of `specs/case-ledger-processing.yaml`.
The CS-13 rules that name the clock helper and the deadline helpers (CS-13-002, CS-13-004, CS-13-008) will be restated against this decision as the code that meets them lands.

This decision narrows [ADR-0103](0103-object-time-is-carried-never-minted.md): ADR-0103 kept the `default_factory` clock for objects this process authors and told the two directions apart by a validation-context marker.
Here no core model field defaults to the clock in either direction, so an authored object takes the act's instant explicitly and the inbound marker no longer has a default to suppress.
ADR-0103's rule that a time a peer sent is carried, never minted, stands unchanged.

The work is tracked under #5676, in slices by node shape: the clock port, act entry points, tree-run instant and the architecture test first (#5757); then tree builders and guard nodes (#5649); sync rate-limit checks (#5651); core models (#5758); the parse edge (#5652); and last, the recording clock through the port (#5760).
