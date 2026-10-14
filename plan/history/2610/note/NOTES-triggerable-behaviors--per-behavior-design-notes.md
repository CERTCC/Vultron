---
source: NOTES-triggerable-behaviors--per-behavior-design-notes
timestamp: '2026-10-12T19:34:28.527844+00:00'
title: Per-Behavior Design Notes
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered or superseded — embargo, CVE ID assignment, and participant triggers are built; party identification moved to suggest-actor-to-case and a Sentinel capability (ADR-0047)
**Superseded by:** `vultron/core/behaviors/embargo/`, `vultron/core/behaviors/report/assign_cve_id_tree.py`, suggest-actor-to-case trigger, ADR-0047, `specs/embargo-policy.yaml`

---

## Per-Behavior Design Notes

### Embargo Evaluation (evaluate-embargo)

"evaluate" in the embargo tree has two layers:

1. **Mechanical evaluation** (automatable): Does the proposed embargo have
   a valid end date? Is the duration within the actor's policy limits?
   (See `specs/embargo-policy.yaml`.) Does it follow the practices in
   `docs/topics/process_models/em/`?

2. **Judgment evaluation** (human-in-the-loop or LLM-assisted): Is the
   embargo duration proportionate to the case? Is the justification
   reasonable? Are the terms commensurate with the coordinating parties'
   constraints?

**Design Decision**: Implement the mechanical layer first. Stub the
judgment layer as a placeholder that always returns SUCCESS.

### Embargo Proposal (propose-embargo)

"Select terms" during embargo proposal is a judgment call that CAN be
stubbed as "apply default embargo policy" (see
`docs/topics/process_models/em/defaults.md`). The stub SHOULD:

1. Load the actor's `embargo_policy` record (see `specs/embargo-policy.yaml`).
2. Apply the preferred duration as the proposed term.
3. Log the selection.

A "customize defaults" extension point SHOULD be stubbed as a placeholder
node that always succeeds and logs a debug event.

Emit EV and Emit EP may have side effects; cross-reference
`docs/topics/process_models/em/` for the specific state transitions
triggered by each.

### Embargo Termination (terminate-embargo)

"other reason?" is a judgment call; stub as a placeholder. "timer expired?"
is a condition check that can be implemented as a direct comparison of the
current time against the embargo end date in the `EmbargoEvent`.

"exit embargo" is a local process placeholder for external callback hooks
(e.g., triggering advisory publication pipelines). It MUST log when
executed.

### CVE ID Assignment (assign-cve-id)

`docs/topics/behavior_logic/id_assignment_bt.md` describes a simplified
tree based on CNA rules. Implementation guidance:

- "id assigned?" — condition check; query case for existing CVE ID.
- "is CNA?" — condition check; query actor profile for CNA role.
- "in scope?" / "assignable?" — partially automatable via CNA Rules
  4.1 (<https://www.cve.org/resourcessupport/allresources/cnarules#section_4_CNA_Operational_Rules>).
  This is a candidate for an LLM-assisted evaluator: present the case
  and the relevant CNA rule text, ask the evaluator to answer a series
  of structured questions about scope and assignability.
- "emit CVE" — execution task; call CVE Services API or record a
  locally-generated placeholder ID.

### Identify Participants (identify-participants)

This is a judgment call well-suited to LLM assistance or human review:

1. Present the case information and ask an evaluator to identify potentially
   affected parties (vendors, coordinators, affected users).
2. The evaluator suggests new participants.
3. A human or policy rule reviews and confirms the suggestions.
4. For confirmed suggestions, trigger the "notify-others" flow (which uses
   `Invite(Actor, CaseStub)` semantics — see below).

The `Suggest(Actor)` protocol message is already semantically supported,
which enables an agent workflow where a suggester-agent evaluates cases and
proposes participants, and the case owner accepts or rejects those proposals
via the normal accept/reject flow.

### Notify Others (notify-actor)

The "notify others" behavior (report to others) iterates over a list of
potential participants and sends each an `Invite(Actor, CaseStub)` message.
Key design constraints:

1. **Embargo must be established first** (or the invitation implies
   acceptance of existing embargo terms). Before sending an `Invite`, the
   system SHOULD verify that either:
   - No embargo is active, or
   - The actor being invited is known to have compatible embargo policy
     (see `specs/embargo-policy.yaml`), or
   - The invitation is constructed to imply embargo acceptance upon
     acceptance of the invitation.

2. **Pre-acceptance information sharing**: Before an invited actor accepts,
   the case information shared with them SHOULD be restricted to a
   "invitation-ready" subset (see below). Full case details SHOULD only
   be shared once the invitation is accepted.

3. **Triggering**: This behavior MAY be triggered event-by-event (i.e.,
   one invitation per trigger call) rather than as a batch loop. This
   allows it to be fired immediately when a new participant is identified
   without requiring a separate batch-iteration mechanism.

4. **"effort limit exceeded?"** — stub as a placeholder that always
   succeeds (no-op for prototype); log when executed.
