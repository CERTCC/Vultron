---
source: NOTES-embargo-default-semantics--cross-references
timestamp: '2026-10-12T19:34:18.145150+00:00'
title: Cross-references
type: note
---

**Archived:** 2026-10-12
**Reason:** citation list; each rule now carries its own citation inline (NF-08-004)
**Superseded by:** specs/embargo-policy.yaml EP-04, EP-07

---

## Cross-references

- `specs/embargo-policy.yaml` EP-04-001 through EP-04-010, EP-07-002/003/005/006
- `specs/case-management.yaml` CM-12-004 and CM-14-010 (default embargo at case
  creation, no longer conditional on a configured policy), CM-14-006 (reporter
  proposal reconciliation, now reachable), CM-18-002 (pocket-veto policy window),
  CM-28-002 (explicit `Invite.end_time` precedence, bounded by EP-07-006),
  CM-28-011 (window bounded by the embargo)
- `specs/vultron-protocol-spec.yaml` VP-07-001 (the "no embargo SHALL exist" rule
  the protocol default replaces), VP-06-001 (propose/accept forbidden once P/X/A is set)
- `specs/vultron-as2-mapping.yaml` VAM-05-001 (`Create(Event)` context may be a report)
- `specs/duration.yaml` DUR-07-003 (default embargo logging)
- `docs/topics/process_models/em/defaults.md` (authoritative protocol source)
- `docs/topics/process_models/model_interactions/rm_em.md` (pre-case guidance, corrected)
- ADR-0096 (protocol default embargo; no pre-case phase), ADR-0065 (RSVP deadline
  and pocket veto as one mechanism), ADR-0041 / ADR-0089 (why not a proto-case)
