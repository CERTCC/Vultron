#!/usr/bin/env python
"""Unit tests for FastAPIIngressAdapter."""

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

from vultron.adapters.driven.db_record import object_to_record
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept
from vultron.wire.as2.vocab.base.objects.actors import as_Organization
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_ACTOR_URI = "https://example.org/actors/alice"
_INVITEE_URI = "https://example.org/actors/bob"


def _make_accept_invite(case, invitee, actor_uri=_ACTOR_URI):
    """Build a minimal Accept(Invite(actor, case)) wire object."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Invite,
    )

    invite = as_Invite(
        actor=actor_uri,
        object_=invitee,
        target=case.id_,
    )
    return as_Accept(actor=_INVITEE_URI, object_=invite)


def test_rehydrate_expands_nested_invite_target(datalayer):
    """FastAPIIngressAdapter.rehydrate() must expand Invite.target from bare ID.

    When vendor receives Accept(Invite) from an invitee, the Invite object's
    ``target`` field is the VulnerabilityCase URI.  Wire-layer rehydrate()
    only recurses into ``object_``, leaving ``target`` as a bare string.
    The adapter must call dl.hydrate() on the nested Invite so that
    CommitCaseLedgerEntryNode's _bare_inline_object_path() finds an inline
    dict for ``target``, not a bare string.
    """
    case = VulnerabilityCase(name="Test Case for Accept-Invite")
    datalayer.create(object_to_record(case))

    invitee = as_Organization(name="Invitee")
    datalayer.create(object_to_record(invitee))

    accept = _make_accept_invite(case, invitee)
    datalayer.create(object_to_record(accept))

    adapter = FastAPIIngressAdapter(dl=datalayer)
    result = adapter.rehydrate(accept)

    assert isinstance(result, as_Activity)
    nested_invite = getattr(result, "object_", None)
    assert nested_invite is not None, "object_ should be present"
    assert not isinstance(
        nested_invite, str
    ), "object_ should not be a bare string"

    invite_target = getattr(nested_invite, "target", None)
    assert (
        invite_target is not None
    ), "Invite.target should be present after rehydration"
    assert not isinstance(
        invite_target, str
    ), "Invite.target must be an inline object, not a bare string ID"
    assert isinstance(
        invite_target, VulnerabilityCase
    ), f"Invite.target must be a VulnerabilityCase; got {type(invite_target).__name__}"
