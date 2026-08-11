---
status: accepted
date: 2026-08-11
deciders: Allen D. Householder
consulted: CERTCC/Vultron contributors
informed: Vultron protocol working group
---

# Rename `CVDRole.OTHER` to `CVDRole.OBSERVER` and Define Observer Participant Semantics

## Context and Problem Statement

`CVDRole.OTHER` was introduced as a catch-all placeholder for case participants
that do not fit any of the standard CVD roles (FINDER, REPORTER, VENDOR, DEPLOYER,
COORDINATOR). The draft Vultron Protocol spec (PR #2078, §7.3.3) proposed
renaming this role to "Observer" to give it a meaningful semantic identity, but
the rename was marked provisional because the protocol had not yet defined what
an Observer *is*:

- What `case_roles` value does the `Invite` carry for an Observer?
  (Empty list `[]` was indistinguishable from the `caseRoles=[]` admission
  defect documented in issue #1288.)
- Does an Observer receive full case content, or a reduced/redacted view?
- What does the RM triage cycle mean for a participant with no remediation
  obligations?
- When a participant holds OBSERVER alongside another role (e.g., DEPLOYER),
  which obligations apply?

This ADR resolves all four questions and formally renames the role.

## Decision Drivers

- The rename cannot land in the spec without a definition: renaming an ambiguity
  is just relabelling it.
- CM-17-003 requires the `Invite` to carry a non-empty `case_roles` list; the
  admission path for an Observer must produce a valid, non-empty value.
- The sentinel design (issue #2092) depends on knowing whether a sentinel, when
  admitted as a case participant, holds a defined role.
- The `coerce_cvd_roles` fallback in `participant_status.py` treats `None` and
  `[]` as `[CVDRole.OTHER]`; once renamed, the fallback must use the new value.

## Considered Options

1. **Rename CVDRole.OTHER → CVDRole.OBSERVER** — give the role a meaningful name
   and define its semantics explicitly (admission, content, RM, VFD).
2. **Keep CVDRole.OTHER; add CVDRole.OBSERVER as a separate new value** — retain
   OTHER as a generic fallback for truly unclassified actors and add OBSERVER as
   a distinct named role for monitoring participants.
3. **Keep CVDRole.OTHER unchanged; define Observer in spec docs only** — no code
   change; Observer is just a name for `case_roles=[CVDRole.OTHER]`.

## Decision Outcome

Chosen option: **Rename CVDRole.OTHER → CVDRole.OBSERVER**, because:

- The role's defining characteristic (monitoring / observing without remediation
  obligations) is what `OTHER` was always intended to capture for the monitoring
  use case. Renaming makes the intent explicit.
- Option 2 (keep OTHER, add OBSERVER) creates two roles whose distinction is
  unclear at admission time; agents and implementers would need to decide which
  to use, recreating the ambiguity.
- Option 3 (docs-only) leaves the enum name misleading for all future
  implementers.

**Observer semantics (normative requirements in CM-25):**

- An Observer is a full Tier-1 case participant: it holds a `CaseParticipant`
  record, runs the RM lifecycle, and must satisfy the same embargo-consent gate
  as any other participant.
- Observer is the **base role** — the lowest non-null privilege set in the
  protocol. All other CVD roles are additive to it.
- An Observer MUST NOT emit VFD state-transition messages (CV, CF, CD) *when
  OBSERVER is its only role*. The RM cycle applies with "engagement not
  remediation" semantics: `RM.ACCEPTED` means the Observer is actively engaged
  with the case, not that it has committed to developing or deploying a fix.
- Full case content is delivered via the existing MV-10-005 gate (admitted +
  embargo-signatory). No new delivery tier is needed.
- Admission is the standard Invite/Accept flow; the `Invite` carries
  `case_roles=[CVDRole.OBSERVER]`, satisfying CM-17-003 and the CM-16-003
  non-empty invariant.

**Role stacking (normative requirements in CM-26):**

- When a participant holds multiple roles, their permitted actions are the
  **union** of what each role permits. A MUST NOT restriction attached to one
  role is superseded when any other role in the list carries MAY, SHOULD, or
  MUST for the same action class.
- Example: OBSERVER + DEPLOYER can and should emit VFD/D transitions because
  DEPLOYER carries that obligation.

### Consequences

- Good, because the `Invite` wire format gains a clear, non-empty `case_roles`
  value for monitoring participants, closing the issue #1288 hole.
- Good, because the sentinel question (issue #2092) is unblocked: a sentinel
  admitted as a case participant holds CVDRole.OBSERVER.
- Good, because `coerce_cvd_roles` fallback and field defaults remain correct
  (they just reference the renamed value).
- Neutral, because the rename is a mechanical refactor across ~10 Python files
  and tests; no behavioral change.
- Watch out: when checking whether the VFD exclusion applies, code MUST test
  whether OBSERVER is the participant's **only** role, not merely whether they
  hold OBSERVER. A participant with OBSERVER + VENDOR must not be blocked from
  emitting VFD transitions.

## Validation

- `test/core/models/test_case_participant.py` updated to use
  `ObserverParticipant` and `CVDRole.OBSERVER`.
- `test/core/behaviors/report/test_report_to_others_tree.py` updated accordingly.
- Spec-check CI (`uv run spec-dump` lint) passes with CM-25 and CM-26 entries.

## More Information

Generated spec requirements: `specs/case-management.yaml` CM-25-001 through
CM-25-005 (Observer semantics) and CM-26-001 (role-stacking union principle).

Related issues: CONCERN-2093 (this decision), CONCERN-2092 (sentinel — blocked
by this ADR), #1288 (empty `caseRoles` defect), #1752 (role-request mechanism).
