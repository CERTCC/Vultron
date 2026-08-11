#!/usr/bin/env python
"""Ratchet signal for ISSUE-2194: outbound Accept ``object_`` emitted as a bare
URN string instead of a fully-inline typed object.

Symptom (confirmed across fcv / fcvcv / fvv / fccv-extension / fvcv-extension
demo scenarios): a participant validates a report (the RM.RECEIVED -> VALID /
ACCEPTED transition). The participant builds the validate-report ``Accept(Offer)``
exactly as the production ``TriggerActivityAdapter.validate_report()`` does — via
:func:`rm_validate_report_activity`, whose ``object_`` is a *fully inline* typed
``_RmSubmitReportActivity`` (the Offer). The adapter then persists the activity
(``self._dl.create(activity)``).

The DataLayer dehydrates ``as_ObjectRef``-typed fields (``object_``) to a bare ID
string on store (``vultron/adapters/driven/db_record.py::_dehydrate_data``). When
the outbox reads the activity back for delivery
(``vultron/adapters/driving/fastapi/outbox_delivery.py::_load_outbound_activity``),
``_rehydrate_fields`` tries to resolve that ID via ``dl.read(offer_id)``. In the
invite / reconstitution path the submit-report Offer activity was never persisted
as a standalone record under ``offer_id`` (it is reconstituted on demand from a
``VultronOfferRecord``), so rehydration finds nothing, logs "Could not rehydrate
field 'object_' ... keeping string reference", and leaves ``object_`` a bare
string. The outbox gate ``_validate_inline_object`` then rejects it:
"Outbound initiating activities must carry fully inline typed objects
(MV-09-001)". The Accept is never delivered, the participant stays at
RM.RECEIVED, and ``engage-case`` later returns 422
``TransitionParticipantRMtoAccepted``.

Location rationale: the true emission site is the driven adapter layer — the
validate-report factory (``vultron/wire/as2/factories/report.py``) plus the
dehydrate-on-store / rehydrate-on-read cycle in
``vultron/adapters/driven/``. This test reproduces the gap at that layer with a
real :class:`SqliteDataLayer` and no Docker: it builds the Accept exactly as the
adapter does, persists it with ``dl.create``, reads it back the way the outbox
does, and asserts the outbound ``object_`` is a fully-inline typed object.
"""

import uuid

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.outbox_delivery import (
    _validate_inline_object,
)
from vultron.errors import VultronOutboxObjectIntegrityError
from vultron.wire.as2.factories import (
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

REPORTER_ID = "https://example.org/actors/reporter"
RECEIVER_ID = "https://example.org/actors/receiver"


@pytest.fixture
def dl():
    layer = SqliteDataLayer("sqlite:///:memory:")
    yield layer
    layer.close()


def _build_validate_report_accept():
    """Build the validate-report ``Accept(Offer)`` exactly as production does.

    Mirrors ``TriggerActivityAdapter.validate_report()``:
    ``rm_validate_report_activity(offer=<fully typed Offer>, actor=..., to=...)``.
    """
    report_id = f"urn:uuid:{uuid.uuid4()}"
    offer_id = f"urn:uuid:{uuid.uuid4()}"
    report = as_VulnerabilityReport(
        id_=report_id, attributed_to=REPORTER_ID, content="test report"
    )
    # The offer the participant is accepting (received / reconstituted, fully
    # typed and inline — never persisted as a standalone record under offer_id
    # in the invite / reconstitution path).
    offer = rm_submit_report_activity(
        report=report, to=RECEIVER_ID, actor=REPORTER_ID, id_=offer_id
    )
    accept = rm_validate_report_activity(
        offer=offer, actor=RECEIVER_ID, to=[REPORTER_ID]
    )
    return accept, offer_id


def test_validate_report_accept_is_inline_before_store(dl):
    """Sanity control: the factory output IS a fully-inline typed object.

    Confirms the bug is introduced by the store/read cycle, not by the
    construction path — so the xfail below is genuinely about emission.
    """
    accept, _offer_id = _build_validate_report_accept()
    assert not isinstance(accept.object_, (str, as_Link))
    # object_ is the fully typed Offer activity carrying the report inline.
    assert getattr(accept.object_, "id_", None) is not None


def test_outbox_gate_rejects_bare_string_object():
    """Control: a bare-string ``object_`` trips the MV-09-001 outbox gate.

    Documents the downstream cause of the 422 TransitionParticipantRMtoAccepted
    (the Accept is rejected and never delivered).
    """
    with pytest.raises(VultronOutboxObjectIntegrityError):
        _validate_inline_object(
            "urn:uuid:some-accept", "Accept", "urn:uuid:bare-offer-ref"
        )


def test_stored_validate_report_accept_carries_inline_typed_object(dl):
    """Outbound validate-report ``Accept.object_`` must be a fully-inline typed
    object (not a bare ``str`` / ``as_Link``) so it passes the MV-09-001 outbox
    gate without a DataLayer expansion round-trip.

    Production adapter persists the Accept with ``dl.create(activity)`` and does
    NOT separately persist the Offer under ``offer_id`` on the reconstitution
    path. Reading the activity back (as ``_load_outbound_activity`` does) yields
    ``object_`` as a bare string today -> MV-09-001 rejection.
    """
    accept, _offer_id = _build_validate_report_accept()

    # Production path: TriggerActivityAdapter.validate_report() -> dl.create.
    # The submit-report Offer is intentionally NOT stored under offer_id
    # (reconstitution path), matching the failing invite-path scenarios.
    dl.create(accept)

    # Outbox delivery reads the queued activity back before the MV-09-001 gate.
    stored = dl.read(accept.id_)
    outbound_object = getattr(stored, "object_", None)

    assert not isinstance(outbound_object, (str, as_Link)), (
        "Outbound validate-report Accept.object_ is a bare"
        f" {type(outbound_object).__name__} ({outbound_object!r}); it must be a"
        " fully-inline typed object to satisfy MV-09-001 (#2194)."
    )
