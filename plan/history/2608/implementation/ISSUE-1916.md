---
source: ISSUE-1916
timestamp: '2026-08-04T13:51:01.322183+00:00'
title: Remove AutoCloseSequence; complete CM-23-002 Leave closure
type: implementation
---

## Issue #1916 — Remove AutoCloseSequence from add_participant_status_tree and conform to CM-23 Leave-closure specs

Implemented per ADR-0050. Dead `AutoCloseSequence` subtree removed from `add_participant_status_tree`. Owner Leave receive path now completes CM-23-002: commits `case_fully_closed` CaseLedgerEntry and fans out to non-RM.CLOSED participants (CM-23-004). New `fanout.py` module provides `FanOutLogEntryExcludingClosedNode` and `CollectNonClosedLogEntryRecipientsNode`. 6 new tests. PR: <https://github.com/CERTCC/Vultron/pull/1966>
