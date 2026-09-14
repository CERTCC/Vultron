---
source: CONCERN-3005
timestamp: '2026-09-14T18:59:48.719034+00:00'
title: 'Fault reporting: correct taxonomy and remove phantom in_reply_to_ discriminator'
type: learning
---

## CONCERN-3005 — Fault reporting: should messages.md adopt the failure-mode partition?

The concern identified that the formal protocol (messages.md) partitions faults
by state machine (RE/EE/CE/GE) while the implementation partitions by failure
mode (not-understood/declined/needs-explanation), and asked whether messages.md
should be revised. Secondary findings: error.md depicted a phantom four-way wire
taxonomy that never existed; ActivityPattern.in_reply_to_ was declared but used
by zero registered patterns; VultronError name ambiguity.

**Resolved**: 2026-09-14 — implementation tracked in #3214.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3215>.
Spec: `specs/message-semantics-mapping.yaml` MSM-05-004 updated.
