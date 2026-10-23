---
source: STATUS-SCHEMA-931
timestamp: '2026-06-15T20:16:53.888074+00:00'
title: Preserve accepted-status consent snapshots on retries
type: learning
---

When reusing an existing report-phase `ParticipantStatus` at `RM.ACCEPTED`, do not overwrite a non-null `em_consent_state` with default `NO_EMBARGO`. Update `cvd_role` as needed, but only backfill consent when it is missing. This keeps retries/idempotent paths from silently downgrading consent snapshots.

**Promoted**: 2026-06-15 — captured in `specs/case-management.yaml` (CM-13-008) and `AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/978>.
