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
"""Wire behaviour for joining a case (ADR-0114, ADR-0121).

Tests for the case-joining requirements: both case Invites name the case in
``object`` and the invitee in ``target`` (CM-11-013, ADR-0205), and the
full-case Invite and its replies being
distinguishable from the stub Invite and its replies (CM-11-011, VAM-04-011
through VAM-04-014).  See ``notes/case-joining.md``.
"""

import pytest

from test.support.objects import authored_at, make
from vultron.core.models._helpers import _as_id
from vultron.core.models.events import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.factories import (
    rm_invite_to_case_activity,
    rm_invite_to_full_case_activity,
)
from vultron.wire.as2.typed_reference import as_TypedReference
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
    as_TentativeReject,
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/joining-wire-1"
_MANAGER_ID = "https://example.org/actors/case-manager"
_INVITEE_ID = "https://example.org/actors/invitee"

_UNKNOWN = {
    MessageSemantics.UNKNOWN,
    MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
}


def _full_case() -> as_VulnerabilityCase:
    return make(
        as_VulnerabilityCase,
        id_=_CASE_ID,
        name="JOINING-WIRE",
        attributed_to=_MANAGER_ID,
        stub_summary="Security issue — details shared after acceptance",
    )


def _stub_invite() -> as_Invite:
    """The stub Invite exactly as the CASE_MANAGER's factory builds it."""
    return rm_invite_to_case_activity(
        make(as_Organization, id_=_INVITEE_ID),
        case=_full_case(),
        actor=_MANAGER_ID,
        id_=f"{_CASE_ID}/invitations/stub-1",
        at=authored_at(),
    )


def _full_case_invite() -> as_Invite:
    """``Invite(whole VulnerabilityCase)[target=Actor]`` — the full-case Invite."""
    return rm_invite_to_full_case_activity(
        make(as_Organization, id_=_INVITEE_ID),
        _full_case(),
        LedgerPosition(log_index=0, entry_hash="0" * 64),
        id_=f"{_CASE_ID}/invitations/full-1",
        actor=_MANAGER_ID,
        to=[_INVITEE_ID],
        at=authored_at(),
    )


_REPLY_CLASSES: dict[str, type[as_TransitiveActivity]] = {
    "accept": as_Accept,
    "tentative_reject": as_TentativeReject,
    "reject": as_Reject,
}


def _reply(kind: str, invite: as_Invite) -> as_TransitiveActivity:
    return make(_REPLY_CLASSES[kind], actor=_INVITEE_ID, object_=invite)


def _semantics_of(kind: str, invite: as_Invite) -> MessageSemantics:
    return find_matching_semantics(_reply(kind, invite))


@pytest.mark.spec("CM-11-013")
@pytest.mark.spec("VAM-04-004")
def test_stub_invite_names_the_case_in_object_and_the_invitee_in_target() -> (
    None
):
    """The stub Invite's object is the case's previewed reference.

    The ``object`` is a typed reference of type ``VulnerabilityCase`` whose
    ``id`` is the case's own, carrying the case stub as its ``preview``; the
    ``target`` is the invitee (ADR-0205).  The stub names no case of its
    own: no ``caseId`` and no ``/stub`` id.
    """
    dumped = _stub_invite().model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    reference = dumped["object"]
    assert reference["type"] == "VulnerabilityCase"
    assert reference["id"] == _CASE_ID
    preview = reference["preview"]
    assert preview["type"] == "CasePreview"
    assert "caseId" not in preview
    assert preview["id"] != f"{_CASE_ID}/stub"
    assert dumped["target"]["id"] == _INVITEE_ID


@pytest.mark.spec("VAM-04-011")
def test_full_case_invite_carries_the_whole_case() -> None:
    """The full-case Invite's object is the whole case, its target the
    invitee (ADR-0205)."""
    invite = _full_case_invite()
    assert isinstance(invite.object_, as_VulnerabilityCase)
    assert invite.object_.id_ == _CASE_ID
    dumped = invite.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert "preview" not in dumped["object"]
    assert dumped["target"]["id"] == _INVITEE_ID


