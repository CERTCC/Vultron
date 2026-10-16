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
"""Every Announce(VulnerabilityCase) refusal is a guard in the one tree (#4643).

A received delivery runs exactly one tree (CLP-10-005, ADR-0135): the
Announce's turn-aways (an incomplete Announce, an untrusted sender) are guards
in that tree, and the refused Announce is still archived (CLP-10-018).
"""

from typing import Any

import pytest
from pydantic import BaseModel

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_CASE_ID = "https://example.org/cases/case-one-tree"


class _IdlessCase(BaseModel):
    """A case-typed object whose id resolves to nothing."""

    type_: str = "VulnerabilityCase"
    id_: str | None = None


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture()
def event(make_payload) -> Any:
    case = as_VulnerabilityCase(id_=_CASE_ID, name="One tree")
    return make_payload(
        announce_vulnerability_case_activity(
            case, actor=_CASE_ACTOR_ID, context=_CASE_ID
        )
    )


def _anchor(dl: SqliteDataLayer) -> None:
    """Record the invite trust anchor naming the case actor (PCR-03-004)."""
    dl.save(
        VultronPendingCaseInbox(case_id=_CASE_ID, case_actor_id=_CASE_ACTOR_ID)
    )


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("CLP-10-018")
@pytest.mark.parametrize(
    "activity_update, reason",
    [
        (None, "Announce carries no activity"),
        ({"object_": None}, "Announce carries no case object"),
        (
            {"object_": as_VulnerabilityReport(name="Not a case")},
            "Announce object is not a VulnerabilityCase (VulnerabilityReport)",
        ),
        (
            {"object_": _IdlessCase()},
            "Announced case object has no id",
        ),
    ],
    ids=["no-activity", "no-object", "not-a-case", "no-case-id"],
)
def test_incomplete_announce_is_refused_in_one_tree(
    dl, event, tree_runs, activity_update, reason
):
    _anchor(dl)
    activity = (
        None
        if activity_update is None
        else event.activity.model_copy(update=activity_update)
    )
    event = event.model_copy(update={"activity": activity})

    result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason == reason
    assert len(tree_runs) == 1
    assert dl.read(_CASE_ID) is None
    if activity is not None:
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))


@pytest.mark.spec("CLP-10-005")
@pytest.mark.spec("PCR-03-004")
def test_untrusted_sender_is_refused_by_the_tree_guard(dl, event, tree_runs):
    result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason is not None
    assert result.reason.endswith(
        f"No CASE_MANAGER is known for case '{_CASE_ID}' to match sender"
        f" '{_CASE_ACTOR_ID}' — REFUSED (HP-01-006, PCR-03-004)"
    )
    assert len(tree_runs) == 1
    assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))
    assert dl.read(_CASE_ID) is None


@pytest.mark.spec("CLP-10-005")
def test_admitted_announce_runs_one_tree(dl, event, tree_runs):
    _anchor(dl)

    result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

    assert result.disposition == HandlerDisposition.APPLIED
    assert len(tree_runs) == 1
    assert dl.read(_CASE_ID) is not None
