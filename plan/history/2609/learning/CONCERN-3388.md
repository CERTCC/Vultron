---
source: CONCERN-3388
timestamp: '2026-09-18T16:11:47.690047+00:00'
title: Rename capability sets to Case Observer/Decision/Hosting; register vocabulary
type: learning
---

The docs "capability sets" model named the CASE_OWNER governance set "Authority"
while ADR-0088 makes "authority" the defining property of the CASE_MANAGER role
(single-writer control of the canonical ledger). Same word, two role-holders. The
"Hosting" set also filed the CASE_MANAGER's single-writer control under
infrastructure — the exact "authority-is-a-hosting-thing" framing ADR-0088 rejects.
The capability-set vocabulary (Observer/Authority/Hosting) was load-bearing across
~9 pages yet absent from the glossary.

**Decision (via grill-me).** Prefix all three named capability sets with "Case" —
**Case Observer / Case Decision / Case Hosting** — so the vocabulary reads
unambiguously as capability sets (properties of *software*) distinct from the
similarly-named roles (positions in a case) they serve. This is the generalized
form of the ADR-0088 authority-vs-hosting split and of the #3342 learning
(hosting/running-a-ledger is genuine infrastructure and keeps an infrastructure
name; only the single-writer *authority* is the role). "Authority" set → "Case
Decision" (fits the project's decision-framework framing; frees "authority" for the
CASE_MANAGER everywhere). "Hosting" kept (narrowed to "Case Hosting") rather than
renamed to a role name, because a capability set is software and a role is a
position — renaming Hosting to a role name would commit the category error the
glossary warns against.

**Resolved**: 2026-09-18 — fix landed directly in PR #3394 (docs-only; no separate
implementation issue). Renamed across the canonical `_capability-sets.md`,
`vultron-taxonomy.md`, `_role-taxonomy.md`, `_conformance-testing.md`, `_intro.md`,
`_terminology.md`, `_capability-shapes.md`, `draft-vultron-replication-spec.md`, and
the ADR-0077 cross-ref; repaired prose that attributed single-writer authority to a
capability set rather than the CASE_MANAGER role (sharpest at `_role-taxonomy.md`);
registered the capability-set vocabulary in `docs/reference/glossary.md`. `spec-dump`
confirmed zero spec entries use these terms.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3394>.
