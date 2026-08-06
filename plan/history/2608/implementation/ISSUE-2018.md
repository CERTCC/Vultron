---
source: ISSUE-2018
timestamp: '2026-08-06T19:10:46.517012+00:00'
title: Vendor2 RM triage cycle in FVCV-handoff demo
type: implementation
---

## Issue #2018 — Update FVCV-handoff demo: show Vendor2 RM triage cycle after joining

Added PROTOTYPE-only `seed-offer-record` endpoint so invited actors can run the standard RM triage cycle (RECEIVED → VALID → ACCEPTED) per CM-11-002. Extended `_phase_coordinator_invites_vendor2` with `validate-report` and `engage-case` calls for Vendor2, `demo_check` assertions for both RM states, a new `wait_for_participant_rm_state` polling helper, and updated CI invariants expecting `engage_case` ≥ 2 and `validate_report` ≥ 2.

PR: <https://github.com/CERTCC/Vultron/pull/2048>
