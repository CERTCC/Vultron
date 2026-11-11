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
"""The ``Multikey`` an actor profile lists under ``assertionMethod`` (ENC-01-002)."""

from typing import Any

import pytest
from pydantic import ValidationError

from test.support.objects import make
from vultron.core.models.actor import VultronOrganization, VultronPerson
from vultron.core.models.multikey import Multikey

ACTOR = "https://example.org/actors/vendorco"
OTHER = "https://example.org/actors/other"
PUBLIC = "z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2"


def _entry(key_id: str = f"{ACTOR}#main-key", controller: str = ACTOR):
    return {
        "id": key_id,
        "type": "Multikey",
        "controller": controller,
        "publicKeyMultibase": PUBLIC,
    }


def _profile(assertion_method: Any) -> dict[str, Any]:
    return {
        "id": ACTOR,
        "type": "Organization",
        "name": "VendorCo",
        "assertionMethod": assertion_method,
    }


@pytest.mark.spec("ENC-01-002")
def test_a_profile_reads_its_keys_from_the_wire_spelling():
    actor = VultronOrganization.model_validate(_profile([_entry()]))

    [key] = actor.assertion_method
    assert key == Multikey(
        id_=f"{ACTOR}#main-key",
        type_="Multikey",
        controller=ACTOR,
        public_key_multibase=PUBLIC,
    )
    assert actor.model_dump(mode="json", by_alias=True)["assertionMethod"] == [
        _entry()
    ]


def test_a_single_key_object_reads_as_a_one_key_list():
    actor = VultronOrganization.model_validate(_profile(_entry()))

    assert [key.id_ for key in actor.assertion_method] == [f"{ACTOR}#main-key"]


def test_a_single_key_instance_reads_as_a_one_key_list():
    key = Multikey.model_validate(_entry())

    actor = VultronOrganization.model_validate(
        {"id": ACTOR, "name": "VendorCo", "assertionMethod": key}
    )

    assert actor.assertion_method == [key]


def test_a_key_without_a_type_is_refused():
    entry = _entry()
    del entry["type"]

    with pytest.raises(ValidationError, match="type"):
        Multikey.model_validate(entry)


def test_a_key_of_another_type_is_refused():
    with pytest.raises(ValidationError):
        Multikey.model_validate({**_entry(), "type": "JsonWebKey"})


def test_a_profile_without_keys_dumps_no_assertion_method():
    actor = make(VultronPerson, id_=ACTOR, name="Vendor")

    assert actor.assertion_method == []
    assert "assertionMethod" not in actor.model_dump(by_alias=True)


@pytest.mark.parametrize(
    "key_id",
    [f"{OTHER}#main-key", ACTOR, f"{ACTOR}#", f"{ACTOR}/main-key"],
    ids=[
        "other-document",
        "no-fragment",
        "empty-fragment",
        "path-not-fragment",
    ],
)
def test_a_key_id_must_be_a_fragment_of_its_controller(key_id: str):
    with pytest.raises(ValidationError, match="fragment of its controller"):
        Multikey.model_validate(_entry(key_id=key_id))


@pytest.mark.parametrize("field", ["id", "controller", "publicKeyMultibase"])
def test_a_key_field_may_not_be_blank(field: str):
    with pytest.raises(ValidationError):
        Multikey.model_validate({**_entry(), field: ""})


def test_a_key_refuses_an_unknown_field():
    with pytest.raises(ValidationError):
        Multikey.model_validate({**_entry(), "secretKeyMultibase": PUBLIC})


@pytest.mark.spec("SIG-02-001")
def test_a_profile_listing_another_actors_key_is_refused():
    with pytest.raises(ValidationError, match="controlled by"):
        VultronOrganization.model_validate(
            _profile([_entry(key_id=f"{OTHER}#main-key", controller=OTHER)])
        )


def test_a_profile_listing_one_key_twice_is_refused():
    with pytest.raises(ValidationError, match="more than once"):
        VultronOrganization.model_validate(_profile([_entry(), _entry()]))


def test_every_violation_is_reported():
    """A profile with a foreign key and a repeated key names both (EH-07-001)."""
    foreign = _entry(key_id=f"{OTHER}#main-key", controller=OTHER)

    with pytest.raises(ValidationError) as caught:
        VultronOrganization.model_validate(
            _profile([foreign, _entry(), _entry()])
        )

    message = str(caught.value)
    assert "controlled by" in message
    assert "more than once" in message
