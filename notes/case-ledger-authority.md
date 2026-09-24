---
title: Case Ledger Authority and Assertion Recording
status: active
description: "Authority model for the case activity log: trusted timestamps, assertion recording, and authority chain."
related_specs:
  - specs/architecture.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/sync-ledger-replication.yaml
related_notes:
  - notes/activitystreams-semantics.md
  - notes/case-communication-model.md
  - notes/case-state-model.md
  - notes/configuration.md
  - notes/ownership-transfer.md
  - notes/sync-ledger-replication.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
---

# Case Ledger Authority and Assertion Recording

**Relates to**: `specs/case-ledger-processing.yaml`,
`specs/case-management.yaml`, `specs/sync-ledger-replication.yaml`,
`notes/activitystreams-semantics.md`, `notes/case-state-model.md`,
`notes/sync-ledger-replication.md`

---

## Overview

This note refines the rough "intent vs event" idea into a model that better
fits Vultron's existing ActivityStreams semantics and single-writer CASE_MANAGER
architecture.

The key distinction is **not** request vs fact. Participant-originated
activities already function as assertions that something happened on the
sender's side. The important distinction is instead:

- **participant assertion**: an inbound case- or proto-case-scoped activity
  that claims a protocol-relevant change occurred
- **canonical case ledger entry**: a CASE_MANAGER-authored record that the
  assertion was accepted into canonical history (CLP-04-007)

This keeps Vultron aligned with the existing rule that Activities are
state-change notifications, not commands, while still preserving the CASE_MANAGER
as the sole authority for replicated case history.

---

## Assertions Are Implicit

For case-scoped and proto-case-scoped flows, ordinary inbound AS2 activities
from participants should be treated as **assertions by default**.

Examples:

- `Offer(Report)` asserts that a report was submitted
- `Add(Note)` asserts that a note was added
- `Assign` asserts that an ownership-related action was taken
- `Invite`, `Accept`, and `Reject` assert that the sender performed those
  protocol actions

Because nearly all relevant inbound work messages already have this shape,
adding a separate `vultron:mode = asserted` field to every ordinary activity
adds noise without much extra meaning. The sender role and processing path
already imply that these are participant assertions awaiting CASE_MANAGER
recording.

This is especially true since reports are treated as **proto-cases** under
ADR-0015. A case object (`VulnerabilityCase`) is created at report receipt,
so logging begins immediately and continues through the full case lifecycle,
rather than starting only after validation. A proto-case is a case in the
RM.RECEIVED or RM.INVALID stage — the case object exists, but validation
has not yet occurred.

---

## The CASE_MANAGER Writes Canonical History

The CASE_MANAGER remains the **single writer** of authoritative shared history.
Participants may send assertions, but participant replicas must not update
shared case state directly from peer messages.

Instead, the CASE_MANAGER:

1. receives a participant assertion
2. validates that it is authentic, case-resolvable, and acceptable at the case
   layer
3. appends a canonical log entry describing the outcome
4. replicates only the canonical recorded history to participant replicas

This means the CASE_MANAGER is not "re-performing" the asserted action. It is
publishing the canonical statement:

> I received and processed this asserted activity, and I recorded it as part of
> authoritative case history.

---

## Three Questions That Look Like One (ADR-0088)

Code near the commit boundary asks three things that all sound like "who is the
CaseActor here?". They are different questions with different answers, and
conflating any two of them has already produced bugs. ADR-0088 separates them.

| Question | Answered by | Signal |
|---|---|---|
| Am I the authority? | `resolve_case_manager_id` / `CheckIsCaseManagerNode` | The `CVDRole.CASE_MANAGER` role, and nothing else |
| What address do I route to? | `_find_case_actor_id` | The role-holder's id, or a `ReportCaseLink`-recorded address during bootstrap |
| May *this store* append here? | `DeclineForeignLedgerCommitNode` / `store_for_actor` | Whether the store in hand holds the log |

**Authority is the role (CM-02-011).** Not a hosting location, not a URL shape.
"Case Actor" is the readable label a demo gives to whichever actor enacts
`CASE_MANAGER`, exactly like "vendor" or "finder" — nobody adopts it as an
identity, and no protocol logic may branch on the string (CM-02-013,
ARCH-24-004, ratcheted by
`test/architecture/test_role_authority_resolver.py`).

**Address resolution is downstream of authority, not a variant of it**
(ARCH-24-005). Because authority *is* the role, the authority's address is just
the role-holder's address, so `_find_case_actor_id` reads the same roster —
but it answers "where do I send this?" and a `None` from it means "no
resolvable address", never "no authority".

