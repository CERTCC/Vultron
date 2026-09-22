"""Tests for the core Vultron actor domain models."""

from typing import Literal

from vultron.core.models.actor import (
    CoreActor,
    VultronApplication,
    VultronGroup,
    VultronOrganization,
    VultronPerson,
    VultronService,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.enums import VultronActorType
from vultron.core.models.registry import CORE_VOCABULARY


def test_core_actor_inherits_core_object():
    assert issubclass(CoreActor, CoreObject)


def test_retired_vultron_actor_mixin_alias_is_gone():
    """``VultronActorMixin = CoreActor`` is removed (#3484 AC-2).

    It was a backward-compatibility alias with no production consumer, and it
    collided by name with the wire class now called ``as_VultronActorMixin``.
    Because it was introduced by *assignment* rather than a ``class`` statement,
    ``test_wire_vocab_naming.py`` could not see the collision at all — which is
    the hole ``test_no_wire_class_name_is_also_a_core_name`` now closes. Keeping
    the alias would keep that collision alive under a name nothing reads.
    """
    import vultron.core.models.actor as actor_module
    import vultron.core.models as models_package

    assert not hasattr(actor_module, "VultronActorMixin")
    assert not hasattr(models_package, "VultronActorMixin")


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
    assert (
        VultronPerson.model_fields["type_"].annotation
        == Literal[VultronActorType.PERSON]
    )
    assert (
        VultronOrganization.model_fields["type_"].annotation
        == Literal[VultronActorType.ORGANIZATION]
    )
