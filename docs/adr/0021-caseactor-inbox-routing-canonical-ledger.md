---
status: accepted
date: 2026-06-17
deciders: Vultron maintainers
consulted: >-
  notes/case-communication-model.md, notes/case-ledger-authority.md,
  specs/case-ledger-processing.yaml, specs/participant-case-replica.yaml
---

# CaseActor Inbox Routing as the Sole Path to Canonical Ledger Entries

## Context and Problem Statement

The two-actor demo CI invariant test
(`test_invariant_5_expected_event_types_present`) failed after PR #1024
introduced the CASE_MANAGER role gate on `CommitCaseLedgerEntryNode`.
Investigation (issue #1026) revealed that most vendor-side trigger and
received-side use cases never send an activity to the CaseActor's inbox.
Consequently the CaseActor's canonical ledger was missing entries for
`validate_report`, `ack_report`, `add_note_to_case`,
`invite_to_embargo_on_case`, `accept_invite_to_embargo_on_case`, and
`close_case`.

Deeper inspection found that some received-side use cases (`note.py`,
`embargo.py`) worked around this by resolving the CaseActor's ID from the
DataLayer and then executing `create_guarded_commit_case_ledger_entry_tree`
with `actor_id=case_actor_id` — even when the use case was running inside
the **vendor actor's** inbox, not the CaseActor's. This violates the
identity contract documented in ADR-0018 and the identity-spoofing pitfall
in `AGENTS.md`: a received-side use case MUST NOT execute a BT with an
`actor_id` different from the actor whose DataLayer is active. The guarded
commit BT emits `Announce(CaseLedgerEntry)` activities as if authored by
the CaseActor while running in the wrong actor's outbox context, which is
either silently dropped or produces hash-chain divergence.

The project has stated this rule in scattered form across `AGENTS.md`,
`notes/case-communication-model.md`, and `specs/case-ledger-processing.yaml`,
but the explicit, ADR-level statement of the **only correct end-to-end path**
has been missing. As a result, agents and contributors keep re-discovering
the shortcut (resolve CaseActor ID, run BT) and believing it is a valid
"delegation" pattern.

## Decision Drivers

- `notes/case-communication-model.md` establishes that all post-creation
  participant messages route through the Case Actor exclusively.
- ADR-0018 established a single-writer canonical ledger authored by the
  CaseActor. ADR-0019 sharpened the content boundary of that ledger.
- The guarded-commit BT (`create_guarded_commit_case_ledger_entry_tree`)
  already enforces the CASE_MANAGER role gate. The problem is that the
  activity must **arrive at the CaseActor's inbox** before that gate can
  fire; there is no inbox delivery mechanism for events that skip it.
- A received-side use case that resolves a foreign actor ID and runs a BT
  under that ID is the same class of identity-spoofing bug documented for
  the `PrioritizeBT(actor_id=invitee_id)` anti-pattern (PCR-08-009,
  PCR-08-010).

## Considered Options

**Option A — Explicit trigger-tree emit + received-UC pre-flight guard
(this ADR's decision).**
Every protocol-significant trigger tree emits an outbound activity addressed
to `case_manager_id`. ASGI delivers it to the CaseActor's inbox. The
CaseActor's received use case checks `receiving_actor_id == case_actor_id`
before executing the guarded commit — and only executes it when the check
passes. Non-CaseActor received use cases do nothing at the commit step; they
rely on the fact that the CaseActor's inbox will separately receive the same
activity.

**Option B — "Delegation" via foreign actor_id resolution.**
Received-side use cases resolve `case_actor_id` from the DataLayer and
execute the guarded-commit BT with `actor_id=case_actor_id`, regardless of
which actor is actually running the use case. This is the pattern found in
`note.py` and `embargo.py` before this fix.

**Option C — Shared commit helper called directly (no BT).**
Received-side use cases call `commit_ledger_entry()` directly after resolving
the CaseActor ID, bypassing the BT and the role gate.

## Decision Outcome

Chosen option: **Option A — Explicit trigger-tree emit + received-UC
pre-flight guard**.

The canonical ledger entry path is:

```text
Trigger tree
  → emits outbound activity addressed to case_manager_id
  → ASGI delivers to CaseActor inbox
  → CaseActor's received use case runs with actor_id = case_actor_id
  → pre-flight guard: receiving_actor_id == case_actor_id  [PASS]
  → guarded commit BT executes with actor_id = case_actor_id
  → CommitCaseLedgerEntryNode authors and broadcasts CaseLedgerEntry
```

When the activity is received by a **non-CaseActor** actor:

```text
Non-CaseActor received use case runs with actor_id ≠ case_actor_id
  → pre-flight guard: receiving_actor_id == case_actor_id  [FAIL]
  → commit step skipped entirely — no delegation, no BT, no spoofing
```

The pre-flight guard MUST use `receiving_actor_id` (the actor whose inbox is
active), not a separately resolved CaseActor ID. This is the pattern already
implemented correctly in `status.py`'s `_commit_log_cascade_bt()` and MUST
be applied to every received-side use case that participates in ledger entry
authorship.

**Why `announce_case_ledger_entry` is excluded from `EXPECTED_EVENT_TYPES`:**
`Announce(CaseLedgerEntry)` is the replication envelope: the mechanism by
which the CaseActor broadcasts its canonical entries to participants. It
cannot appear as the `payloadSnapshot` of a canonical entry because the
snapshot is the protocol activity that *triggered* the entry, not the
replication envelope that *delivers* it. Including it in `EXPECTED_EVENT_TYPES`
for the case-actor log creates a circular requirement that can never be
satisfied without corrupting the ledger.

### Consequences

- Good, because the delivery mechanism (ASGI self-delivery) is the same
  trusted path already proven to work for case creation and status events.
  No new infrastructure is needed.
- Good, because the pre-flight guard keeps received-side use cases honest:
  a use case that runs in a non-CaseActor inbox simply skips the commit step
  instead of spoofing the CaseActor's identity.
- Good, because the rule is symmetric with the existing "actor MUST NOT
  spoof another actor's identity" pitfall and can be enforced structurally
  (the BT's CASE_MANAGER role gate fires naturally once the activity arrives
  at the right inbox).
- Bad, because every trigger tree that currently omits an emit node needs
  one added — this is a mechanical but non-trivial change spread across
  multiple trees.
- Bad, because received-side use cases that currently use the Option B
  shortcut must have their shortcut removed and replaced with a strict
  pre-flight guard, which is a semantics-changing fix that requires new
  tests.

## Validation

- `specs/case-ledger-processing.yaml` CLP-10 codifies the requirements
  from this ADR as MUST-level rules.
- CI test `test_invariant_5_expected_event_types_present` (parameterized
  per event type after issue #1026 implementation) is promoted from `xfail`
  to a hard assertion for each event type as its routing gap is closed.
- A grep-based test (CLP-09-002) asserts that no bare, unguarded commit
  invocation exists outside the guarded-commit factory.

## More Information

- Issue #1026 — root-cause analysis and fix plan.
- ADR-0018 — single-writer canonical ledger established.
- ADR-0019 — content boundary of the canonical ledger established.
- `notes/case-communication-model.md` — canonical communication flow,
  including antipattern sections.
- `specs/case-ledger-processing.yaml` CLP-09 — commit authorization and
  coverage requirements that this ADR extends.
- `specs/case-ledger-processing.yaml` CLP-10 — normative requirements
  generated from this ADR.
