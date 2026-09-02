---
source: CONCERN-3021
timestamp: '2026-09-02T17:57:40.383316+00:00'
title: PEC state machine has no wire message partition — transitions are EM side-effects
type: learning
---

## Concern

Issue #3021 identified that the 28-shorthand formal message set contains no PEC
partition, and that the MSM spec mapped EM shorthands to wire activities without
documenting how those same wire activities drive per-participant PEC state changes
as side-effects. Anyone implementing embargo-enforcement logic had no clear spec
to follow for PEC.

## Resolution

Documented PEC transitions as side-effects of EM wire activities — not as an
independent message partition — and clarified the CaseActor-sets vs. self-reported
distinction.

Key findings:

- PEC is a participant-specific state machine; the CaseActor (CM-28-003) sets it
  based on observed participant behavior, unlike RM (self-reported by participant)
  and VF/D (self-reported by vendor/deployer).
- EP drives the PEC INVITE trigger; EA has two-audience semantics (advances EM
  PROPOSED→ACTIVE for case owner AND applies PEC ACCEPT to accepting participants);
  ER similarly dual-purpose.
- EV cascades SIGNATORY→LAPSED for all SIGNATORY participants (no wire message).
- ET cascades *→NO_EMBARGO for all participants (no wire message).
- Timer-based pocket veto (INVITED/LAPSED→DECLINED) is enforced lazily by
  CaseActor; no wire message; CaseActor authors ledger entry (CM-28-005).

## Changes

- `specs/message-semantics-mapping.yaml`: bumped to v0.3.0; added MSM-07 group
  (7 normative entries) documenting the PEC/EM coupling.
- `notes/participant-embargo-consent.md`: expanded frontmatter cross-references,
  reformatted transition table with Trigger Source column (Wire/Cascade/Timer
  taxonomy), added new "PEC Is Set by the CaseActor, Not Self-Reported" section.

## Implementation Issues

- #3067: docs(topics): add EM/PEC interaction page to docs/topics/

## PR

<https://github.com/CERTCC/Vultron/pull/3064>
