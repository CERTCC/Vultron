---
source: ISSUE-1504
timestamp: '2026-07-20T14:27:38.892948+00:00'
title: 'Remove DataLayer duck-typing Protocols from core (issue #1504)'
type: implementation
---

## Issue #1504 — Remove DataLayer duck-typing Protocols from core

Removed CaseModel, ParticipantModel, ParticipantStatusModel, LogEntryModel Protocols
and is_case_model/is_participant_model/is_participant_status_model/is_log_entry_model
TypeGuard helpers from vultron/core/models/protocols.py. Replaced every call site (72
files) with direct isinstance() checks against concrete core domain classes.

The duck-typing workaround was made obsolete by ADR-0034/DL-05-003 (DataLayer read path
returns core objects). The architecture constraint (ARCH-01-001, no wire imports in core)
no longer requires structural typing — isinstance() against core types is clean.

Special receive-side boundary in announce.py uses dual check (isinstance OR type_==)
to accept both wire and core objects at the AS2 receive boundary per ADR-0032.

Tests using MagicMock now require spec=VulnerabilityCase to pass isinstance guards.

PR: <https://github.com/CERTCC/Vultron/pull/1529>
