---
source: NOTES-activity-factories--migration-guide
timestamp: '2026-09-17T17:07:27.049669+00:00'
title: Migration Guide (activity factories)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) factory migration delivered and CI-enforced; call sites migrated.
**Superseded by:** test/architecture/test_activity_factory_imports.py; specs/activity-factories.yaml AF-01; vultron/wire/as2/factories/AGENTS.md.

---

## Migration Guide

### Call-site Pattern: Before and After

```python
# BEFORE (direct class instantiation — violates AF-01-001 after migration)
from vultron.wire.as2.vocab.activities.report import RmSubmitReportActivity

report_offer = RmSubmitReportActivity(
    object_=report,
    to=[alice_id],
)

# AFTER (factory function — correct)
from vultron.wire.as2.factories import rm_submit_report_activity

report_offer = rm_submit_report_activity(report=report, to=alice_id)
```

```python
# BEFORE
from vultron.wire.as2.vocab.activities.case import RmAcceptInviteToCaseActivity

accept = RmAcceptInviteToCaseActivity(actor=actor.id_, object_=invite)

# AFTER
from vultron.wire.as2.factories import rm_accept_invite_to_case_activity

accept = rm_accept_invite_to_case_activity(actor=actor.id_, invite=invite)
```

```python
# BEFORE (embargo proposal)
from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargoActivity

proposal = EmProposeEmbargoActivity(object_=embargo_event, context=case_ref)

# AFTER
from vultron.wire.as2.factories import em_propose_embargo_activity

proposal = em_propose_embargo_activity(embargo=embargo_event, context=case_ref)
```

### Accept/Reject with `model_validator` Logic

Classes like `RmAcceptInviteToCaseActivity` have a `model_validator`
that auto-sets `in_reply_to` from the invite's `id_`. The factory
function absorbs this:

```python
# factories/case.py
def rm_accept_invite_to_case_activity(
    invite: as_Invite,
    actor: str | None = None,
    **kwargs,
) -> as_Accept:
    """Build Accept(Invite) — the RV message when a case already exists."""
    try:
        return RmAcceptInviteToCaseActivity(
            actor=actor,
            object_=invite,
            **kwargs,
        )
    except ValidationError as exc:
        raise VultronActivityConstructionError(
            "rm_accept_invite_to_case_activity: invalid arguments"
        ) from exc
```

The `model_validator` on the internal class still fires — no need to
duplicate the logic in the factory.
