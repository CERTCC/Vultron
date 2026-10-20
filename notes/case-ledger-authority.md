---
title: Case Ledger Authority and Assertion Recording
status: active
kind: guidance
description: >
  Rules for the canonical case ledger: participant assertions versus
  CASE_MANAGER-admitted entries, the three authority/address/store questions,
  what belongs in the ledger, one entry per change and one transaction per
  act, the two timestamps, native
  case-initialization entries, the genesis hash, and why an unrecorded transition
  is invisible to every replica.
related_specs:
  - specs/architecture.yaml
  - specs/case-ledger-processing.yaml
  - specs/case-management.yaml
  - specs/case-proposal.yaml
  - specs/sync-ledger-replication.yaml
  - specs/sync-behavior-trees.yaml
  - specs/embargo-policy.yaml
related_notes:
  - notes/bt-integration.md
  - notes/case-joining.md
  - notes/case-proposal.md
  - notes/demo-interactive-ui.md
  - notes/activitystreams-semantics.md
  - notes/case-communication-model.md
  - notes/participant-embargo-consent.md
  - notes/case-state-model.md
  - notes/configuration.md
  - notes/domain-validation.md
  - notes/embargo-lifecycle.md
  - notes/ownership-transfer.md
  - notes/sync-ledger-replication.md
  - notes/case-ledger-parsing.md
  - notes/case-ledger-genesis-hardening.md
  - notes/wire-artifact-immutability.md
  - notes/outbox-delivery-reliability.md
  - notes/participant-case-replica.md
  - notes/demo-ci-diagnostics.md
  - notes/rfc-review-rubric.md
relevant_packages:
  - vultron/wire/as2
  - vultron/core/models
  - vultron/core/behaviors
---

# Case Ledger Authority and Assertion Recording

Normative requirements are in `specs/case-ledger-processing.yaml` (CLP). This note
holds the rules that keep code near the commit boundary from repeating known
mistakes.

## Assertions and Admitted Entries

Inbound case- or proto-case-scoped activities from participants are
**assertions** by default: `Offer(Report)` asserts a report was submitted,
`Add(Note)` that a note was added, `Invite`/`Accept`/`Reject` that the sender did
those things. No `mode = asserted` marker is needed; the sender role and path
already say it. A report is a proto-case (ADR-0015), so logging starts at report
receipt.

A **canonical `CaseLedgerEntry`** is the CASE_MANAGER's record that an assertion
was **admitted** (CLP-04-007). The vocabulary is *asserted* / *admitted* /
*refused*, never "intent vs event".

The CASE_MANAGER is the single writer of shared history. It receives an
assertion, validates it, appends an entry, and replicates only that entry.
Participant replicas never update shared state straight from peer messages.

## Three Questions That Look Like One (ADR-0088)

Code near the commit boundary asks three questions that all sound like "who is
the CaseActor here?". Conflating any two has produced bugs.

| Question | Answered by | Signal |
|---|---|---|
| Am I the authority? | `resolve_case_manager_id` / `CheckIsCaseManagerNode` | The `CVDRole.CASE_MANAGER` role, and nothing else |
| What address do I route to? | `_find_case_actor_id` | The role-holder's id, or a `ReportCaseLink`-recorded address during bootstrap |
| May *this store* append here? | `DeclineForeignLedgerCommitNode` / `store_for_actor` | Whether the store in hand holds the log |

- **Authority is the role (CM-02-011).** Not a hosting location or URL shape.
  "Case Actor" is a demo label; no protocol logic may branch on the string
  (CM-02-013, `test/architecture/test_role_authority_resolver.py`).
- **Address resolution is downstream of authority** (ARCH-24-005). A `None` from
  `_find_case_actor_id` means "no resolvable address", never "no authority".
- **The store guard is not an authority check** (ARCH-24-005). It raises when a
  commit would mint an index in a store that is not the log's home, which would
  fork the chain; no sanctioned path gets there (CLP-10-014, ADR-0109).
- **A resolver that cannot answer says so.** Never fall back to "the first
  `Service` in the store": a failed lookup must not look like a successful one.

## `CaseLedgerEntry` Is the Canonical Content Object

