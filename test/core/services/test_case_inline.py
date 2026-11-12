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

"""Tests for carrying a new case's items and references inline."""

import pytest

from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.vulnerability_item import VulnerabilityItem
from vultron.core.services.case_inline import inline_owned
from vultron.errors import VultronValidationError

_CASE_ID = "https://example.org/cases/c1"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://example.org/actors/cm"
    )


@pytest.mark.spec("AKM-02-004")
def test_a_stored_id_is_carried_as_its_object(dl: SqliteDataLayer) -> None:
    item = make(VulnerabilityItem, cve="CVE-2026-0001")
    dl.create(item)

    assert inline_owned(dl, _CASE_ID, [item.id_], VulnerabilityItem) == [item]


@pytest.mark.spec("AKM-02-004")
def test_an_inline_object_is_kept_as_it_is(dl: SqliteDataLayer) -> None:
    ref = make(CaseReference, url={"href": "https://example.org/a"})

    assert inline_owned(dl, _CASE_ID, [ref], CaseReference) == [ref]


@pytest.mark.spec("AKM-02-004")
def test_an_id_naming_another_type_is_refused(dl: SqliteDataLayer) -> None:
    item = make(VulnerabilityItem, cve="CVE-2026-0001")
    dl.create(item)

    with pytest.raises(VultronValidationError, match="CaseReference"):
        inline_owned(dl, _CASE_ID, [item.id_], CaseReference)
