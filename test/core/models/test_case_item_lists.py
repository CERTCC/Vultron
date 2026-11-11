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

"""A case holds its vulnerability items and case references (CM-05-021)."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.vulnerability_item import VulnerabilityItem

OWNER = "https://test.example/actors/owner"


@pytest.fixture
def dl():
    layer = SqliteDataLayer(
        "sqlite:///:memory:", actor_id="https://test.example/actors/a"
    )
    yield layer
    layer.clear_all()
    layer.close()


@pytest.mark.spec("CM-05-021")
def test_both_lists_are_empty_by_default():
    case = VulnerabilityCase(attributed_to=OWNER)
    assert case.vulnerability_items == []
    assert case.case_references == []


@pytest.mark.spec("CM-05-021")
def test_the_lists_survive_save_and_read(dl):
    item = VulnerabilityItem(cve="CVE-2024-0001")
    ref = CaseReference(url="https://example.org/a", name="Advisory")
    dl.save(item)
    dl.save(ref)
    case = VulnerabilityCase(
        attributed_to=OWNER,
        vulnerability_items=[item.id_],
        case_references=[ref.id_],
    )
    dl.save(case)

    back = dl.read(case.id_)
    assert isinstance(back, VulnerabilityCase)
    assert back.vulnerability_items == [item.id_]
    assert back.case_references == [ref.id_]
    assert dl.read(item.id_) == item
    assert dl.read(ref.id_) == ref


@pytest.mark.spec("CM-05-021")
def test_the_lists_ride_the_case_snapshot_to_a_replica():
    item = VulnerabilityItem(cve="CVE-2024-0001")
    ref = CaseReference(url="https://example.org/a")
    case = VulnerabilityCase(
        attributed_to=OWNER,
        vulnerability_items=[item.id_, item],
        case_references=[ref.id_],
    )
    replica = VulnerabilityCase.model_validate_json(
        case.model_dump_json(by_alias=True)
    )
    assert replica.vulnerability_items == [item.id_, item]
    assert replica.case_references == [ref.id_]


@pytest.mark.spec("CM-05-021")
def test_a_blank_entry_is_refused():
    with pytest.raises(ValueError):
        VulnerabilityCase(attributed_to=OWNER, vulnerability_items=[" "])


@pytest.mark.spec("CM-05-021")
def test_a_received_case_keeps_both_lists_through_the_extractor():
    from vultron.wire.as2.extractor._builders.objects import (
        _build_case_object,
    )

    item = VulnerabilityItem(cve="CVE-2024-0001")
    case = VulnerabilityCase(
        attributed_to=OWNER,
        vulnerability_items=[item, "urn:uuid:item-2"],
        case_references=["urn:uuid:ref-1"],
    )

    built = _build_case_object(case)["object_"]

    assert built.vulnerability_items == [item, "urn:uuid:item-2"]
    assert built.case_references == ["urn:uuid:ref-1"]