The canonical object is a neutral `CaseLedgerEntry`, not a renamed copy of the
activity and not the transport envelope. It carries the asserted activity (or a
deterministic snapshot of it) plus the CASE_MANAGER's recording metadata
(`log_index`, `entry_hash`, `received_at`, `prev_log_hash`, `term`). `Announce`
is only the replication wrapper around it.

Replicas need the asserted content to rebuild state, so the hash chain is
computed over entries that each include the payload snapshot, never over pointers
to prior assertions.

**Planned: `semantic_type` is the registry's label for the payload (ADR-0140,
proposed).** Every payload is a valid AS2 activity, and an entry's `semantic_type`
must equal the semantic type the registry assigns to its `payload_snapshot`,
including for the CASE_MANAGER's own acts. Today each write path stamps
`semantic_type` from its own string constant. The shapes for ledger-only acts are
decided in #4723; the equality test is #4724.

**The field is `semantic_type`, wire key `semanticType` (CLP-02-014).** The
glossary names "event type" as a term to avoid for it. The hash chain hashes
the field under its own name, as `object_id` already is. An entry still
carrying the retired `eventType` key is refused, never aliased: a stored row
means the store must be reset, a received one that its sender is out of date
(`notes/datalayer-design.md`).

## Refusals Go to the Process Log

Only admitted assertions enter the ledger; there is no disposition field.

- A message that cannot be tied to a case or proto-case is a transport/actor
  diagnostic: Python `logging` only.
- A case-resolvable message refused by a precondition guard gets a `Reject` sent
  to the asserting participant alone (CLP-05-001) plus a log event. Nothing enters
  the hash chain (CLP-05-002). Other participants need canonical history, not
  failed attempts.
- The `Reject` wraps the refused activity inline, `inReplyTo` its id, with the
  guard's reason in `summary` (ADR-0141). `create_receive_activity_tree` adds
  it to every tree that commits to a case and has precondition guards
  (CLP-10-022); a tree never sends it itself, nor from `execute()`. A tree whose
  refusals are answered otherwise names a registered `RefusalNoticeExemption`
  (`case/nodes/refusal_notice.py`) that says how, pinned by
  `test_received_tree_refusal_notice.py`. A sender-guard refusal and a
  `SKIPPED` repeat get none. A guard that can fail as a repeat implements
  `ReportsIdempotentRepeat` (`behaviors/idempotency.py`), or the stage reads its
  repeat as a refusal and answers it. The reason is read by the sender, so it
  names the sender's own standing only.
- A `Reject(Invite)` or `Reject(Offer)` refusal notice has the shape of a decline;
  the sender reads it with the decline's use case, which closes the pending entry.
  Do not add a pattern to tell them apart: the request had no effect either way
  (CLP-05-001).

The Python log is per-actor and ephemeral; never replicate it or rely on it for
protocol semantics (ADR-0019).

## Every Change Is an Entry; Replicas Copy (ADR-0124, CLP-07-013)

Two replicas at the same ledger position hold identical case files only if the
replica decides nothing:

- **One act can commit several entries.** The act's entry comes first, then one
  CASE_MANAGER-authored entry per further change, in write order: `Create(Object)`
  for a new record, `Update(Object)` for a changed one, each carrying the object
  in full. A stub Invite is the Invite's entry plus a `Create(CaseParticipant)`
  for the inert invitee.
- **An act whose activity states the change is that change's entry.**
  `Add(Note, target=Case)` is applied by copying the note; an invitee's `Accept`
  of the stub Invite is the entry for its consent row and `joined` mark
  (CM-31-012). No second entry records either again (CLP-07-002).
- **A replica copies.** Applying an entry mints no id, reads no clock, reads no
  policy or state outside the case, and runs no lifecycle logic (CM-23-016).
  Lifecycle and policy code runs on the CASE_MANAGER before the commit.
- **Case file vs. case bookkeeping (CLP-07-014).** The recommendation index,
  offer records and pending markers are the CASE_MANAGER's working records: not
  ledgered, not replicated, never read to compute a case-file value.
