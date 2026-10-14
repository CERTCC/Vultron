---
source: NOTES-participant-case-replica--testing-patterns
timestamp: '2026-10-12T19:35:06.232702+00:00'
title: Testing Patterns
type: note
---

**Archived:** 2026-10-12
**Reason:** illustrative test snippets that copy no live test; the real tests are the reference
**Superseded by:** test/core/use_cases/received/actor/test_announce.py; specs/participant-case-replica.yaml PCR-07

---

## Testing Patterns

```python
# PCR-07-001: Announce from the CASE_MANAGER creates local replica
def test_announce_creates_replica(dl, case_actor, new_case):
    activity = AnnounceVulnerabilityCaseActivity(
        actor=case_actor.id_,
        object_=new_case,
        to=["https://example.org/reporter"],
        context=new_case.id_,
    )
    event = build_event(activity, actor_id="https://example.org/reporter")
    AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()
    assert dl.read(new_case.id_) is not None


# PCR-07-003: Announce from non-CASE_MANAGER is rejected
def test_announce_from_non_case_actor_rejected(dl, imposter_actor, new_case,
                                               caplog):
    activity = AnnounceVulnerabilityCaseActivity(
        actor=imposter_actor.id_,
        object_=new_case,
        to=["https://example.org/reporter"],
        context=new_case.id_,
    )
    event = build_event(activity, actor_id="https://example.org/reporter")
    with caplog.at_level(logging.WARNING):
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()
    assert dl.read(new_case.id_) is None
    assert "not the CASE_MANAGER" in caplog.text


# PCR-07-005: Activity with unknown context is queued, not applied
def test_unknown_context_queued(dl, case_scoped_note_activity):
    # case does not exist in dl yet
    dispatch_case_scoped_activity(case_scoped_note_activity, dl)
    assert dl.read(case_scoped_note_activity.context) is None
    assert _is_enqueued(case_scoped_note_activity.id_)
```
