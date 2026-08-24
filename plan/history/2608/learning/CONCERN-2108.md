---
source: CONCERN-2108
timestamp: '2026-08-24T17:20:43.005624+00:00'
title: 'CNA eligibility: reference baseline over normative citation or implementation-defined'
type: learning
---

## Outcome

CONCERN-2108 asked whether the RFC should normatively cite CNA Operational
Rules v4.1.0 eligibility criteria, or treat CVE assignment eligibility as
fully implementation-defined. Resolved via ADR-0070: the RFC endorses
v4.1.0 as the **reference conformance baseline** — neither a normative
external citation nor a blank implementation-defined slate.

## Key Decisions

- **Reference baseline posture**: the spec endorses the code's v4.1.0 pin as
  the reference; adopting a newer edition requires updating both the spec and
  the implementing call-out factory.
- **Architectural refactoring direction**: CVE eligibility is one logical
  capability (a 9-pin connector). The current 9-child `IdAssignable` structure
  misrepresents the substitution unit. Correct design is one
  `EvaluateCveEligibility` Evaluator call-out (BTND-05-007).
- **Implementation deferred**: refactoring tracked separately as #2518,
  blocked by this Concern.

## Artifacts

- ADR-0070: `docs/adr/0070-cna-eligibility-reference-baseline.md`
- Spec entries: BTND-05-007, BTND-05-008 in `specs/behavior-tree-node-design.yaml`
- Spec update: `docs/reference/draft-vultron-spec.md` §7.4.3 (Open Question 9 resolved)
- AGENTS.md pitfall: external-versioned-standard capabilities should be one call-out unit
- Docs PR: <https://github.com/CERTCC/Vultron/pull/2517>
- Impl issue: #2518 (Schedule=Now, parent epic=#2100)

## Learning for Future Work

When a BT capability is grounded in an external, independently-versioned
specification, treat the full capability as a single Evaluator call-out point
— not one call-out per criterion. The substitution unit is the whole
capability. See BTND-05-007, ADR-0070, AGENTS.md pitfall added in this PR.
