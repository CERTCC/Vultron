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

"""Tests for the core CaseActor domain model (step 6 of issue #699)."""

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import CoreObject
from vultron.core.models.case_actor import (
    CaseActor,
    VultronCaseActor,
    VultronOutbox,
)
from vultron.core.models.registry import CORE_VOCABULARY


class TestCaseActorBasics:
    """CaseActor is a CoreObject with type_='Service'."""

    def test_inherits_core_object(self):
        assert issubclass(CaseActor, CoreObject)

    def test_type_literal_is_service(self):
        actor = CaseActor()
        assert actor.type_ == "Service"

    def test_has_outbox(self):
        actor = CaseActor()
        assert isinstance(actor.outbox, VultronOutbox)

    def test_outbox_items_default_empty(self):
        actor = CaseActor()
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor.id_)
        dl.create(actor)
        assert dl.outbox_list() == []

    def test_attributed_to_optional(self):
        actor = CaseActor(attributed_to="https://example.org/owner")
        assert actor.attributed_to == "https://example.org/owner"

    def test_id_auto_generated_as_urn(self):
        actor = CaseActor()
        assert actor.id_.startswith("urn:uuid:")


class TestCaseActorRegistration:
    """CaseActor registers under 'CaseActor' key in CORE_VOCABULARY (ADR-0017)."""

    def test_registered_in_core_vocabulary_by_classname(self):
        # CaseActor registers by cls.__name__, not by type_ value "Service"
        assert "CaseActor" in CORE_VOCABULARY
        assert CORE_VOCABULARY["CaseActor"] is CaseActor

    def test_not_registered_under_service_key(self):
        # "Service" key belongs to the wire layer, not core
        assert CORE_VOCABULARY.get("Service") is not CaseActor


class TestCaseActorBackwardCompatAlias:
    """VultronCaseActor must be an alias for CaseActor."""

    def test_alias_is_same_class(self):
        assert VultronCaseActor is CaseActor

    def test_alias_construction_works(self):
        actor = VultronCaseActor()
        assert isinstance(actor, CaseActor)
        assert actor.type_ == "Service"


class TestCaseActorWireRoundTrip:
    """Wire CaseActor.from_core / .to_core must preserve identity."""

    def test_from_core_preserves_id(self):
        from vultron.wire.as2.vocab.objects.case_actor import (
            CaseActor as WireCaseActor,
        )

        core_actor = CaseActor(
            id_="urn:uuid:actor-test",
            attributed_to="https://example.org/owner",
        )
        wire_actor = WireCaseActor.from_core(core_actor)
        assert wire_actor.id_ == "urn:uuid:actor-test"

    def test_to_core_preserves_attributed_to(self):
        from vultron.wire.as2.vocab.objects.case_actor import (
            CaseActor as WireCaseActor,
        )

        wire_actor = WireCaseActor(
            id_="urn:uuid:actor-test",
            attributed_to="https://example.org/owner",
        )
        core_actor = wire_actor.to_core()
        assert isinstance(core_actor, CaseActor)
        assert core_actor.attributed_to == "https://example.org/owner"

    def test_round_trip_preserves_id(self):
        from vultron.wire.as2.vocab.objects.case_actor import (
            CaseActor as WireCaseActor,
        )

        core_actor = CaseActor(
            id_="urn:uuid:actor-roundtrip",
            attributed_to="https://example.org/owner",
        )
        wire_actor = WireCaseActor.from_core(core_actor)
        restored = wire_actor.to_core()
        assert restored.id_ == "urn:uuid:actor-roundtrip"
        assert isinstance(restored, CaseActor)