**The store guard is not an authority check either** (ARCH-24-005). By the time
`DeclineForeignLedgerCommitNode` runs, role-authority has already said "you may
commit"; it only stops a delegated-emit fall-through from minting a canonical
index in a store that is not the log's home, which would fork the chain
(#2626). Reading it as an authority check makes the role look like a property of
a store, which it is not.

### The bootstrap window this replaced

The retired signals were not merely redundant, they were wrong in a reachable
state. Under ADR-0041 the CaseActor `Service` object is written *before* the
case exists, so it carries no `context` — and a `context == case_id` scan
therefore found nothing. In that window the real authority **failed its own
hosting test** and took the *participant* arm of the announce split on its own
ledger, validating a hash chain it owns. Role membership is stable from
replica-seed onward (CP-09-004) and has no such window; the regression test is
`test_case_manager_role_takes_authority_arm_without_service_object`
(CM-02-012).

A related trap lived in the deleted `_find_case_actor` helper: on a miss it
returned *the first arbitrary `Service` in the store*, so a failed lookup was
indistinguishable from a successful one and published a plausible-looking
address belonging to some other case. When a resolver cannot answer, it must
say so.

---

## `CaseLedgerEntry` Is the Canonical Content Object

The canonical object should be a neutral **`CaseLedgerEntry`**, not a renamed copy
of the original activity and not the transport envelope itself.

Why a neutral object type:

- it records only CASE_MANAGER-accepted assertions — every entry is canonical
- it separates canonical log content from transport concerns
- it gives the CASE_MANAGER a stable object to hash, replicate, replay, and audit

A `CaseLedgerEntry` carries:

- the asserted activity payload, or a normalized immutable snapshot sufficient
  for deterministic replay
- the CASE_MANAGER's own recording metadata (log_index, entry_hash, received_at,
  prev_log_hash, term)

Rejection outcomes are not recorded as ledger entries. When the CASE_MANAGER
rejects an incoming assertion, it sends a `Reject` protocol activity to the
asserting participant (CLP-02-005) and emits a Python log event; nothing enters
the hash chain (CLP-04-007, CLP-05-002).

`Announce` remains the **transport wrapper** for replication. The thing being
announced is the `CaseLedgerEntry`, not the other way around.

---

## Canonical Ledger vs. Python Process Log

Two related but distinct structures capture case-layer information:

### 1. Canonical Case Ledger

The canonical case ledger is append-only and contains only CASE_MANAGER-accepted
protocol-significant assertions. Every entry is a `CaseLedgerEntry` with a valid
payload snapshot and a hash chain position. No disposition field exists — every
entry in the ledger is, by definition, accepted (CLP-04-007).

The canonical ledger:

- drives participant replica state reconstruction
- participates in the Merkle/hash chain
- is fanned out to other participants as canonical updates via `Announce`

### 2. Python Process Log

Rejection outcomes, diagnostic events, and processing traces go to Python
`logging` output. This log is per-actor, ephemeral, and must never be
replicated or relied on for protocol semantics (ADR-0019).

When the CASE_MANAGER rejects an incoming assertion:

- A `Reject` protocol activity is sent directly to the asserting participant
  (CLP-02-005, CLP-05-001)
- A Python log event is emitted at `INFO` or `WARNING` level
- Nothing enters the hash chain (CLP-05-002, CLP-05-003)

---

## Rejection Routing

Not every inbound failure belongs in the canonical ledger — nothing does except
accepted assertions.

- If a message cannot be tied to a report/case (including proto-cases in
  RM.RECEIVED/INVALID stages), it belongs in transport- or actor-level
  diagnostics (Python `logging`), not the canonical ledger.
- If the CASE_MANAGER resolves the message to a case context but rejects it
  during case-layer validation, it sends a `Reject` protocol activity to the
  asserting participant (CLP-05-001) and emits a Python log event.

Rejection feedback is directed only to the asserting sender, not broadcast to
all case participants. The other participants need the canonical history, not
the full stream of invalid assertion attempts (CLP-05-001).

---

## Replication Implications

This model sharpens the replication boundary:

- participant assertions are **inputs** to CASE_MANAGER processing
- `CaseLedgerEntry` objects are the **canonical replicated facts** — every entry
  is an accepted assertion by definition (CLP-04-007)
- participant replicas derive state only from canonical ledger entries

