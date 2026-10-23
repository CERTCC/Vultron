"""The DataLayer stores state values as their string value (SM-08-003).

A stored ``ParticipantStatus`` or ``CaseStatus`` row must carry each state as
the same string value the wire form uses (``"ACCEPTED"``, ``"NONE"``,
``"pxa"``), never a Python enum name such as ``"RM.ACCEPTED"`` or an integer,
so a row written by one process is read back as the same state by any other.
The row keys are the model's field names (``rm``, ``em``, ``pxa``), not the
wire aliases.
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

from collections.abc import Iterator
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM

pytestmark = pytest.mark.spec("SM-08-003")

_ACTOR = "https://example.org/actors/state-store-actor"


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    try:
        yield store
    finally:
        store.close()


def _stored(dl: SqliteDataLayer, type_: str, id_: str) -> dict[str, Any]:
    (row,) = [r["data_"] for r in dl.get_all(type_) if r["id_"] == id_]
    assert isinstance(row, dict)
    return row


def test_a_participant_status_row_stores_rm_as_its_string_value(
    dl: SqliteDataLayer,
):
    status = ParticipantStatus(
        id_="urn:uuid:ps-stored",
        context="urn:case:1",
        rm=RmDimension(state=RM.ACCEPTED),
    )
    dl.save(status)

    row = _stored(dl, "ParticipantStatus", status.id_)

    assert row["rm"] == "ACCEPTED"
    assert type(row["rm"]) is str


def test_a_case_status_row_stores_em_and_pxa_as_their_string_values(
    dl: SqliteDataLayer,
):
    status = CaseStatus(id_="urn:uuid:cs-stored", context="urn:case:1")
    dl.save(status)

    row = _stored(dl, "CaseStatus", status.id_)

    assert (row["em"], row["pxa"]) == ("NONE", "pxa")
    assert all(type(row[k]) is str for k in ("em", "pxa"))
