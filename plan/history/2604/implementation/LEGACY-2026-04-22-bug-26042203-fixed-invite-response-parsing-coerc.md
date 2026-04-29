---
title: 'BUG-26042203 fixed: invite response parsing/coercion'
type: implementation
date: '2026-04-22'
source: LEGACY-2026-04-22-bug-26042203-fixed-invite-response-parsing-coerc
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 7756
legacy_heading: "2026-04-22 \u2014 BUG-26042203 fixed: invite response parsing/coercion"
date_source: git-blame
legacy_heading_dates:
- '2026-04-22'
---

## BUG-26042203 fixed: invite response parsing/coercion

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:7756`
**Canonical date**: 2026-04-22 (git blame)
**Legacy heading**

```text
2026-04-22 — BUG-26042203 fixed: invite response parsing/coercion
```

**Legacy heading dates**: 2026-04-22

- Issue: multi-party invite response flows could degrade inbound
  `Accept(Invite(...))` / `Reject(Invite(...))` activities into generic or
  unresolved shapes, which blocked semantic extraction and could lead to
  dead-letter handling downstream.
- Root cause: `parse_activity()` only pre-expanded the outer inline `object`
  dict, so nested actor and case-stub dicts inside invite response payloads
  were validated through generic base-field types and lost the subtype
  information required by invite-response patterns.
- Resolution: added recursive inline-model expansion in the AS2 parser with
  special handling for `VulnerabilityCase` stubs, defaulted invite
  accept/reject `inReplyTo` to the original invite ID, and added regression
  coverage for parser extraction, SQLite semantic coercion, and
  `accept-case-invite` trigger output.