To support replay and stale-position detection, participant assertions should
carry the sender's last accepted canonical log hash or position in `context`
when available. That gives the CASE_MANAGER a concrete basis for deciding whether
to accept the assertion, reject it as stale, or replay missing canonical
entries first.

The hash chain should therefore be computed over **CASE_MANAGER-authored canonical
recorded entries**, each of which includes the asserted payload snapshot needed
by recipients. Replicating only pointers to prior assertions is insufficient,
because replicas need the actual asserted content to reconstruct state.

---

## `pending_assertions`: Local Decision-Suppression Memory (Epic #788)

Epic #788 (#789–#792, completed) made canonical `CaseLedgerEntry` the sole source
of protocol-significant history and removed `CaseEvent` / `record_event()`.
Actor-local `pending_assertions` suppresses duplicate emits during the canonical
round-trip window — it is temporary local memory, not a second source of truth;
canonical `CaseLedgerEntry` remains authoritative.

Policy (`vultron/core/models/pending_assertion.py`):

- default timeout is **180 seconds** and configurable
- timeout marks the assertion `timed_out` and logs an error
- timeout does not auto-retry
- entries clear when a matching canonical `CaseLedgerEntry` arrives

## Consequences for Future Design Work

This framing has several practical consequences:

- The old "intent vs event" terminology should be retired for this topic.
  `asserted` vs `accepted` is more accurate — every entry in the ledger is an
  accepted canonical assertion; rejections are protocol activities, not ledger
  entries (CLP-04-007).
- The `CaseEvent` / `record_event()` path was a useful foundation, but
  the long-term canonical content model needs to grow into a richer
  `CaseLedgerEntry`.
- Specs and implementations dealing with replication operate directly on the
  canonical ledger — no disposition filtering is required because the ledger
  contains only accepted entries.
- Proto-case history must remain continuous across the
  report-to-case transition rather than being split into two unrelated logs.

This note should be treated as the durable design explanation. Normative
requirements belong in `specs/case-ledger-processing.yaml`.

---

## Canonical Entry Criteria: What Belongs in the Log

The canonical case ledger is a **protocol ledger**, not a process log. It records
exactly one entry per CASE_MANAGER-accepted protocol-significant assertion. Each
entry's `payloadSnapshot` is the verbatim AS2 activity that was asserted (or a
deterministic canonical normalization of it).

Concretely:

**Belongs in the canonical case ledger (allowed `payloadSnapshot` types):**

- `Offer(VulnerabilityReport)` — finder asserts report submission
- `Add(Note)` — participant asserts a note exchange
- `Add(ParticipantStatus)` — participant asserts an RM/CS/EM transition
- `Offer(EmbargoEvent)`, `Accept(EmbargoEvent)`, `Reject(EmbargoEvent)` —
  embargo proposal/response
- `Invite(VulnerabilityCase)`, `Accept(Invite)`, `Reject(Invite)` — case
  membership handshake (note: routed through the CASE_MANAGER per PCR-08)
- `Announce(VulnerabilityCase)` — case bootstrap broadcast
- Any other protocol-significant AS2 activity that mutates protocol-visible
  state

**Does NOT belong in the canonical case ledger:**

- Synthetic checkpoint markers (e.g., `demo_verification`)
- Per-actor runtime diagnostics, troubleshooting traces, or "I made it to
  step N" markers
- Internal cascade triggers, sentinels, or scheduling events
- Any event whose `payloadSnapshot` would be empty or whose `logObjectId`
  points at the case itself rather than a specific protocol activity

Anything in the "does NOT belong" category is **process-log content** and
belongs in Python `logging` output governed by `specs/structured-logging.yaml`,
not in the canonical case ledger.

### Why the Separation Matters

The canonical case ledger is replicated to every participant and contributes
to the hash chain that participants use to verify their replicas agree
with the CASE_MANAGER's authoritative copy. If diagnostic or synthetic
content enters the chain:

- Participants cannot deterministically reconstruct case state from the
  log alone — they'd have to filter out non-protocol entries.
- The hash chain becomes sensitive to runtime details that have nothing
  to do with protocol semantics (e.g., timing of demo checkpoints).
- Operators using process logs for troubleshooting cannot freely add
  detail without risking protocol-level effects.

The decision is captured at the ADR level in
**ADR-0019 — Case Ledger Is a Canonical Protocol Ledger, Not a Process Log**.

### `Announce` Envelope vs. `payloadSnapshot` Actor

A subtle but important distinction:

