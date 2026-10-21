---
source: SPEC-RETIRE-RSH-05-008
timestamp: '2026-10-20T20:13:13.726595+00:00'
title: Retired requirement RSH-05-008
type: implementation
---

Retired RSH-05-008 from `specs/received-status-handling.yaml` (#3741).

Why: ADR-0107 detail 5: a received status is accepted whole or refused whole, so the ledger never records a status nobody sent (#4451 decision on #3741). The embedded EM is still not judged against the case; the rule moved into the acceptance rules.

Replacement: RSH-09-003

Final text: `plan/retired-specs/RSH-05-008.md`.
