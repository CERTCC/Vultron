---
source: ISSUE-440
timestamp: '2026-05-06T18:39:36.147764+00:00'
title: Implement participant case replica safety
type: implementation
---

## Issue #440 — PCR: Implement participant case replica safety rules (PCR-03, PCR-05, PCR-06)

- enforced announce-case replica seeding so known CaseActors are authoritative while first-time seeding can still establish the initial local replica
- added persisted ReportCaseLink and PendingCaseInbox models so report submissions can later bind to received case replicas and unknown case-context inbox activities can be replayed safely
- updated inbox and trigger paths, expanded regression coverage, and opened PR #457: <https://github.com/CERTCC/Vultron/pull/457>
