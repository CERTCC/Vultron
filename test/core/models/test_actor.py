"""Tests for the core Vultron actor domain models."""

from typing import Literal

from vultron.core.models.actor import (
    CoreActor,
    VultronActorMixin,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_VOCABULARY


def test_core_actor_inherits_core_object():
    assert issubclass(CoreActor, CoreObject)


def test_vultron_actor_mixin_aliases_core_actor():
    assert VultronActorMixin is CoreActor


def test_core_actor_has_embargo_policy_field():
    actor = CoreActor()
    assert actor.embargo_policy is None


def test_person_org_service_application_and_group_register():
    snapshot = dict(CORE_VOCABULARY)
    try:
        assert VultronPerson().type_ == "Person"
        assert VultronOrganization().type_ == "Organization"
        assert VultronService().type_ == "Service"
        assert VultronApplication().type_ == "Application"
        assert VultronGroup().type_ == "Group"

        for cls in (
            VultronPerson,
            VultronOrganization,
            VultronService,
            VultronApplication,
            VultronGroup,
        ):
            assert cls.__name__ in CORE_VOCABULARY
            assert CORE_VOCABULARY[cls.__name__] is cls
    finally:
        CORE_VOCABULARY.clear()
        CORE_VOCABULARY.update(snapshot)


def test_concrete_actor_type_annotations_are_literal():
    assert VultronPerson.model_fields["type_"].annotation == Literal["Person"]
    assert (
        VultronOrganization.model_fields["type_"].annotation
        == Literal["Organization"]
    )
