---
status: accepted
date: 2026-08-26
deciders: Allen D. Householder
consulted: CERTCC/Vultron contributors
informed: Vultron protocol working group
lint_suppress: [status_prose_contradiction]
---

# Retire `CVDRole.FINDER` — Reporter Is the Protocol-Salient Role

## Context and Problem Statement

The Vultron protocol models multi-party CVD as a Communicating Hierarchical State
Machine. Each Participant runs a process, and $N$ is the count of unique
Participants. The formal protocol definition (Brand & Zafiropulo,
`docs/reference/formal_protocol/index.md`) characterised the participant pool as
"Finders, Vendors, Coordinators, Deployers, and Others."

The draft Vultron Protocol Spec (PR #2078, §7.3.1) provisionally listed `Finder`
as a protocol role while deferring its finalisation pending this ADR. The note
read:

> **Finder** still requires an ADR before the removal can be treated as normative.

Separately, `CVDRole.FINDER` is present in the implementation enum
(`vultron/enums/roles.py`), and convenience subclasses `FinderParticipant` and
`FinderReporterParticipant` exist in `vultron/core/models/case_participant.py`.

The question this ADR answers: should Finder be a distinct, protocol-recognised
role, or should it be retired?

## Decision Drivers

- **Protocol neutrality**: The protocol cares about who *reports* a
  vulnerability, not about who *found* it. A Finder who reports their own
  finding acts as a Reporter. A Finder who asks someone else to report acts as
  a source of information for that Reporter. Neither interaction requires a
  dedicated protocol role.
- **Formal model alignment**: The $N$ definition in
  `docs/reference/formal_protocol/index.md` already uses the formula
  $N = |Reporters \cup Vendors \cup Coordinators \cup Deployers \cup Others|$
  — not Finders. The prose description that said "Finder" was already
  inconsistent with the formula. The formula is correct.
- **Role simplicity**: Fewer roles reduces the combinatorial surface of role
  stacking (CM-26). A role that adds no protocol obligations and can always be
  expressed via another role is a source of confusion for implementers.
- **Circulation blocker**: PR #2078 identified the missing ADR as a blocker for
  external circulation of the draft spec. Resolving it unblocks the spec.

## Considered Options

1. **Retain `CVDRole.FINDER` as a distinct protocol role** — keep the current
   status quo, add normative requirements for Finder behaviour.
2. **Retire `CVDRole.FINDER`; record discoverer identity as report metadata** —
   remove Finder from the CVD role taxonomy. Any actor that discovers and reports
   a vulnerability holds the `REPORTER` role. An actor that discovers but does not
   report may be credited in the Report's free-text fields or in case Notes.
3. **Retain `CVDRole.FINDER` as a non-normative annotation** — keep the value in
   the enum as an informational tag only, with no protocol obligations or
   permissions associated with it.

## Decision Outcome

Chosen option: **Retire `CVDRole.FINDER`** (option 2), because:

- Nothing in the protocol state machines (RM, EM, CS, PEC) distinguishes a
  Finder from a Reporter. A Finder that enters the protocol is a Reporter.
  Adding normative requirements for Finder (option 1) would require inventing
  protocol obligations that do not exist in the specification's source material.
- Option 3 (non-normative annotation) retains the implementation surface and
  all the confusion it creates while providing no protocol value in return.
- The formal $N$ formula already expresses the correct model; the prose
  description of "Finders" in `docs/reference/formal_protocol/index.md` was an
  artefact of earlier CERT/CC CVD terminology and is inconsistent with the
  formula itself. Aligning the prose with the formula is the minimal correct fix.
- The "Note on Reporter" already in draft §7.3.1 captures the relationship
  precisely: the protocol is concerned with who reported, not who found.

**Normative scope of this decision:**

- `CVDRole.FINDER` is **retired** from the Vultron CVD role taxonomy.
- The discoverer of a vulnerability SHOULD be recorded in the Report content or
  in case Notes; it is metadata, not a protocol role.
- The formal protocol process count $N$ is defined over Reporters, Vendors,
  Coordinators, Deployers, and Others (the formula already in place).
- An actor who discovers and reports a vulnerability simultaneously holds
  `CVDRole.REPORTER`. There is no separate "Finder-Reporter" combined role;
  `REPORTER` is sufficient.

### Consequences

- Good, because the formal $N$ definition and the role taxonomy are now
  consistent with each other.
- Good, because role stacking complexity (CM-26) is reduced by one role.
- Good, because the draft spec §7.3.1 provisional marker is removed and Open
  Question #5 is resolved, unblocking external circulation.
- Neutral, because the implementation change (removing `CVDRole.FINDER` from
  `vultron/enums/roles.py`, retiring `FinderParticipant` and
  `FinderReporterParticipant`) is a follow-on task; the enum value is retained in
  the code until that task ships. Wire actors in demo scenarios that hold the
  "Finder" conceptual role hold `CVDRole.REPORTER` (or `CVDRole.REPORTER` +
  `CVDRole.OBSERVER`) in practice.
- Watch out: code and specs that reference `CVDRole.FINDER` directly must be
  updated in the follow-on task. Until that task ships, `CVDRole.FINDER` remains
  a valid (if deprecated) wire value and implementers may encounter it in stored
  data.

## Validation

- Spec: no new spec entries are generated by this ADR; the existing role taxonomy
  in `specs/participant-role-management.yaml` and `specs/case-management.yaml`
  will be updated in the follow-on implementation task to remove FINDER references.
- Draft spec: §7.3.1 provisional note removed; Open Question #5 struck.
- Formal protocol doc: prose description updated from "Finder" to "Reporter".
- ADR index updated.

## More Information

Related issues: #2102 (this ADR, circulation blocker), #2078 (draft spec PR).
Follow-on implementation task: remove `CVDRole.FINDER` from the enum and retire
`FinderParticipant` / `FinderReporterParticipant`; update all spec entries and
code that reference `CVDRole.FINDER`.
