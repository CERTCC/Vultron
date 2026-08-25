---
signal: design-question
source: decision-audit-20260803
timestamp: '2026-08-03T14:36:45.820910+00:00'
title: Decision audit 2026-08-03 — top-5 risk candidates resolved
type: learning
---

Ran decision-audit on MSM-02, MSM-03, ADR-0033, ADR-0015, CM-22.

MSM-02 (EE/EK) and MSM-03 (CE/CK): testable: false removed. Absence-from-registry
is testable; entries updated to expect tests asserting EE/EK/CE/CK are absent from
MessageSemantics and SEMANTICS_ACTIVITY_PATTERNS.

ADR-0033 (Lifecycle-Staged Domain Types): promoted status: proposed → accepted.
The ~70% confidence hedge referred to transition constructors as a future option, not
the main field-set-anchored decision. Opened Idea #1912 to preserve the transition-
constructor alternative before it could get lost.

ADR-0015 (Create VulnerabilityCase at Report Receipt): moved to docs/adr/archived/
so agents doing a docs/adr/ sweep no longer load the superseded decision.

CM-22-001: removed stale ADR-0015 adr: edge. The historical supersession prose mention
is retained with lint_suppress: [dangling_adr_ref].

Docs PR: <https://github.com/CERTCC/Vultron/pull/1913>.
