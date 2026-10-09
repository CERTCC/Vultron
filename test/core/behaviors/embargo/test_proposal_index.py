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

"""``record_embargo_proposal_index`` keeps one correlation per embargo (DL-06)."""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.embargo.proposal_index import (
    record_embargo_proposal_index,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.errors import VultronNotFoundError

CASE_ID = "https://example.org/cases/proposal-index"
EMBARGO_ID = f"{CASE_ID}/embargo_events/e1"


@pytest.fixture
def dl() -> SqliteDataLayer:
    store = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/users/owner"
    )
    store.create(
        VulnerabilityCase(
            id_=CASE_ID, attributed_to="https://example.org/users/owner"
        )
    )
    return store


def _index(dl: SqliteDataLayer) -> dict[str, str]:
    case = cast(VulnerabilityCase, dl.read(CASE_ID))
    return dict(case.pending_embargo_proposal_index)


def test_records_then_reports_an_unchanged_entry(dl: SqliteDataLayer) -> None:
    assert record_embargo_proposal_index(dl, CASE_ID, EMBARGO_ID, "urn:p1")
    assert not record_embargo_proposal_index(dl, CASE_ID, EMBARGO_ID, "urn:p1")
    assert _index(dl) == {EMBARGO_ID: "urn:p1"}


def test_overwrite_replaces_the_entry(dl: SqliteDataLayer) -> None:
    record_embargo_proposal_index(dl, CASE_ID, EMBARGO_ID, "urn:p1")
    assert record_embargo_proposal_index(dl, CASE_ID, EMBARGO_ID, "urn:p2")
    assert _index(dl) == {EMBARGO_ID: "urn:p2"}


@pytest.mark.spec("EP-09-007")
def test_without_overwrite_a_replay_keeps_the_invite(
    dl: SqliteDataLayer,
) -> None:
    """A replayed proposal never displaces the Invite addressed to this store."""
    record_embargo_proposal_index(dl, CASE_ID, EMBARGO_ID, "urn:invite")

    changed = record_embargo_proposal_index(
        dl, CASE_ID, EMBARGO_ID, "urn:proposal", overwrite=False
    )

    assert changed is False
    assert _index(dl) == {EMBARGO_ID: "urn:invite"}


def test_without_overwrite_an_absent_entry_is_recorded(
    dl: SqliteDataLayer,
) -> None:
    assert record_embargo_proposal_index(
        dl, CASE_ID, EMBARGO_ID, "urn:proposal", overwrite=False
    )
    assert _index(dl) == {EMBARGO_ID: "urn:proposal"}


def test_an_unknown_case_raises(dl: SqliteDataLayer) -> None:
    with pytest.raises(VultronNotFoundError):
        record_embargo_proposal_index(
            dl, "https://example.org/cases/missing", EMBARGO_ID, "urn:p"
        )
