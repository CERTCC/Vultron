---
title: "P347-PUPPETEER \u2014 Demo Trigger-Based Puppeteering"
type: implementation
timestamp: '2026-04-20T00:00:00+00:00'
source: P347-PUPPETEER
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 6982
legacy_heading: "P347-PUPPETEER \u2014 Demo Trigger-Based Puppeteering (COMPLETE\
  \ 2026-07-21)"
date_source: git-blame
legacy_heading_dates:
- '2026-07-21'
---

## P347-PUPPETEER — Demo Trigger-Based Puppeteering

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:6982`
**Canonical date**: 2026-04-20 (git blame)
**Legacy heading**

```text
P347-PUPPETEER — Demo Trigger-Based Puppeteering (COMPLETE 2026-07-21)
```

**Legacy heading dates**: 2026-07-21

**Task:** Convert all spoofing functions in `three_actor_demo.py` and
`multi_vendor_demo.py` from direct inbox injection to trigger-based
puppeteering. Added inline prerequisite: `invite-actor-to-case` trigger.

**New trigger added (inline prerequisite):**

- `InviteActorToCaseTriggerRequest` in `requests.py`
- `SvcInviteActorToCaseUseCase` in `triggers/actor.py`
- `InviteActorToCaseRequest` HTTP model in `trigger_models.py`
- `invite_actor_to_case_trigger` adapter in `_trigger_adapter.py`
- `POST /{actor_id}/trigger/invite-actor-to-case` endpoint in `trigger_actor.py`

**Spoofing functions converted (5 in three_actor_demo.py):**

- `coordinator_creates_case_on_case_actor` — now calls `create-case` trigger,
  adds `coordinator_client` param
- `coordinator_adds_report_to_case` — now calls `add-report-to-case` trigger,
  adds `coordinator_client` param
- `coordinator_invites_actor` — fully redesigned: new signature
  `(actor_client, recipient_client, actor, recipient, case, case_actor_client=None,
  case_actor=None)`, calls `invite-actor-to-case` trigger
- `actor_accepts_case_invite` — now calls `accept-case-invite` trigger, adds
  `actor_client` param, delivers accept to case_actor
- `actor_accepts_embargo` — now calls `accept-embargo` trigger on
  `case_actor_client`, removes `case_actor` param and `EmAcceptEmbargoActivity`
  return type

**Spoofing functions converted (2 in multi_vendor_demo.py):**

- `vendor_creates_case_on_case_actor` — now calls `create-case` trigger,
  adds `vendor_client` param
- `vendor_adds_report_to_case` — now calls `add-report-to-case` trigger,
  adds `vendor_client` param

**Test updates:**

- `test/demo/test_three_actor_demo.py` — updated call site for
  `coordinator_creates_case_on_case_actor`; removed stale assertion that case
  was NOT in coordinator's DL (now it IS, by design)
- `test/demo/test_multi_vendor_demo.py` — updated both call sites for
  `vendor_creates_case_on_case_actor`; attribution now checked against
  `vendor_in_vendor.id_`
- `test/core/use_cases/triggers/test_actor_triggers.py` — new: 4 unit tests
  for `SvcInviteActorToCaseUseCase`

**Test Result:**

1673 passed, 12 skipped, 182 deselected, 5581 subtests passed
