---
source: ISSUE-1201
timestamp: '2026-07-08T13:39:12.386617+00:00'
title: Add CVE_NUMBERING_AUTHORITY to CVDRole enum
type: implementation
---

## Issue #1201 — Add CVE_NUMBERING_AUTHORITY to CVDRole enum

Added CVDRole.CVE_NUMBERING_AUTHORITY as the 9th atomic CVD role, representing a participant that holds CVE Numbering Authority (CNA) status. The role is orthogonal to all existing roles.

Key changes: roles.py (new enum member + docstring), BTND-05-004 spec (MUST requirement), catalog note updates for IsIDAssignmentAuthority and IdAssignable, 13 new tests (6 in test_cvd_roles.py, 7 in TestCNARoleOnParticipant), pythonpath=["."] pytest fix for devcontainer path shadowing.

PR: <https://github.com/CERTCC/Vultron/pull/1244>