- **No allow-list.** A write with no entry is a defect. `NO_REPLICA_EFFECT` in
  `test/architecture/test_ledger_semantic_types_are_replayed.py` lists committed
  types that change nothing a replica holds; it is not a place to park an
  unreplayed write. `EXEMPT` in `test/architecture/test_ledger_commit_coverage.py`
  lists routed activities that commit nothing: each row is a CLP-02-013 ground
  (not a case event) or the open issue that owns the missing commit. A handler
  believed to need no entry that fits no ground is an amendment to CLP-02-013
  first, never a new row.
- **The rebuild check.** Every exchange demo and every `LedgerNetwork` scenario
  is rebuilt from the CASE_MANAGER's ledger into an empty store when it ends,
  and its roster, participant records, consent rows and embargo register must
  equal the CASE_MANAGER's (`test/support/ledger_rebuild.py`, #4294). A test
  that writes the CASE_MANAGER's store outside the ledger on purpose, as setup,
  calls `LedgerNetwork.bypass_ledger()`; a production write with no entry is
  the defect the check exists to find, never a reason to bypass it.

**Pitfall: "one act, one entry".** That reading leaves the second change an act
causes with nowhere to be recorded, and replicas rebuild it with their own ids
and times (#4425).

**Pitfall: "a failed commit is retried by the next act".** It is not: a repeated
trigger starts a new act and a redelivered one stops at its idempotency guard. So
an act never leaves work for a later run: `commit_and_apply_embargo_entries()`
trial-applies, commits every entry and saves the case file inside one
`CasePersistence.transaction()`, and any failure writes nothing. Never add a
stored plan, a finishing node or a per-act repair pass; put the act's writes
inside the transaction instead (CLP-07-015, ADR-0146). A later node that commits
a consequence of the act (the stub re-issue, a proposal's relay) runs in the
same transaction: compose the act's commit node and it into one `ActTransaction`
(`vultron/core/behaviors/act_transaction.py`), through
`create_case_manager_gated_tree(as_one_act=True)` or
`create_receive_activity_tree(as_one_act=True)` (#4949). In a received tree the
act block also holds the guarded commit of the act's own entry, so a failed
received act keeps no entry, and a later delivery is not stopped as a repeat
(ADR-0151).

### Two Meanings of "Reject"

| What | Word | Ledgered? |
|---|---|---|
| A participant's AS2 `Reject` / `TentativeReject` answering an `Offer` or `Invite` | Reject (the activity) | **Yes** — a case event, like the matching `Accept` |
| The CASE_MANAGER's verdict that an assertion does not enter the ledger | **refused** (never "rejected") | No (CLP-04-007) |
| The notice the CASE_MANAGER sends the asserter about that verdict, and a replica's `Reject(CaseLedgerEntry)` sync-repair request | Reject (the activity), about the ledger itself | No — not case events (CLP-02-013) |

The positive verdict is **admitted**, not "accepted". `HandlerDisposition.REFUSED`
is the handler-level form of the refused verdict.

**Pitfall: "a decline changes nothing, so there is nothing to commit".** A Reject
closes a request/reply pair, and whether a pair is open is read from the ledger
(CLP-11-001). An unledgered Reject leaves every replica holding a request that
never closes (#3748).

**Whether an activity is ledgered is not decided per handler.** Every admitted
case event is ledgered (CLP-02-001). CLP-02-013 closes the list of activities
that are not case events, and `test/architecture/test_ledger_commit_coverage.py`
(CLP-09-003) fails any routed use case that reaches no commit without one of
those grounds or an open tracking issue. Read that list instead of opening a
design question. A handler only a participant runs, receiving what the
CASE_MANAGER sent, has nothing to commit there: the entry, if the activity is a
case event, is the CASE_MANAGER's at sending (CLP-09-001, CLP-09-003).

## `pending_assertions`: Local Decision-Suppression Memory

Actor-local `pending_assertions` (`vultron/core/models/pending_assertion.py`)
suppresses duplicate emits during the canonical round trip. It is temporary local
memory, not a second source of truth. A timeout marks the assertion `timed_out`
and logs an error but never auto-retries; a matching canonical entry clears it.

## Canonical Entry Criteria: What Belongs in the Log

The ledger is a protocol ledger, not a process log (ADR-0019). Each act's entry
has the verbatim asserted AS2 activity (or a deterministic normalization) as its
`payloadSnapshot`, followed by its consequence entries (CLP-07-013).

**Belongs:** `Offer(VulnerabilityReport)`, `Add(Note)`, `Add(ParticipantStatus)`,
`Offer`/`Accept`/`Reject(EmbargoEvent)`, the stub and full-case `Invite`s with
their `Accept`/`Reject` (routed through the CASE_MANAGER, PCR-08),
`Announce(VulnerabilityCase)`, and any other activity that changes
protocol-visible state.

**Does not belong:** checkpoint markers (`demo_verification`), runtime
diagnostics, "reached step N" traces, cascade triggers, sentinels, scheduling
events, and anything whose `payloadSnapshot` would be empty or whose
`logObjectId` names the case itself. Those go to Python `logging`
(`specs/structured-logging.yaml`).

**Why:** the ledger is replicated and hash-chained. Non-protocol content would
force replicas to filter it, make the chain sensitive to runtime timing, and stop
operators adding log detail freely.

### `Announce` Envelope vs. `payloadSnapshot` Actor

The `Announce` envelope's `actor` is always the CASE_MANAGER. The
`payloadSnapshot.actor` keeps the original asserter, and replicas apply the
snapshot's asserter. Never rewrite `payloadSnapshot.actor` to the CASE_MANAGER;
it erases provenance (CLP-07-003).

### An Act and Its Consequences Are Separate Entries

CLP-07-002 bars two entries for the *same* change, but an act and the changes it
causes are different facts. For a `Leave`, the CASE_MANAGER commits the
`close_case` entry, then one participant-status entry per RM transition it writes
for the leaver (`V → D → C` is two), in that order (CM-23-001). Replicas apply
the status entries and never derive a closure path from their own state.

The status entries are the CASE_MANAGER's own writes, so their
`payloadSnapshot.actor` is the CASE_MANAGER; the leaver's act stays attributed to
the leaver in `close_case`. A replica copies each step as carried; it refuses
only a step whose composite state is impossible (RSH-09-006), and then writes
nothing in its place. Every activity-typed RM move works the same way: the
report verdicts, engage/defer and the full-case Invite replies commit the act,
then the status the CASE_MANAGER wrote (`CommitParticipantStatusEntriesNode`,
CLP-07-013); the act's own entry changes nothing on a replica.

### A Sent Message Is Committed After Its Outbox Write (SYNC-09-002)

Queue the activity, then commit the entry that records it; only
`Announce(CaseLedgerEntry)` follows its commit, because it delivers the record
(SYNC-09-002, SBT-04-004, ADR-0119). A retry must rebuild the activity under its
first id or it sends it twice; see
[outbox-delivery-reliability](outbox-delivery-reliability.md) § "A Response to an
Inbound Activity Takes Its Id From the Request".

### Commit-Boundary Enforcement

The commit boundary refuses entries that break CLP-07-001 through CLP-07-004
before they enter the chain (CLP-07-005). Failing at commit keeps the chain clean
and surfaces bugs at once instead of as replica divergence.

The CLP-07-003 actor-identity check lives in `CommitCaseLedgerEntryNode`
(`vultron/core/behaviors/case/nodes/lifecycle.py`), where the original
`activity.actor_id` is available, **not** in `_validate_canonical_entry`. A
CASE_MANAGER may legitimately self-assert participant activities (ADR-0088), and
a commit-boundary identity check false-rejects those (#3282). Do not move the
comparison back. `_CASE_AUTHORED_SIGNATURES` stays: CLP-12-002's native-init
coverage check needs it.

### An Entry Has Two Timestamps, and They Belong to Different Layers

`CaseLedgerEntry.published` is the CASE_MANAGER's **commit** stamp.
`payloadSnapshot.published` is the asserter's **claimed** event time (CLP-14,
CLP-15, ADR-0079). Pick the wrong one and a check is vacuous or falsely refuses.

- Commit-time invariants hold by construction (one writer, one clock). Only the
  conformance harness (`check_clp14_timestamp_invariants`) sees a whole ledger,
  so they belong there; an entry never sees its predecessor, so the model layer
  cannot enforce them.
- Claimed-time invariants (CLP-14-006/007/008, CLP-15-003) cannot hold by
  construction, so they belong in `_validate_entry_timestamps` at the commit
  boundary.

Rules:

1. **Claimed-time monotonicity is per snapshot actor.** Comparing across actors
   is the wall-clock ordering ADR-0079 rejected.
2. **CLP-15-003 is reported, never refused.** The CASE_MANAGER sees arrival
   order, not causal order (ADR-0037). Refusing loses the assertion entirely,
   because the guarded commit precedes the effects (CLP-10-006). Report at
   `INFO` within the clock-skew tolerance, `WARNING` beyond it.
3. **A snapshot built on a participant's behalf carries that participant's
   claimed time** (`claimed_published_iso()`). Stamping `now_utc()` under a
   participant's URI puts a foreign clock in its stream. A snapshot the
   CASE_MANAGER genuinely authors (its own URI, such as the `Leave` closure
   status entries) uses its own clock. One exception: the expired-invitation
   entry from the owner-close settle step (CM-23-014) or the overdue-invitation
   sweep (CM-28-015) names the invitee in `actor` but carries the
   CASE_MANAGER's clock, because the invitee sent nothing. When the sweep's
   invitee is the sender of the activity that prompted it, its own entry would
   precede that activity's entry, so it carries the activity's claimed time
   instead, as the late-`Accept` expiry does. Do not copy the CASE_MANAGER's
   clock to any other entry a participant's own entries can follow.
4. **A missing or blank top-level inbound `published` is refused at parse**
   (CLP-15-006, MV-03-002): the wire default would otherwise pose the
   receiver's clock as the sender's claim. A present, non-blank but unreadable
   value stays a schema fault. Nested objects may omit `published` and are
   taken as received (ADR-0103); refuse only where a decision needs the time
   (CLP-08-002, CLP-14-002, CLP-02-008). Rebuild core objects from a snapshot
   through `project_wire_snapshot_to_core`, never `Model.model_validate(snapshot)`,
   or the `default_factory` stamps the replica's clock.
5. **Never gate a whole guard on one optional argument.** Gate each check on the
   context it needs, and test enforcement through the production node, not the
   private validator.

CLP-15-001/002 bind the participant and CLP-15-005 forbids the CASE_MANAGER from
reconstructing a participant's causal order; they are verified by
`check_causal_edges` (DEMOMA-22-005), not per assertion.

## Native Case-Initialization Entries (ADR-0041)

The CASE_MANAGER commits every initialization entry natively in
`CommitNativeLedgerEntriesNode` (`vultron/core/behaviors/case/nodes/proposal_ledger.py`)
while handling `Create(as_CaseProposal)` (CM-22-003, CLP-12). The create-case
trigger composes the same node (`create_case_trigger_tree.py`), its creator being
owner and CASE_MANAGER, so both creation paths commit one sequence; do not add a
second copy (CLP-07-013). Order:

1. `create_case` — `Create(VulnerabilityCase)`, actor CASE_MANAGER
2. `add_report_to_case` — actor CASE_MANAGER
3. per seated record, `create_case_participant` — `Create(CaseParticipant)`
   carrying the record as created (roles, consent rows, its first status), then
   `add_participant_status_to_participant` for each later status (the
   CASE_MANAGER's VALID, ACCEPTED; CM-23-007) — actor CASE_MANAGER
4. `add_case_status_to_case` — actor **vendor URI**

Each snapshot is the CASE_MANAGER's factory-built activity, sealed and committed
verbatim: the `record_*` methods of `TriggerActivityPort`
(`trigger_activity_adapter/ledger.py`). Core builds no snapshot dict itself
(VM-08-003; `test/architecture/test_no_hand_built_payload_snapshots.py`).
A record is sealed, not stored as an activity (`_seal_record`): it is no
message, and a scan for the messages sent (one `Create(VulnerabilityCase)` per
case, CP-09-009) must not count it. Its id is derived from the CASE_MANAGER and
what changed, so a retry hands back the first sealed body (ID-04-004).

- **Exactly one participant-status entry per participant** (CM-18-007). The
  default embargo is set before PEC state is fixed, so the single snapshot already
  carries the true consent value. A second entry shifts every downstream
  `log_index` and breaks "`log_index` order is causal order".
- **Every creation entry is required.** The first entry that fails to commit
  stops the sequence and the node returns FAILURE, so no later entry lands out
  of order (CLP-07-013, #4442). On both paths the node runs after the `Create`
  is queued (CM-14-011, CP-09-009, SYNC-09-002), so the failure is surfaced, not
  prevented. Only the trigger path can undo a failed genesis: it withdraws the
  still-pending `Create` from the outbox (`outbox_withdraw`) and the case with it,
  and keeps the case once delivery has taken the `Create`.
- **Step 4 names the vendor** because the vendor set the genesis status.
  `("Add", "CaseStatus")` is also in `_CASE_AUTHORED_SIGNATURES` (CLP-12-001), so
  single-actor deployments (vendor is the CASE_MANAGER) validate too. That
  signature entry is correct, but adding it was never a substitute for removing
  the old two-init-path back-fill: the report receiver authors no initialization
  entry (CM-22-003, ADR-0041).

## Per-Case Genesis Hash (CLP-08)

The genesis hash is
`SHA-256(case_id + "|" + created_at.isoformat() + "|" + owner_actor_id)`, with
`owner_actor_id` the case owner (`attributed_to` at creation), on every creation
path (ADR-0117). There is one formula, `compute_genesis_hash`, called by the
`VulnerabilityCase` validator when no hash is supplied:

- A creator sets `attributed_to` and passes no hash.
- A replica keeps the `genesisHash` it received. A received case with none
  derives it from its carried `attributedTo` and `published` (ADR-0103).

A computable hash still leaves a targeted-DoS gap; the planned fix is in
[case-ledger-genesis-hardening.md](case-ledger-genesis-hardening.md).

## Snapshots Are the Factory's Exact Blob

- `EmitInviteActorToCaseNode` commits its entry through
  `create_commit_log_entry_tree`, and every entry passes
  `_validate_canonical_entry`; there is no bypass (CLP-04-007).
- The `payloadSnapshot` is `json.loads(activity_blob)`, the exact blob the outbox
  delivers (VM-08-003). Core never strips or patches it.
- That Invite commit is the only one (ADR-0109, CM-17-006). An Invite that loops
  back to the CaseActor (for example via `cc:`) would be committed twice; one
  entry per `payloadSnapshot.id` is asserted by the invariant harness (CLP-07-002).
- `_validate_canonical_entry` accepts a bare-string `target` **only when it
  equals the entry's case URI**, at any depth; any other bare string in an
  inline-object slot is refused (CLP-07-006). Do not add a core-side rewrite to
  satisfy the validator; fix the factory.

## A Store-Local State Change Is Invisible to Every Replica

The ledger is the only channel by which state crosses actors, so **an unrecorded
transition did not happen** for every replica and every ledger-derived check. A
clause like CM-23-005 ("each transition MUST be recorded as a `CaseLedgerEntry`")
is the visibility contract, not bookkeeping.

A replica effect keys off its own entry's `payloadSnapshot.actor`, so one
actor's transition can never be inferred from an entry attributed to someone
else. Hence the CASE_MANAGER's own `RM.CLOSED` needs its own entry
(`CommitRMClosureEntriesNode`, `case/nodes/leave/record.py`); neither
`close_case` (the leaver) nor `case_fully_closed` (the owner) can stand in.

Owner-close order: `close_case`, the Case Owner's RM steps, the CASE_MANAGER's
own steps, one expired-invitation entry per pending Invite, then
`case_fully_closed` (CM-23-002, CM-23-014). `close_case` has no replay slot
(CM-23-001, CM-23-016).

- **Recording is best-effort.** The node warns and returns SUCCESS where it
  cannot produce the entry, because a FAILURE would skip `case_fully_closed` and
  the enclosing Selector would misreport the owner arm. A nested result flagged
  `internal_error` still raises `VultronBTInternalError`, so a bug never reads as
  a WARNING (#4113).
- **It is committed inline, not through the loopback.** CM-23-002 needs a fixed
  order, which a background outbox task cannot honour. The commit runs where
  `receiving_actor_id == case_actor_id` (ADR-0021), and
  `DeclineForeignLedgerCommitNode` keeps any other store from minting an index
  (CLP-10-014).

**When reviewing any write node, ask what a different actor learns from it.** If
the answer is "nothing", the node is incomplete, and no check that reads the
writer's own store will notice. See
[sync-ledger-replication.md](sync-ledger-replication.md) for fan-out.