```text
Vendor sends:  Add(ParticipantStatus, actor=vendor) → CASE_MANAGER
CASE_MANAGER commits: CaseLedgerEntry(
  log_index=N,
  recording_actor=case_actor,
  payloadSnapshot=Add(ParticipantStatus, actor=vendor),  ← verbatim assertion
)
CASE_MANAGER broadcasts: Announce(
  actor=case_actor,                                       ← envelope actor
  object=CaseLedgerEntry(...),
) → all participants
```

The `Announce` envelope's `actor` field is always the CASE_MANAGER. The
`payloadSnapshot.actor` inside the `CaseLedgerEntry` preserves the original
asserter (`vendor` in the example). Replicas receiving the broadcast
update their state based on the snapshot's asserter, not the envelope's
actor. Rewriting `payloadSnapshot.actor` to the CASE_MANAGER would erase
the assertion's provenance and is forbidden by CLP-07-003.

### Commit-Boundary Enforcement

CLP-07-005 recommends a runtime guard at the CASE_MANAGER commit boundary
that rejects entries violating CLP-07-001 through CLP-07-004 *before*
they enter the hash chain. Failing fast at commit time keeps the
canonical chain clean and surfaces bugs immediately, rather than allowing
silent pollution that's discovered only when replicas diverge.

### CLP-07-003 Actor-Identity Check Lives at the Receive Pipeline, Not the Commit Boundary

