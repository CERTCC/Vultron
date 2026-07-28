---
source: ISSUE-1729
timestamp: '2026-07-28T14:49:15.281984+00:00'
title: Add mandatory phrase field to SemanticEntry and migrate demo report tool
type: implementation
---

## Issue #1729 — Add mandatory phrase field to SemanticEntry and migrate demo report tool

Added mandatory `phrase: str` field (no default) to `SemanticEntry` frozen dataclass. All 50 registry entries across 9 sub-modules populated with active-voice format-string templates. New `vultron/core/display.py` with `friendly_name()`. Migrated `vultron/demo/report.py` to delete `_EVENT_PHRASES` and use registry-driven phrase lookup in `event_phrase()` and `CaseTimelineEvent.summary`. Fixed 4 pre-PR FAIL findings: capitalisation logic when actor_uri=None, grammar fix in status.py phrase, strengthened test assertion, added missing no-actor-uri test.

PR: <https://github.com/CERTCC/Vultron/pull/1751>