@pytest.mark.spec("CM-11-011")
def test_full_case_invite_replies_have_their_own_semantics() -> None:
    """RV, RI and RC replies to ``Invite(whole VulnerabilityCase)[target=Actor]`` route apart.

    The CASE_MANAGER records the three full-case replies as three different
    RM transitions (``R → V``, ``R → I``, ``R → C``), so the receiver must
    classify each as its own message — distinct from one another, from the
    replies to the stub Invite (which judge nothing), and never ``UNKNOWN``.
    """
    stub, full = _stub_invite(), _full_case_invite()
    stub_reply_semantics = {
        _semantics_of("accept", stub),
        _semantics_of("reject", stub),
    }
    observed = {kind: _semantics_of(kind, full) for kind in _REPLY_CLASSES}

    assert not set(observed.values()) & _UNKNOWN, observed
    assert len(set(observed.values())) == 3, observed
    assert not set(observed.values()) & stub_reply_semantics, (
        f"full-case replies {observed} share semantics with the stub-Invite"
        f" replies {stub_reply_semantics}"
    )


@pytest.mark.spec("VAM-04-011")
@pytest.mark.spec("SE-01-009")
def test_full_case_invite_and_stub_invite_match_different_patterns() -> None:
    """The object's form alone tells the two Invites for the same case
    apart, and every answer to each (ADR-0205).

    Both name an object of type ``VulnerabilityCase``: the stub Invite a
    reference carrying its preview, the full-case Invite the whole case.
    The stub Invite has no ``TentativeReject`` (CM-11-028).
    """
    stub, full = _stub_invite(), _full_case_invite()
    assert _as_id(stub.object_) == _as_id(full.object_) == _CASE_ID

    assert find_matching_semantics(stub) is (
        MessageSemantics.INVITE_ACTOR_TO_CASE
    )
    assert find_matching_semantics(full) is (
        MessageSemantics.INVITE_ACTOR_TO_FULL_CASE
    )
    assert _semantics_of("accept", stub) is (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
    )
    assert _semantics_of("accept", full) is (
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE
    )
    assert _semantics_of("reject", stub) is (
        MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
    )
    assert _semantics_of("reject", full) is (
        MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE
    )
    assert _semantics_of("tentative_reject", stub) in _UNKNOWN
    assert _semantics_of("tentative_reject", full) is (
        MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE
    )


@pytest.mark.spec("VAM-04-012")
def test_full_case_invite_accept_is_not_the_stub_accept() -> None:
    """``Accept(Invite(whole VulnerabilityCase)[target=Actor])`` is RV, not joining."""
    full = _semantics_of("accept", _full_case_invite())

    assert full not in _UNKNOWN
    assert full != _semantics_of("accept", _stub_invite())


@pytest.mark.spec("CM-11-028")
@pytest.mark.spec("VAM-04-013")
def test_full_case_invite_tentative_reject_is_ri_and_stub_has_none() -> None:
    """Only the full-case Invite can be tentatively rejected (CM-11-028)."""
    assert _semantics_of("tentative_reject", _full_case_invite()) not in (
        _UNKNOWN
    )
    assert _semantics_of("tentative_reject", _stub_invite()) in _UNKNOWN


@pytest.mark.spec("VAM-04-014")
def test_full_case_invite_reject_is_not_the_stub_reject() -> None:
    """``Reject(Invite(whole VulnerabilityCase)[target=Actor])`` is RC on the case."""
    full = _semantics_of("reject", _full_case_invite())

    assert full not in _UNKNOWN
    assert full != _semantics_of("reject", _stub_invite())


@pytest.mark.spec("VAM-04-006")
def test_reject_of_stub_invite_is_reject_invite_actor_to_case() -> None:
    """``Reject(Invite(VulnerabilityCase preview)[target=Actor])`` is the stub Reject.

    The stub Invite's object is the case's reference carrying the stub as
    its preview, and its ``Reject`` classifies as
    ``REJECT_INVITE_ACTOR_TO_CASE``.
    """
    stub_invite = _stub_invite()

    assert isinstance(stub_invite.object_, as_TypedReference)
    assert isinstance(stub_invite.object_.preview, as_CasePreview)
    assert (
        _semantics_of("reject", stub_invite)
        is MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
    )
