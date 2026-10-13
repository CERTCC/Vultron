---
source: NOTES-case-bootstrap-trust--testing-patterns
timestamp: '2026-10-12T19:35:57.116692+00:00'
title: Testing Patterns
type: note
---

**Archived:** 2026-10-12
**Reason:** illustrative test snippets that copy no live test
**Superseded by:** specs/case-bootstrap-trust.yaml (verification fields); test/core/use_cases/received/

---

## Testing Patterns

```python
def test_bootstrap_create_records_case_manager(
    dl, report_submitter, report_receiver, submitted_report, bootstrap_activity
):
    event = build_event(bootstrap_activity, actor_id=report_submitter.id_)
    CreateVulnerabilityCaseReceivedUseCase(dl, event).execute()

    trust = dl.read(case_bootstrap_trust_id(submitted_report.id_))
    assert trust.case_creator_id == report_receiver.id_
    assert trust.case_manager_id is not None
```

```python
def test_pre_bootstrap_case_actor_announce_is_queued_not_applied(
    dl, queue_dl, case_actor_announce
):
    process_inbox_item(case_actor_announce, dl, queue_dl)

    assert local_case_not_updated(dl, case_actor_announce.context)
    assert queued_for_bootstrap(queue_dl, case_actor_announce.id_)
```

```python
def test_late_joiner_invite_establishes_case_actor_trust(
    dl, invite_activity, announce_activity
):
    InviteActorToCaseReceivedUseCase(dl, build_event(invite_activity)).execute()
    AnnounceVulnerabilityCaseReceivedUseCase(
        dl, build_event(announce_activity)
    ).execute()

    assert late_joiner_replica_created(dl, announce_activity.context)
```
