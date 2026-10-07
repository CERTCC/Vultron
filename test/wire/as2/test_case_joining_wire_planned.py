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
"""Planned wire behaviour for joining a case (ADR-0114, ADR-0070, #4006).

Tests for requirements introduced by the case-joining plan: the case stub's
own wire identity (CM-11-013) and the full-case Invite and its replies being
distinguishable from the stub Invite and its replies (CM-11-011, VAM-04-011
through VAM-04-014).  They were strict-``xfail`` until #4045 and #4050
landed; see ``notes/case-joining.md``.
"""

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.factories import rm_invite_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Invite,
    as_Reject,
    as_TentativeReject,
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
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
    return as_VulnerabilityCase(
        id_=_CASE_ID,
        name="JOINING-WIRE",
        attributed_to=_MANAGER_ID,
        stub_summary="Security issue — details shared after acceptance",
    )


def _stub_invite() -> as_Invite:
    """The stub Invite exactly as the CASE_MANAGER's factory builds it."""
    return rm_invite_to_case_activity(
        as_Organization(id_=_INVITEE_ID),
        target=_full_case(),
        actor=_MANAGER_ID,
        id_=f"{_CASE_ID}/invitations/stub-1",
    )


def _full_case_invite() -> as_Invite:
    """``Invite(Actor)[target=VulnerabilityCase]`` — the full-case Invite."""
    return as_Invite(
        id_=f"{_CASE_ID}/invitations/full-1",
        actor=_MANAGER_ID,
        object_=as_Organization(id_=_INVITEE_ID),
        target=_full_case(),
        to=[_INVITEE_ID],
    )


_REPLY_CLASSES: dict[str, type[as_TransitiveActivity]] = {
    "accept": as_Accept,
    "tentative_reject": as_TentativeReject,
    "reject": as_Reject,
}


def _reply(kind: str, invite: as_Invite) -> as_TransitiveActivity:
    return _REPLY_CLASSES[kind](actor=_INVITEE_ID, object_=invite)


def _semantics_of(kind: str, invite: as_Invite) -> MessageSemantics:
    return find_matching_semantics(_reply(kind, invite))


@pytest.mark.spec("CM-11-013")
def test_stub_invite_target_has_its_own_type_and_id() -> None:
    """The stub in a stub Invite is not the case on the wire.

    It serialises with ``type`` ``VulnerabilityCaseStub`` and ID
    ``<case-id>/stub``, and names the case it stands for in a field of its
    own, so the stub Invite and the full-case Invite are told apart by the
    target's ``type`` alone (#4045).
    """
    dumped = _stub_invite().model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    stub = dumped["target"]
    assert isinstance(stub, dict)

    assert stub["type"] == "VulnerabilityCaseStub"
    assert stub["id"] == f"{_CASE_ID}/stub"
    others = {k: v for k, v in stub.items() if k not in {"id", "type"}}
    assert _CASE_ID in others.values(), (
        "the stub must name the case it stands for in a field of its own;"
        f" got {stub!r}"
    )


@pytest.mark.spec("CM-11-011")
def test_full_case_invite_replies_have_their_own_semantics() -> None:
    """RV, RI and RC replies to ``Invite(Actor, VulnerabilityCase)`` route apart.

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
def test_full_case_invite_and_stub_invite_match_different_patterns() -> None:
    """The ``target`` type alone tells the two Invites apart."""
    stub = find_matching_semantics(_stub_invite())
    full = find_matching_semantics(_full_case_invite())

    assert stub not in _UNKNOWN
    assert full not in _UNKNOWN
    assert stub != full


@pytest.mark.spec("VAM-04-012")
def test_full_case_invite_accept_is_not_the_stub_accept() -> None:
    """``Accept(Invite(Actor)[target=VulnerabilityCase])`` is RV, not joining."""
    full = _semantics_of("accept", _full_case_invite())

    assert full not in _UNKNOWN
    assert full != _semantics_of("accept", _stub_invite())


@pytest.mark.spec("VAM-04-013")
def test_full_case_invite_tentative_reject_is_ri_and_stub_has_none() -> None:
    """Only the full-case Invite can be tentatively rejected (CM-11-007)."""
    assert _semantics_of("tentative_reject", _full_case_invite()) not in (
        _UNKNOWN
    )
    assert _semantics_of("tentative_reject", _stub_invite()) in _UNKNOWN


@pytest.mark.spec("VAM-04-014")
def test_full_case_invite_reject_is_not_the_stub_reject() -> None:
    """``Reject(Invite(Actor)[target=VulnerabilityCase])`` is RC on the case."""
    full = _semantics_of("reject", _full_case_invite())

    assert full not in _UNKNOWN
    assert full != _semantics_of("reject", _stub_invite())


@pytest.mark.spec("VAM-04-006")
def test_reject_of_stub_invite_is_reject_invite_actor_to_case() -> None:
    """``Reject(Invite(Actor)[target=VulnerabilityCaseStub])`` is the stub Reject.

    Passing marker: the stub Invite's target is already the stub object, and
    its ``Reject`` already classifies as ``REJECT_INVITE_ACTOR_TO_CASE``.
    """
    from vultron.wire.as2.vocab.objects.vulnerability_case import (
        as_VulnerabilityCaseStub,
    )

    stub_invite = _stub_invite()

    assert isinstance(stub_invite.target, as_VulnerabilityCaseStub)
    assert (
        _semantics_of("reject", stub_invite)
        is MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
    )
