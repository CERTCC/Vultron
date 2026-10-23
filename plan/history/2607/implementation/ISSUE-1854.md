---
source: ISSUE-1854
timestamp: '2026-07-31T16:25:28.850047+00:00'
title: wire PreCloseAction and rename close-case trigger path
type: implementation
---

## Issue #1854 — wire PreCloseAction and rename close-case trigger path

Implemented all 3 acceptance criteria:

1. **CheckCaseOwner guard** added as first node in `create_close_case_trigger_tree`; only CASE_OWNER may close
2. **PreCloseAction** Actuator call-out wired between CheckCaseOwner and CheckReportNotClosed; DETERMINISTIC default = AlwaysSucceed
3. **Rename**: `create_close_report_trigger_tree` → `create_close_case_trigger_tree`; `SvcCloseReportUseCase` → `SvcCloseCaseUseCase`; all callers updated (service.py, TriggerServicePort, FastAPI router, MCP adapter, 5 test files); backward-compat aliases kept

PR: <https://github.com/CERTCC/Vultron/pull/1869>
