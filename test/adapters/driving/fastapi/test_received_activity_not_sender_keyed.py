#!/usr/bin/env python
"""
DL-06-006: a received activity is never held under its sender's id.

The receiver's type tables are where its own sent activities live, so a
received copy stored there under the sender's id is read as one of its own
(#4866).  Strict xfails until inbox ingress stops writing that row (#4871).
"""

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

import pytest

from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.behaviors.case.nodes.proposal_retry_marker import (
    case_is_announced,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_SENDER_URI = "https://example.org/actors/mallory"
_RECEIVER_URI = "https://example.org/actors/case-actor"
_CASE_ID = "https://example.org/cases/c1"

_NOT_YET = pytest.mark.xfail(
    strict=True,
    reason="DL-06-006: inbox ingress still stores the activity under the"
    " sender's id. #4871.",
)


def _create_case(actor: str) -> as_Create:
    return as_Create(
        actor=actor,
        object_=as_VulnerabilityCase(id_=_CASE_ID, name="c1"),
        context=_CASE_ID,
    )


def _deliver(datalayer, activity: as_Create) -> None:
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert FastAPIIngressAdapter(datalayer).parse(body) is not None


@pytest.mark.spec("DL-06-006")
def test_the_receivers_own_create_is_an_announcement(datalayer):
    datalayer.create(_create_case(_RECEIVER_URI))
    assert case_is_announced(datalayer, _CASE_ID) is True


@pytest.mark.spec("DL-06-006")
@_NOT_YET
def test_ingress_holds_nothing_under_the_senders_id(datalayer):
    activity = _create_case(_SENDER_URI)
    _deliver(datalayer, activity)
    assert datalayer.read(activity.id_) is None


@pytest.mark.spec("DL-06-006")
@_NOT_YET
def test_a_received_create_naming_the_case_is_not_an_announcement(datalayer):
    _deliver(datalayer, _create_case(_SENDER_URI))
    assert case_is_announced(datalayer, _CASE_ID) is False