The check that `payloadSnapshot.actor` equals the asserting actor is enforced at
`CommitCaseLedgerEntryNode` (`vultron/core/behaviors/case/nodes/lifecycle.py`),
where the original `activity.actor_id` is still available — **not** at
`_validate_canonical_entry` in `chain.py`, which sees only the built snapshot.
ADR-0088 grants authority by role, so a CASE_MANAGER may legitimately self-assert
participant activities; an identity check at the commit boundary false-rejects
those (ISSUE-3282, PR #3313).

Pitfall: do not restore the identity comparison to `_validate_canonical_entry`.
`_CASE_AUTHORED_SIGNATURES` is still needed there for CLP-12-002's native-init
coverage check — do not delete it, only its use in the identity comparison.

### An Entry Has Two Timestamps, and They Belong to Different Layers

*Spec: CLP-14, CLP-15; ADR-0079 § "Validation". Issue #2824.*

`CaseLedgerEntry.published` is the CASE_MANAGER's **commit** stamp.
`payloadSnapshot.published` is the asserting actor's **claimed** event time.
Deciding which one an invariant is about is not a detail — get it wrong and the
check is either vacuous or falsely rejecting:

- Commit-timestamp invariants (CLP-14-002/003/006 read against the envelope)
  hold **by construction** — one writer, one clock. They belong to the
  conformance harness (`check_clp14_timestamp_invariants`), which is the only
  vantage point that sees a whole ledger. An entry never sees its predecessor,
  so the *model* layer can never enforce them; asserting that it should is what
  produced seven permanently-red `xfail(strict=True)` stubs.
- Claimed-timestamp invariants (CLP-14-006/007/008, CLP-15-003) cannot hold by
  construction, because a participant chose the value. They belong to
  `_validate_entry_timestamps` at the commit boundary.

Five traps, all found the hard way:

1. **Claimed-timestamp monotonicity MUST be scoped per snapshot actor.**
   Comparing claimed times across actors is exactly the wall-clock ordering
   ADR-0079 rejected as option C. CLP-15-003 says "within the same
   participant's event stream" for this reason.
2. **CLP-15-003 is reported, never refused.** The CASE_MANAGER sees *arrival*
   order, not causal order, and the transport promises no ordering (ADR-0037).
   Refusing a regression is the reconstruction CLP-15-005 forbids, and it loses
   the assertion completely — the guarded commit precedes the effect nodes
   (CLP-10-006), so a raise aborts the whole receive sequence with no ledger
   record and no retry. Two report bands: `INFO` within the configured
   clock-skew tolerance, `WARNING` beyond it.
3. **A snapshot the CASE_MANAGER builds on a participant's behalf carries that
   participant's claimed time**, from the triggering activity — use
   `claimed_published_iso()`. Stamping `now_utc()` under a participant's actor
   URI puts a foreign clock in that actor's claimed stream, which trap 2 then
   reports as a regression, and leaves CLP-14-007/008 comparing the receiver's
   clock against itself. A snapshot the CASE_MANAGER genuinely authors (its own
   actor URI) does use its own clock.
4. **A missing inbound `published` is a validity failure, not something to
   fill in.** `as_Base` defaults the field to `now_utc` so the same classes can
   author outbound activities; on the inbound path that default is the
   receiver's clock posing as the sender's claim, and after `model_validate` the
   two are indistinguishable. `parse_activity` therefore refuses it on the raw
   body (CLP-15-006), which is why nothing downstream needs an
   "absent claimed time" branch. Note this is *not* CLP-07-011 — that requires
   the snapshot be the verbatim activity, and says nothing about `published`.

   **"Missing" means the value, not the key** (MV-03-002, ADR-0090). A
   present-but-blank `published` — empty or whitespace-only — carries no claimed
   time either and is refused identically. Testing only `is None` asked whether
   the key was absent, so `published: ""` slipped past and was reported as a
   schema fault, which told the sender their timestamp was malformed rather than
   absent. The boundary against that widening: a value that is present and
   non-blank but unreadable (`"not-a-date"`, `0`, `[]`) stays a schema fault —
   reporting corrupt data as missing data tells a sender to resend what they
   already sent.

   This holds only at the **top level**. Nested objects legitimately omit
   `published` (AS2 makes it optional everywhere), so they are **taken as
   received** (ADR-0103): `as_Base.carry_absent_times_on_inbound` reads an
   omitted clock-defaulted timestamp as `None` for whichever class is being
   validated, switched on by the inbound context `parse_activity` passes; the
   extractor passes it through, and core keeps `None` — an object's time is
   carried, never minted by whoever receives or renders it (#3257, #2553).
   Refusal is reserved for a decision that *needs* the time, and it happens at
   parse: a case with no `genesisHash` and no `published` (CLP-08-002), an
   embargo with no `endTime`, a replicated ledger entry with no `published` or
   `receivedAt` (CLP-14-002, CLP-02-008). Consumers that merely order by time
   tolerate `None` — `most_recent_status` sorts it lowest and breaks ties by
   append order.

   The rule binds **storage too, not just parsing**. A payload snapshot is
   dumped with `exclude_none=True`, so a carried absence leaves no key, and
   validating that dict straight into a core class let the `default_factory`
   stamp the *replica's* clock — the same fabrication one boundary later, and
   the reason two replicas disagreed about which status was current. Rebuild a
   core object from a snapshot through `project_wire_snapshot_to_core`, which
   reads those absences, never `Model.model_validate(snapshot)` directly.
5. **Never gate a whole guard on one optional argument.** The CLP-14 guard sat
   behind `if case_published is not None:` and the sole production call site
   never passed it, so nothing was checked for the guard's entire life while
   its unit tests passed by calling it directly. Gate each check on the context
   *it* needs, and test enforcement through the production node, not the
   private validator.

CLP-15-001 and CLP-15-002 bind the *participant*, and CLP-15-005 forbids the
CASE_MANAGER from reconstructing participant-internal causal order. Their
verification is `check_causal_edges` (DEMOMA-22-005), not a per-assertion
check.

---

## Commit Authorization and Coverage (CLP-09, Epic #788 retrospective)

Two gaps surfaced late in Epic #788 that CLP-09 now makes explicit, because
the prior framing (BT-10-004's single line, "CASE_MANAGER MUST enforce
case-level authorization") was not specific enough to prevent them from
accumulating call site by call site.

### Gap 1: Authorization Was a Convention, Not a Gate

`CommitCaseLedgerEntryNode` (the canonical commit mechanism established by
PR #1017 / BT-06-006) had no built-in authorization check. An audit found
that only one of roughly ten call sites guarded the commit, and it did so
with an ad hoc Python-level identity check (`_is_case_actor_receiver`)
*outside* the BT, not a role check inside it. The other call sites
committed unconditionally.

The fix is a reusable guarded-commit composition, following the same
Selector/Sequence/Success idiom already used elsewhere in this codebase
(see `notes/bt-integration.md` § "Conditional BT Branches as Selector
Composites" and § "Guarded Commit: Role-Gated Canonical Writes"):

```text
Selector
├─ Sequence
│  ├─ CheckIsCaseManagerNode   # role check, not identity comparison
│  └─ CommitCaseLedgerEntryNode
└─ Success("CommitCaseLedgerEntrySkippedNotCaseManager")
```

CLP-09-001 requires every commit call site to reach the commit only through
this kind of guarded composition. CLP-09-002 requires a test that fails if
any call site bypasses it.

### Gap 2: Commit Coverage Had No Structural Check

`validate_report`, `ack_report`, and `close_case` produced **no** canonical
ledger entry at all on `main` for an unknown span of time (issue #998).
Dispatch completeness already has a structural guarantee — DR-02-002 and
UCORG-02-002 require every `MessageSemantics` value to resolve to a callable
use case, enforced by a coverage test. Commit completeness had no
equivalent: a use case could be fully wired for dispatch and still never
touch the ledger, and nothing would fail until someone manually re-audited
the tree-by-tree commit sites (which is how #998/#1022 found the gap).
CLP-09-003 closes this by requiring the same kind of enumerated coverage
test for commits that already exists for dispatch.

### Gap 3: Dual-Invocation Use Cases Need Per-Invocation Authorization

Some use-case classes are invoked more than once for the same logical
activity, with different receiving actors. The clearest example is
`ack_report` in the two/three-actor demo: the same `AckReportReceivedUseCase`
runs once with the vendor (which holds `CVDRole.CASE_MANAGER`) as receiver, and
once with the finder as a relay target. Only the CASE_MANAGER's invocation
should commit.

This is structurally the same bug shape that produced the original
hash-chain fork in issue #923 — a use case authored or committing on behalf
of the wrong actor. CLP-09-004 makes the general rule explicit: authorization
for a commit must be evaluated **per invocation**, against the actor that is
actually active for that invocation, never assumed from the use-case class
itself or from a prior invocation having been authorized.

---

## Native Case-Initialization Entries (ADR-0041) — replaces the prologue backfill

*Spec: `specs/case-management.yaml` CM-22-003; `specs/case-ledger-processing.yaml`
CLP-12.*

The CASE_MANAGER commits every case-initialization ledger entry **natively**, in
`CommitNativeLedgerEntriesNode` inside
`vultron/core/behaviors/case/nodes/proposal_ledger.py`, while handling the
inbound `Create(as_CaseProposal)`.  Causal order:

1. `create_case` — `Create(VulnerabilityCase)`, `actor` = CASE_MANAGER
2. `add_report_to_case` — `Add(VulnerabilityReport)`, `actor` = CASE_MANAGER
3. `add_participant_status_to_participant` × N — `actor` = CASE_MANAGER
4. `add_case_status_to_case` — `Add(CaseStatus)`, `actor` = **vendor URI**

The `payloadSnapshot` shapes come from
`vultron/core/behaviors/case/ledger_snapshots.py`.

**Exactly one `add_participant_status` entry per participant** (CM-18-007). The
default embargo is established *before* participant PEC state is fixed, so each
participant's single initialization snapshot already carries its true consent
value — no `UNBOUND` placeholder followed by a correction. Because `ACCEPT` is
valid directly from `UNBOUND` (CM-18-003, ADR-0048), one transition suffices.
Do not add a second per-participant entry here: it would shift every downstream
`log_index`, which is what got PR #1746 reverted after it broke `fvcv-extension`
VFD replication timing, and it would break the "`log_index` order *is* causal
order" property below.

**Fail-fast on genesis, best-effort after.** Step 1 is the root of the
CASE_MANAGER's hash chain; if it fails the node returns FAILURE so the enclosing
Sequence aborts before `Accept`/`Create` are emitted, rather than telling the
vendor a case exists with no canonical ledger.  Steps 2–4 log a warning and
continue.

**Why step 4 uses the vendor URI.** The vendor is who set the genesis case
status, so the snapshot names the vendor as `actor`.  That is a provenance
statement, not a workaround: `("Add", "CaseStatus")` *is* in
`_CASE_AUTHORED_SIGNATURES` (CLP-12-001), so a CASE_MANAGER-authored
`add_case_status_to_case` also validates — which is what makes single-actor
deployments (vendor IS the CASE_MANAGER) work.

History worth not re-litigating: adding `("Add", "CaseStatus")` to
`_CASE_AUTHORED_SIGNATURES` on its own (commit `256ef3e1`) was rejected and
reverted (`f6578c22`) as ADR-0041 Option 3 — a *symptom* fix that left the
two-init-path architecture in place.  The signature entry is correct; it was
only ever wrong as a substitute for removing the back-fill.  Both are now
done.

> **Historical:** Issue #1688 introduced `WritePrologueLedgerEntriesNode`
> (`vultron/core/behaviors/case/nodes/prologue.py`), which back-filled these
> entries best-effort when the CASE_MANAGER accepted an `Offer(CaseManagerRole)`.
> ADR-0041 removed the two-init-path architecture that made the back-fill
> necessary, and Issue #1777 deleted the node.  Its known
> assignment-time-vs-causal-time `log_index` skew disappeared with it: the
> native entries are committed at initialization, so `log_index` order *is*
> causal order (normative decision record: ADR-0079; testable invariants:
> CLP-14-001 through CLP-14-010).  `Offer(CaseManagerRole)` was subsequently
> removed entirely
> (issue #2429, ADR-0039); the delegation mechanism was replaced by
> `OFFER_CASE_PARTICIPANT_ROLE` (`Offer(CaseParticipantRole, target=Actor,
> context=VulnerabilityCase)`) handled by `OfferCaseParticipantRoleReceivedUseCase`.
> See SE-08-005.

---

## Per-Case Genesis Hash — Origin Binding and Future Improvements

*Spec: `specs/case-ledger-processing.yaml` CLP-08-001 through CLP-08-006.*

The per-case genesis hash is derived as
`SHA-256(case_id + "|" + created_at.isoformat() + "|" + case_actor_id)`.
This anchors each case ledger to its origin identity and timestamp,
replacing the former global `GENESIS_HASH = "0" * 64` constant.

### Current Threat Model

Domain-bound case URIs (e.g., `https://example.org/cases/<uuid>`) with a
cryptographically random UUID path segment satisfy CLP-08-006. The domain
prefix is public but irrelevant — an attacker must still brute-force the
UUID component to predict the genesis hash.

If case metadata (`case_id`, `created_at`, `case_actor_id`) is observable
by an attacker — which is possible in a federated protocol — the genesis
hash becomes computable by anyone with that knowledge. This means:

- **Hash-chain integrity** is preserved: the attacker cannot forge or silently
  drop entries from a chain whose genesis hash a receiver has independently
  stored.
- **DoS amplification** is reduced from universal (any attacker, any case) to
  targeted (attacker must know this specific case's metadata), but is not
  fully eliminated.

### Future Improvement: Secret Nonce

Adding a secret nonce to the genesis hash input — a random value generated
by the CASE_MANAGER at case creation and never transmitted on the wire — would
close the targeted DoS vector even when case metadata leaks:

```python
genesis_hash = sha256(
    case_id + "|" + created_at.isoformat() + "|" + case_actor_id
    + "|" + secret_nonce
)
```

The nonce would need to be stored securely in the CASE_MANAGER's DataLayer and
shared only with legitimate participants through an authenticated channel.
This adds key-management complexity that is out of scope for the prototype
tier but is the natural next step for production deployments.

### Future Improvement: CASE_MANAGER Keypairs

The more durable long-term solution is **cryptographic identity for
CaseActors**. When CaseActors generate a new keypair at actor creation time
(planned), the genesis hash can incorporate the CASE_MANAGER's public key or a
key-signed commitment over case creation data:

```python
genesis_hash = sha256(
    case_id + "|" + created_at.isoformat() + "|" + case_actor_public_key
)
# or: genesis_hash = sha256(case_actor.sign(case_id + created_at))
```

This would:

- **Eliminate DataLayer trust for genesis authenticity**: any party with the
  CASE_MANAGER's public key can independently verify the ledger's origin without
  trusting the DataLayer's `case_id` field.
- **Close the targeted DoS vector**: the nonce is effectively the private key,
  which is never observable on the wire.
- **Enable third-party auditing**: auditors can verify ledger provenance from
  the public key alone, without needing out-of-band case metadata.

The keypair-per-CASE_MANAGER design is tracked as a planned capability. Until
it lands, the domain-bound UUID genesis hash defined in CLP-08-002 is the
correct implementation.

---

## `invite_actor_to_case` Commits a Canonical Ledger Entry (Issue #1689)

`EmitInviteActorToCaseNode._call_factory()` (in
`vultron/core/behaviors/case/nodes/actor.py`, renamed from `_emit()` by #2881)
commits a canonical ledger entry via `create_commit_log_entry_tree`. All ledger
entries pass through `_validate_canonical_entry` — there is no bypass path
(CLP-04-007). This requires that `Invite(CoreActor, VulnerabilityCase)` be
recognized as a canonical payload signature, which is why `"CoreActor"` was
added to `_ACTOR_TYPES` in
`vultron/core/behaviors/sync/nodes/canonical_entry.py`.

**Snapshot construction**: the `payloadSnapshot` is built with
`_snapshot_with_context(raw, case_id)` to strip any bare-string inline
object references (`object`, `object_`, `target`) that
`_validate_canonical_entry` would otherwise reject.

---

## `EmitAddCaseParticipantNode` Pattern for `Add(CaseParticipant)` (Issue #1689)

After `PersistInviteeParticipantNode` records the new participant in the
DataLayer, `EmitAddCaseParticipantNode` (in
`vultron/core/behaviors/case/nodes/accept_invite.py`) fans out
`Add(CaseParticipant, Case)` to all existing participants and commits a
canonical `CaseLedgerEntry`.

**Fan-out delivery**: recipients are resolved from
`case.actor_participant_index.keys()` (HTTP actor URLs), **not** from
`case.case_participants` (which stores bare UUID participant IDs as strings
in the DataLayer). Using bare UUIDs as inbox delivery targets causes
`"Request URL is missing 'http://'"` errors. The actor-participant index
keys are always proper HTTP URIs.

**Snapshot bare-ref pattern**: factory methods serialize `target=case_id`
as a bare URI string in the stored activity. `_build_snapshot` must call
`_snapshot_with_context(raw, case_id)` (which calls `_drop_bare_inline_refs`)
before passing the snapshot to `create_commit_log_entry_tree`. Skipping this
step will cause `_validate_canonical_entry` to reject the entry with
`"bare string found"`. See also
`notes/plan/incoming/learnings/20260727-snapshot-bare-ref-pattern.md`.

---

## A Store-Local State Change Is Invisible to Every Replica (Issue #2505)

A node that writes a state change to its own actor's store and stops has
changed nothing that any other participant can see. The ledger is the only
channel through which state crosses actors, so **an unrecorded transition did
not happen** as far as every replica and every ledger-derived check is
concerned.

This is what a spec clause like CM-23-005 — *"Each transition MUST be recorded
as a `CaseLedgerEntry`"* — is actually for. It reads like bookkeeping. It is the
**visibility contract**: the recording is not a log of the transition, it *is*
the transition's only cross-actor existence.

**Why a replica cannot infer the transition from a neighbouring entry.** A
replica-side effect node keys off its own entry's `payloadSnapshot.actor`, so an
actor's transition can never be derived from an entry attributed to somebody
else. Both entries adjacent to the CASE_MANAGER's own `RM.CLOSED` are
attributed elsewhere:

| Entry | `payloadSnapshot.actor` | Why it cannot stand in |
|---|---|---|
| `close_case` | the *departing* actor | `ApplyCloseCaseFromLedgerNode` fires for the leaver, and the Case Actor never sends itself a `Leave` |
| `case_fully_closed` | the *owner* who left | attributed to the owner, and has no effect node at all |

So for months the CASE_MANAGER advanced itself to `RM.CLOSED` correctly
(`AdvanceCaseActorToRMClosedNode`, CM-23-002 step 2) while every replica read it
as permanently `RM.ACCEPTED`. The three bootstrap transitions
(`RECEIVED`/`VALID`/`ACCEPTED`) were recorded; the terminal one was not.
`CommitCaseActorRMClosedEntryNode` (`case/nodes/leave/record.py`) is that
missing record.

**Recording it is best-effort, deliberately.** The node warns and returns
SUCCESS on every path where it cannot produce the entry. CM-23-002 orders this
entry *before* `case_fully_closed` in a single Sequence, so a FAILURE would skip
the final entry and its fan-out — and the enclosing Selector would read the
failed owner arm as "the sender is not the Case Owner" and report SUCCESS down
the non-owner path, leaving a half-closed case with no diagnostic. Losing one
transition's visibility beats losing the case's terminal anchor. `_commit_one`
in `nodes/proposal_ledger.py` makes the same call for the same event type,
reserving hard failure for the load-bearing genesis entry.

**Why this entry is committed synchronously rather than through the loopback.**
The standard path for a protocol-significant event is CLP-10-001: emit an
activity addressed to `case_manager_id` and let HTTP loopback self-delivery
(OX-12-004) drive the received-side commit. That is unavailable here, because
loopback delivery runs as an outbox background task and CM-23-002 requires a
specific *order* — the CASE_MANAGER's own `RM.CLOSED` penultimate,
`case_fully_closed` last. A background task cannot honour that. The entry is
therefore committed inline in the CaseActor's own receive tree, which keeps
ADR-0021's identity contract intact: the commit runs where
`receiving_actor_id == case_actor_id`, not by resolving a foreign actor ID, and
`create_commit_log_entry_tree`'s `DeclineForeignLedgerCommitNode` makes a
replica decline rather than fork the chain.

**The generalisation.** When reviewing any write node, ask what a *different*
actor learns from it. If the answer is "nothing", the node is incomplete no
matter how correct its local write is — and the gap is invisible to any check
that reads the writer's own store. See also `notes/case-state-model.md` for the
RM lifecycle itself, and `notes/sync-ledger-replication.md` for fan-out.
