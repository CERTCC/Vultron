#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""
Unit tests for vultron.wire.as2.factories.case.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-01-003: Explicit, domain-typed parameters for protocol-significant fields.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions re-exported from factories/__init__.py.
"""

import pytest

from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    accept_case_ownership_transfer_activity,
    add_note_to_case_activity,
    add_report_to_case_activity,
    add_status_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    create_case_status_activity,
    offer_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    rm_accept_invite_to_case_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
    update_case_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_status import CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"


@pytest.fixture
def sample_case() -> VulnerabilityCase:
    return VulnerabilityCase(name="Test Case")


@pytest.fixture
def sample_report() -> VulnerabilityReport:
    return VulnerabilityReport(name="Test Report")


@pytest.fixture
def sample_status() -> CaseStatus:
    return CaseStatus()


@pytest.fixture
def sample_note() -> as_Note:
    return as_Note(content="Test note content")


@pytest.fixture
def sample_actor() -> as_Person:
    return as_Person(name="Alice", id_=_ACTOR_URI)


@pytest.fixture
def sample_offer(sample_case) -> as_Offer:
    """OfferCaseOwnershipTransferActivity — used for Accept/Reject tests."""
    return offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI
    )


@pytest.fixture
def sample_invite(sample_actor) -> as_Invite:
    """RmInviteToCaseActivity — used for Accept/Reject invite tests."""
    return rm_invite_to_case_activity(
        invitee=sample_actor, target=_CASE_URI, actor=_ACTOR_URI
    )


# ---------------------------------------------------------------------------
# add_report_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_report_to_case_returns_add(sample_report):
    result = add_report_to_case_activity(
        report=sample_report, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_add_report_to_case_object_is_report(sample_report):
    result = add_report_to_case_activity(
        report=sample_report, actor=_ACTOR_URI
    )
    assert result.object_ == sample_report


def test_add_report_to_case_target_is_set(sample_report):
    result = add_report_to_case_activity(
        report=sample_report, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_report_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_report_to_case_activity(
            report="not-a-report"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_status_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_status_to_case_returns_add(sample_status):
    result = add_status_to_case_activity(
        status=sample_status, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Add)


def test_add_status_to_case_object_is_status(sample_status):
    result = add_status_to_case_activity(
        status=sample_status, actor=_ACTOR_URI
    )
    assert result.object_ == sample_status


def test_add_status_to_case_target_is_set(sample_status):
    result = add_status_to_case_activity(
        status=sample_status, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_status_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_status_to_case_activity(
            status="not-a-status"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# create_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_create_case_returns_create(sample_case):
    result = create_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert isinstance(result, as_Create)


def test_create_case_object_is_case(sample_case):
    result = create_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.object_ == sample_case


def test_create_case_kwargs_forwarded(sample_case):
    result = create_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.actor == _ACTOR_URI


@pytest.mark.spec("AF-04-001")
def test_create_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        create_case_activity(case="not-a-case")  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# create_case_status_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_create_case_status_returns_create(sample_status):
    result = create_case_status_activity(
        status=sample_status, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Create)


def test_create_case_status_object_is_status(sample_status):
    result = create_case_status_activity(
        status=sample_status, actor=_ACTOR_URI
    )
    assert result.object_ == sample_status


@pytest.mark.spec("AF-04-001")
def test_create_case_status_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        create_case_status_activity(
            status="not-a-status"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_note_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_note_to_case_returns_add(sample_note):
    result = add_note_to_case_activity(note=sample_note, actor=_ACTOR_URI)
    assert isinstance(result, as_Add)


def test_add_note_to_case_object_is_note(sample_note):
    result = add_note_to_case_activity(note=sample_note, actor=_ACTOR_URI)
    assert result.object_ == sample_note


def test_add_note_to_case_target_is_set(sample_note):
    result = add_note_to_case_activity(
        note=sample_note, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_note_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_note_to_case_activity(note=42)  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# update_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_update_case_returns_update(sample_case):
    result = update_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert isinstance(result, as_Update)


def test_update_case_object_is_case(sample_case):
    result = update_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_update_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        update_case_activity(case="not-a-case")  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_engage_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_engage_case_returns_join(sample_case):
    result = rm_engage_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert isinstance(result, as_Join)


def test_rm_engage_case_object_is_case(sample_case):
    result = rm_engage_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_rm_engage_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_engage_case_activity(case="not-a-case")  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_defer_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_defer_case_returns_ignore(sample_case):
    result = rm_defer_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert isinstance(result, as_Ignore)


def test_rm_defer_case_object_is_case(sample_case):
    result = rm_defer_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_rm_defer_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_defer_case_activity(case="not-a-case")  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_close_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_close_case_returns_leave(sample_case):
    result = rm_close_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert isinstance(result, as_Leave)


def test_rm_close_case_object_is_case(sample_case):
    result = rm_close_case_activity(case=sample_case, actor=_ACTOR_URI)
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_rm_close_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_close_case_activity(case="not-a-case")  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# offer_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_offer_ownership_transfer_returns_offer(sample_case):
    result = offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Offer)


def test_offer_ownership_transfer_object_is_case(sample_case):
    result = offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI
    )
    assert result.object_ == sample_case


def test_offer_ownership_transfer_target_is_set(sample_case, sample_actor):
    result = offer_case_ownership_transfer_activity(
        case=sample_case, target=sample_actor, actor=_ACTOR_URI
    )
    assert result.target == sample_actor


@pytest.mark.spec("AF-04-001")
def test_offer_ownership_transfer_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        offer_case_ownership_transfer_activity(
            case="not-a-case"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# accept_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_accept_ownership_transfer_returns_accept(sample_offer):
    result = accept_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Accept)


def test_accept_ownership_transfer_object_is_offer(sample_offer):
    result = accept_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI
    )
    assert result.object_ == sample_offer


@pytest.mark.spec("AF-04-001")
def test_accept_ownership_transfer_plain_offer_raises(sample_report):
    """A plain as_Offer (not from offer_case_ownership_transfer_activity) must fail."""
    plain_offer = as_Offer(actor=_ACTOR_URI, object_=sample_report)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        accept_case_ownership_transfer_activity(offer=plain_offer)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# reject_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_reject_ownership_transfer_returns_reject(sample_offer):
    result = reject_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Reject)


def test_reject_ownership_transfer_object_is_offer(sample_offer):
    result = reject_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI
    )
    assert result.object_ == sample_offer


@pytest.mark.spec("AF-04-001")
def test_reject_ownership_transfer_plain_offer_raises(sample_report):
    plain_offer = as_Offer(actor=_ACTOR_URI, object_=sample_report)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        reject_case_ownership_transfer_activity(offer=plain_offer)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_invite_to_case_returns_invite(sample_actor):
    result = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    assert isinstance(result, as_Invite)


def test_rm_invite_to_case_object_is_actor(sample_actor):
    result = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    assert result.object_ == sample_actor


def test_rm_invite_to_case_target_is_set(sample_actor):
    result = rm_invite_to_case_activity(
        invitee=sample_actor, target=_CASE_URI, actor=_ACTOR_URI
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_rm_invite_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_invite_to_case_activity(
            invitee="not-an-actor"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_accept_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_accept_invite_to_case_returns_accept(sample_actor):
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_accept_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert isinstance(result, as_Accept)


def test_rm_accept_invite_to_case_object_is_invite(sample_actor):
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_accept_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert result.object_ == invite


def test_rm_accept_invite_to_case_in_reply_to_auto_set(sample_actor):
    """Model validator auto-populates in_reply_to from invite.id_."""
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_accept_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert result.in_reply_to == invite.id_


def test_rm_accept_invite_to_case_explicit_in_reply_to_preserved(sample_actor):
    """Explicitly provided in_reply_to is not overwritten."""
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    explicit_id = "https://example.org/activities/explicit-invite-id"
    result = rm_accept_invite_to_case_activity(
        invite=invite, in_reply_to=explicit_id, actor=_ACTOR_URI
    )
    assert result.in_reply_to == explicit_id


@pytest.mark.spec("AF-04-001")
def test_rm_accept_invite_to_case_plain_invite_raises(sample_actor):
    """A plain as_Invite (not from rm_invite_to_case_activity) must fail."""
    plain_invite = as_Invite(actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_accept_invite_to_case_activity(invite=plain_invite)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_reject_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_reject_invite_to_case_returns_reject(sample_actor):
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_reject_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert isinstance(result, as_Reject)


def test_rm_reject_invite_to_case_object_is_invite(sample_actor):
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_reject_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert result.object_ == invite


def test_rm_reject_invite_to_case_in_reply_to_auto_set(sample_actor):
    """Model validator auto-populates in_reply_to from invite.id_."""
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    result = rm_reject_invite_to_case_activity(invite=invite, actor=_ACTOR_URI)
    assert result.in_reply_to == invite.id_


def test_rm_reject_invite_to_case_explicit_in_reply_to_preserved(sample_actor):
    """Explicitly provided in_reply_to is not overwritten."""
    invite = rm_invite_to_case_activity(invitee=sample_actor, actor=_ACTOR_URI)
    explicit_id = "https://example.org/activities/explicit-invite-id"
    result = rm_reject_invite_to_case_activity(
        invite=invite, in_reply_to=explicit_id, actor=_ACTOR_URI
    )
    assert result.in_reply_to == explicit_id


@pytest.mark.spec("AF-04-001")
def test_rm_reject_invite_to_case_plain_invite_raises(sample_actor):
    plain_invite = as_Invite(actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_reject_invite_to_case_activity(invite=plain_invite)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# announce_vulnerability_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_announce_vulnerability_case_returns_announce(sample_case):
    result = announce_vulnerability_case_activity(
        case=sample_case, actor=_ACTOR_URI
    )
    assert isinstance(result, as_Announce)


def test_announce_vulnerability_case_object_is_case(sample_case):
    result = announce_vulnerability_case_activity(
        case=sample_case, actor=_ACTOR_URI
    )
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_announce_vulnerability_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        announce_vulnerability_case_activity(
            case="not-a-case"  # type: ignore[arg-type]
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_case_factories_importable_from_package():
    """All case factory functions must be importable from the factories package."""
    from vultron.wire.as2.factories import (  # noqa: F401
        accept_case_ownership_transfer_activity,
        add_note_to_case_activity,
        add_report_to_case_activity,
        add_status_to_case_activity,
        announce_vulnerability_case_activity,
        create_case_activity,
        create_case_status_activity,
        offer_case_ownership_transfer_activity,
        reject_case_ownership_transfer_activity,
        rm_accept_invite_to_case_activity,
        rm_close_case_activity,
        rm_defer_case_activity,
        rm_engage_case_activity,
        rm_invite_to_case_activity,
        rm_reject_invite_to_case_activity,
        update_case_activity,
    )
