---
source: CONCERN-5867
timestamp: '2026-11-06T15:19:24.847195+00:00'
title: CBT-04-003 is priority MUST but its statement grants a MAY
type: learning
---

Theme: theme:requirements-traceability — CBT-04-003's priority and its statement say the same thing, so a reader knows whether the late-joiner Announce is required or permitted.

## Summary

CBT-04-003 (`specs/case-bootstrap-trust.yaml`) has `priority: MUST`, but its statement is a permission: "After the late joiner has accepted the stub Invite (`Accept(Invite(Actor)[target=VulnerabilityCaseStub])`), the CASE_MANAGER MAY send `Announce(VulnerabilityCase)` without a separate `Create(VulnerabilityCase)` bootstrap." A maintainer must decide which one is meant.

## Surface Symptom vs. Underlying Problem

- **Surface:** the priority field and the keyword in the statement disagree, so this looks like a typo.
- **Underlying:** the two readings oblige different things. As a MUST, the CASE_MANAGER is required to seed the late joiner with `Announce(VulnerabilityCase)` and is forbidden a separate `Create` bootstrap. As a MAY, the `Announce`-only path is one permitted option and a `Create` bootstrap stays allowed. The verification test (`test_the_stub_invite_is_the_late_joiners_trust_anchor` in `test/demo/test_pcr_late_joiner.py`) shows that the `Announce`-only path works. It does not show that this path is the only one.
- **Correct and worth keeping:** the rationale. The accepted stub Invite is already the joiner's Trust Anchor (CBT-04-001), so a further `Create` adds a trust step with nothing new to check.

## Category

Specification quality: priority and statement inconsistent (SR-10).

## Severity

Low. The implementation and demo already take the `Announce`-only path. The ambiguity matters to a conformance reader, or to an implementation that bootstraps a late joiner with `Create`.

## Evidence

- `specs/case-bootstrap-trust.yaml`, CBT-04-003: `priority: MUST`, statement "MAY send".
- `spec-lint` does not flag it.
- Found by the SR-13 link audit of the CLP, SYNC, RSH, PCR, CP, TRIG, CBT and SBT families (PR #5863, #5211). It is outside that audit's scope (links only), so the PR did not change it.

## Impact if Ignored

A conformance check built from `priority` would require behavior that the statement only permits. A reader cannot tell whether a `Create(VulnerabilityCase)` bootstrap for a late joiner conforms.

## Suggested Action

Ask the maintainer which one is meant. If it is a permission, change `priority` to `MAY`. If it is an obligation, reword the statement as "MUST send `Announce(VulnerabilityCase)` and MUST NOT send a separate `Create(VulnerabilityCase)`", and add a test that a `Create` bootstrap is not sent. Record the change in a `## Spec amended` block, because it changes what the requirement obliges.

**Resolved**: 2026-11-06 — resolved in the planning PR by spec edits; no implementation issue needed (code and tests already conform). CBT-04-003 is now MUST_NOT: the CASE_MANAGER sends a late joiner no Create(VulnerabilityCase) and seeds it with Announce(VulnerabilityCase) — a late joiner is told what the case is, not a witness to its initialization.

Docs PR: https://github.com/CERTCC/Vultron/pull/6027.
