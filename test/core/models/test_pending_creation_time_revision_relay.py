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

"""The durable creation-time revision relay obligation (EP-04-011, #4121)."""

from typing import Any

import pytest
from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.pending_creation_time_revision_relay import (
    PendingCreationTimeRevisionRelay,
)
from vultron.core.models.registry import CORE_TYPE_MAP
from vultron.core.services.embargo_duration import EmbargoDurationSource

CASE_ID = "https://example.org/cases/c-1"
MANAGER = "https://example.org/actors/case-actor"


def _fields(**overrides: Any) -> dict[str, Any]:
    return {
        "case_id": CASE_ID,
        "embargo_id": f"{CASE_ID}/embargo_events/e-1",
        "proposal_id": "urn:uuid:invite-1",
        "losing_source": "actor_default",
        "report_id": "https://example.org/reports/r-1",
        "case_actor_id": MANAGER,
        **overrides,
    }


@pytest.mark.spec("EP-04-011")
def test_the_id_is_keyed_on_the_case() -> None:
    """One obligation per case: creation-time initialization runs once per
    case (EP-04-012), so a second write for the case replaces the first."""
    marker = PendingCreationTimeRevisionRelay(**_fields())

    assert marker.id_ == PendingCreationTimeRevisionRelay.build_id(CASE_ID)
    assert "/" not in marker.id_.removeprefix("pending-revision-relay/")


@pytest.mark.spec("EP-04-011")
def test_losing_source_mirrors_the_duration_source_values() -> None:
    """The record spells the values out (a core model does not import a
    core service); they must stay the enum's.  Only a sender proposal or an
    actor default can lose: shortest-wins registers a revision only when both
    held terms, so the protocol default never does."""
    for source in (
        EmbargoDurationSource.SENDER_PROPOSAL,
        EmbargoDurationSource.ACTOR_DEFAULT,
    ):
        PendingCreationTimeRevisionRelay(**_fields(losing_source=source.value))
    with pytest.raises(ValidationError):
        PendingCreationTimeRevisionRelay(
            **_fields(
                losing_source=EmbargoDurationSource.PROTOCOL_DEFAULT.value
            )
        )


@pytest.mark.spec("EP-04-011")
def test_an_unknown_losing_source_is_refused() -> None:
    with pytest.raises(ValidationError):
        PendingCreationTimeRevisionRelay(**_fields(losing_source="neither"))


@pytest.mark.spec("CS-08-002")
@pytest.mark.parametrize(
    "field",
    ["case_id", "embargo_id", "proposal_id", "report_id", "case_actor_id"],
)
def test_a_blank_required_field_is_refused(field: str) -> None:
    with pytest.raises(ValidationError):
        PendingCreationTimeRevisionRelay(**_fields(**{field: "  "}))


@pytest.mark.spec("EP-04-011")
def test_it_round_trips_through_the_store() -> None:
    assert (
        CORE_TYPE_MAP["PendingCreationTimeRevisionRelay"]
        is PendingCreationTimeRevisionRelay
    )
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    marker = PendingCreationTimeRevisionRelay(**_fields())
    dl.save(marker)

    assert dl.read(marker.id_) == marker
    assert dl.list_objects("PendingCreationTimeRevisionRelay") == [marker]


@pytest.mark.spec("EP-04-011")
@pytest.mark.spec("ARCH-10-001")
def test_an_obligation_with_no_report_is_refused() -> None:
    """A relay needs the reporter, so an obligation naming no report could
    never be discharged; it fails at construction instead."""
    with pytest.raises(ValidationError):
        PendingCreationTimeRevisionRelay(**_fields(report_id=None))
