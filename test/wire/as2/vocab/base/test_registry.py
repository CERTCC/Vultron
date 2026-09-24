#!/usr/bin/env python
"""Unit tests for the vocabulary registry (VOCAB-REG-1.1/1.2).

Verifies:
- Flat VOCABULARY dict is populated by __init_subclass__ auto-registration
- Dynamic module discovery populates all expected types at import time
- find_in_vocabulary() returns the correct class or raises KeyError on miss
- Abstract base classes (no concrete type_ annotation) are NOT registered
- Concrete subclasses with union type_ annotations are NOT registered
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

import pytest

from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    find_in_vocabulary,
)


class TestFindInVocabulary:
    def test_returns_class_for_known_type(self):
        """find_in_vocabulary returns the registered class for a known type."""
        # Import vocab to ensure dynamic discovery runs
        import vultron.wire.as2.vocab  # noqa: F401

        cls = find_in_vocabulary("Create")
        assert cls is not None
        assert callable(cls)

    def test_raises_key_error_for_unknown_type(self):
        """find_in_vocabulary raises KeyError for an unregistered type name."""
        with pytest.raises(KeyError, match="NoSuchType"):
            find_in_vocabulary("NoSuchType")

    def test_returned_class_is_correct_type(self):
        """find_in_vocabulary('Create') returns as_Create."""
        import vultron.wire.as2.vocab  # noqa: F401
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )

        cls = find_in_vocabulary("Create")
        assert cls is as_Create

    def test_vultron_types_registered(self):
        """Vultron-specific types are registered after dynamic discovery."""
        import vultron.wire.as2.vocab  # noqa: F401

        for type_name in [
            "VulnerabilityReport",
            "VulnerabilityCase",
            "VulnerabilityRecord",
            "CaseParticipant",
            # Note: EmbargoEvent is intentionally NOT registered — it
            # inherits type_="Event" from as_Event.  See embargo_event.py.
        ]:
            cls = find_in_vocabulary(type_name)
            assert cls is not None, f"Expected '{type_name}' in vocabulary"

    def test_actor_types_registered(self):
        """AS2 actor types (including as_Actor fallback) are registered."""
        import vultron.wire.as2.vocab  # noqa: F401

        for type_name in ["Actor", "Person", "Organization", "Service"]:
            cls = find_in_vocabulary(type_name)
            assert cls is not None, f"Expected '{type_name}' in vocabulary"

    def test_vocabulary_is_flat_dict(self):
        """VOCABULARY is a plain dict, not a nested object."""
        assert isinstance(VOCABULARY, dict)
        # All values should be classes (callables)
        for key, val in VOCABULARY.items():
            assert isinstance(key, str)
            assert callable(val), f"VOCABULARY[{key!r}] is not callable"


class TestAutoRegistration:
    def test_concrete_subclass_registers_via_init_subclass(self):
        """A subclass with a concrete Literal type_ is auto-registered."""
        from pydantic import Field
        from typing import Literal
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        class as_TestAutoRegType(as_Object):
            type_: Literal["TestAutoRegType"] = Field(
                default="TestAutoRegType",
                validation_alias="type",
                serialization_alias="type",
            )

        # VOCABULARY is keyed by full class name (ARCH-23-002)
        assert "as_TestAutoRegType" in VOCABULARY
        assert VOCABULARY["as_TestAutoRegType"] is as_TestAutoRegType

        # WIRE_TYPE_MAP is keyed by wire type_ value (for parser lookups)
        assert "TestAutoRegType" in WIRE_TYPE_MAP
        assert WIRE_TYPE_MAP["TestAutoRegType"] is as_TestAutoRegType

        # Cleanup to avoid polluting registries across tests
        del VOCABULARY["as_TestAutoRegType"]
        del WIRE_TYPE_MAP["TestAutoRegType"]

    def test_abstract_base_without_type_not_registered(self):
        """Classes with no type_ override in own annotations are not registered."""
        # as_Object itself has no concrete type_ annotation — neither registry
        assert "as_Object" not in VOCABULARY
        assert "Object" not in WIRE_TYPE_MAP

    def test_union_type_annotation_not_registered(self):
        """Classes with type_: str | None are skipped (abstract bases)."""
        from pydantic import Field
        from vultron.wire.as2.vocab.base.base import as_Base

        class as_AbstractLike(as_Base):
            type_: str | None = Field(default=None)

        # Should NOT be registered in either registry
        assert "as_AbstractLike" not in VOCABULARY
        assert "AbstractLike" not in WIRE_TYPE_MAP


class TestDynamicDiscovery:
    def test_discovery_populates_at_least_n_types(self):
        """Dynamic discovery registers a substantial number of types."""
        import vultron.wire.as2.vocab  # noqa: F401

        # The registry should have many types after discovery
        assert len(VOCABULARY) >= 20, (
            f"Expected at least 20 vocab types, got {len(VOCABULARY)}: "
            f"{list(VOCABULARY.keys())}"
        )

    def test_core_as2_types_present(self):
        """Core ActivityStreams 2.0 types are findable after discovery."""
        import vultron.wire.as2.vocab  # noqa: F401

        expected = [
            "Create",
            "Update",
            "Delete",
            "Accept",
            "Reject",
            "Offer",
            "Invite",
            "Add",
            "Remove",
            "Undo",
            "Announce",
            "Note",
        ]
        for type_name in expected:
            cls = find_in_vocabulary(type_name)
            assert cls is not None, f"Expected AS2 type '{type_name}' findable"

    def test_vocab_bug_26040902_regression(self):
        """as_VulnerabilityReport and VulnerabilityCase are findable via vocabulary.

        Regression test for BUG-26040902: empty vocab registry caused
        ReceiveReportCaseBT to silently fail in Docker (where no test
        conftest imports populated the registry as a side effect).

        With VOCAB-REG-1.2, importing vultron.wire.as2.vocab triggers
        dynamic module discovery which registers all types automatically.
        """
        # This import triggers dynamic discovery — no explicit VulnerabilityCase
        # or as_VulnerabilityReport import is needed.
        import vultron.wire.as2.vocab  # noqa: F401

        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        # WIRE_TYPE_MAP is keyed by wire type_ value (ARCH-23-002: disjoint from CORE_VOCABULARY)
        assert (
            "VulnerabilityReport" in WIRE_TYPE_MAP
        ), "BUG-26040902: as_VulnerabilityReport missing from WIRE_TYPE_MAP"
        assert (
            "VulnerabilityCase" in WIRE_TYPE_MAP
        ), "BUG-26040902: VulnerabilityCase missing from WIRE_TYPE_MAP"
        assert WIRE_TYPE_MAP["VulnerabilityReport"] is as_VulnerabilityReport
        assert WIRE_TYPE_MAP["VulnerabilityCase"] is as_VulnerabilityCase

        # After ADR-0099 detail 3 deletion (issue #3487), the core class IS the
        # wire class — these are no longer registered under "as_*" in VOCABULARY
        # but are accessible via WIRE_TYPE_MAP (checked above).
        assert "as_VulnerabilityReport" not in VOCABULARY
        assert "as_VulnerabilityCase" not in VOCABULARY

    def test_case_stub_does_not_claim_the_case_wire_type_key(self):
        """VM-01-008: an alias class holds no key of its own (issue #2982).

        ``as_VulnerabilityCaseStub`` emits ``type: "VulnerabilityCase"``, so the
        key belongs to ``as_VulnerabilityCase``. It used to also register under
        ``VulnerabilityCaseStub`` — a key no payload carries, which is why
        ``docs/ns/context.jsonld`` correctly grants the stub no term of its own.
        """
        import vultron.wire.as2.vocab  # noqa: F401 — dynamic discovery

        from vultron.wire.as2.vocab.base.registry import wire_type_value
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
            as_VulnerabilityCaseStub,
        )

        assert wire_type_value(as_VulnerabilityCaseStub) == "VulnerabilityCase"
        assert "VulnerabilityCaseStub" not in WIRE_TYPE_MAP
        assert WIRE_TYPE_MAP["VulnerabilityCase"] is as_VulnerabilityCase

        # The stub stays reachable by class name through VOCABULARY.
        assert (
            VOCABULARY["as_VulnerabilityCaseStub"] is as_VulnerabilityCaseStub
        )


class TestCoreTypeMapFallback:
    """Regression tests for ARCH-12-003 / issue #1992.

    Core-layer types must NOT appear in VOCABULARY directly, but
    find_in_vocabulary() must still locate them via the CORE_TYPE_MAP fallback.
    """

    def setup_method(self):
        # Import the objects subpackage — its _discover_modules() imports each
        # wire vocab module, which in turn imports the core model classes and
        # triggers VultronObject.__init_subclass__ to populate CORE_TYPE_MAP.
        import vultron.wire.as2.vocab.objects  # noqa: F401

    _CORE_TYPE_NAMES = [
        "CoreActor",
        "OfferRecord",
        "PendingCaseInbox",
        "PendingCreateCaseActivity",
        "ReportCaseLink",
        "ReplicationState",
    ]

    @pytest.mark.spec("VM-06-008")
    def test_ordered_collection_is_not_a_core_type(self):
        """No core class claims ``OrderedCollection`` (ISSUE-3563).

        The vestigial ``CoreActorCollection`` registered under that name, so
        the core-map fallback answered a wire caller with a core class
        (ISSUE-3217).  Core models an actor's inbox as a URL, not a list.
        """
        from vultron.core.models.registry import CORE_TYPE_MAP

        assert "OrderedCollection" not in CORE_TYPE_MAP
        assert "CoreActorCollection" not in CORE_TYPE_MAP

    def test_core_types_absent_from_vocabulary(self):
        """None of the formerly-misregistered core types should be in VOCABULARY."""
        for name in self._CORE_TYPE_NAMES:
            assert (
                name not in VOCABULARY
            ), f"ARCH-12-003 violation: {name!r} must not be in wire VOCABULARY"

    def test_actor_key_is_wire_type(self):
        """WIRE_TYPE_MAP['Actor'] must be the wire as_Actor, not CoreActor."""
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.core.models.actor import CoreActor

        assert "Actor" in WIRE_TYPE_MAP
        assert WIRE_TYPE_MAP["Actor"] is as_Actor
        assert WIRE_TYPE_MAP["Actor"] is not CoreActor

    def test_core_types_findable_via_fallback(self):
        """find_in_vocabulary must resolve each formerly-misregistered core type."""
        for name in self._CORE_TYPE_NAMES:
            cls = find_in_vocabulary(name)
            assert (
                cls is not None
            ), f"find_in_vocabulary({name!r}) returned None"
            assert callable(
                cls
            ), f"find_in_vocabulary({name!r}) is not callable"

    def test_core_actor_resolves_to_core_actor_class(self):
        """find_in_vocabulary('CoreActor') returns CoreActor."""
        from vultron.core.models.actor import CoreActor

        cls = find_in_vocabulary("CoreActor")
        assert cls is CoreActor

    def test_offer_record_resolves_correctly(self):
        """find_in_vocabulary('OfferRecord') returns VultronOfferRecord."""
        from vultron.core.models.offer_record import VultronOfferRecord

        cls = find_in_vocabulary("OfferRecord")
        assert cls is VultronOfferRecord

    def test_replication_state_resolves_correctly(self):
        """find_in_vocabulary('ReplicationState') returns VultronReplicationState."""
        from vultron.core.models.replication_state import (
            VultronReplicationState,
        )

        cls = find_in_vocabulary("ReplicationState")
        assert cls is VultronReplicationState

    def test_pending_case_inbox_resolves_correctly(self):
        """find_in_vocabulary('PendingCaseInbox') returns VultronPendingCaseInbox."""
        from vultron.core.models.pending_case_inbox import (
            VultronPendingCaseInbox,
        )

        cls = find_in_vocabulary("PendingCaseInbox")
        assert cls is VultronPendingCaseInbox

    def test_pending_create_case_activity_resolves_correctly(self):
        """find_in_vocabulary('PendingCreateCaseActivity') returns PendingCreateCaseActivity."""
        from vultron.core.models.pending_create_case_activity import (
            PendingCreateCaseActivity,
        )

        cls = find_in_vocabulary("PendingCreateCaseActivity")
        assert cls is PendingCreateCaseActivity

    def test_report_case_link_resolves_correctly(self):
        """find_in_vocabulary('ReportCaseLink') returns VultronReportCaseLink."""
        from vultron.core.models.report_case_link import (
            VultronReportCaseLink,
        )

        cls = find_in_vocabulary("ReportCaseLink")
        assert cls is VultronReportCaseLink


class TestDisjointKeys:
    """ARCH-23-002: set(VOCABULARY) & set(CORE_VOCABULARY) must be empty."""

    def setup_method(self):
        import vultron.wire.as2.vocab.objects  # noqa: F401

    def test_vocabulary_and_core_vocabulary_keys_are_disjoint(self):
        """ARCH-23-002: VOCABULARY and CORE_VOCABULARY key sets are disjoint."""
        from vultron.core.models.registry import CORE_VOCABULARY

        collision = set(VOCABULARY) & set(CORE_VOCABULARY)
        assert collision == set(), (
            f"ARCH-23-002 violation: {len(collision)} key(s) shared between "
            f"VOCABULARY and CORE_VOCABULARY: {sorted(collision)}"
        )

    def test_vocabulary_keys_use_wire_class_prefix(self):
        """VOCABULARY keys use the full 'as_*' wire class name."""
        import vultron.wire.as2.vocab.objects  # noqa: F401

        for key in VOCABULARY:
            assert key.startswith(
                "as_"
            ), f"VOCABULARY key {key!r} does not start with 'as_'"

    def test_wire_type_map_keys_are_stripped(self):
        """WIRE_TYPE_MAP keys are wire type_ values (no 'as_' prefix)."""
        for key in WIRE_TYPE_MAP:
            assert not key.startswith(
                "as_"
            ), f"WIRE_TYPE_MAP key {key!r} still has 'as_' prefix"


class TestWireTypeValues:
    """ARCH-23-003: serialized wire `type_` values are independent of registry key changes."""

    def setup_method(self):
        import vultron.wire.as2.vocab  # noqa: F401

    def test_all_concrete_type_defaults_are_reachable_via_wire_type_map(self):
        """ARCH-23-003: every wire class with a concrete type_ default is findable by that value.

        The registry key is an internal lookup concern; the `type` field value is an
        external protocol commitment. For each wire class registered in WIRE_TYPE_MAP
        with a concrete type_ default, the type_ value must itself be a key in
        WIRE_TYPE_MAP (either as the primary key, or as an override entry), ensuring
        the serialized wire output remains reachable after any key restructuring.
        """
        from pydantic_core import PydanticUndefinedType

        unreachable = []
        for key, cls in WIRE_TYPE_MAP.items():
            field = cls.model_fields.get("type_")
            if field is None:
                continue
            default = field.default
            if isinstance(default, PydanticUndefinedType) or default is None:
                continue
            type_value = str(default)
            # The class must be reachable via its own type_ value
            if WIRE_TYPE_MAP.get(type_value) is None:
                unreachable.append((key, cls.__name__, type_value))

        assert unreachable == [], (
            f"ARCH-23-003: {len(unreachable)} wire class(es) have type_ values that "
            f"are not reachable via WIRE_TYPE_MAP — serialized output would be "
            f"undeserializable: {unreachable}"
        )

    @pytest.mark.parametrize(
        "type_value,expected_class_name",
        [
            ("VulnerabilityCase", "VulnerabilityCase"),
            ("VulnerabilityReport", "VulnerabilityReport"),
            ("Accept", "as_Accept"),
            ("Create", "as_Create"),
            ("Announce", "as_Announce"),
            ("Person", "VultronPerson"),
            ("Service", "VultronService"),
            ("Actor", "as_Actor"),
            ("Add", "as_Add"),
            ("EmbargoEvent", "EmbargoEvent"),
        ],
    )
    def test_critical_type_values_resolve_to_expected_wire_class(
        self, type_value, expected_class_name
    ):
        """ARCH-23-003: key wire type_ values resolve to the same wire classes as before.

        Verifies that registry key restructuring did not alter which class handles
        each wire type_ value, ensuring deserialization is byte-identical to the
        pre-change behaviour.
        """
        cls = find_in_vocabulary(type_value)
        assert cls.__name__ == expected_class_name, (
            f"ARCH-23-003: find_in_vocabulary({type_value!r}) returned "
            f"{cls.__name__!r}, expected {expected_class_name!r}"
        )

    @pytest.mark.spec("VM-01-007")
    @pytest.mark.spec("VM-03-002")
    def test_every_class_presenting_its_own_type_is_reachable_under_it(self):
        """VM-01-007: a class presenting its own ``type`` is what that value finds.

        The mirror of the registry walk above: walk the *classes* rather than
        the registry, so a class that registered nothing is visible.  A class
        presents its ``type_`` default, or its class name without ``as_`` when
        it has none (``set_type_from_class_name``).  When that value is its own
        class-name-derived one, ``WIRE_TYPE_MAP`` must answer it with that very
        class — otherwise an inbound payload carrying the value this class
        emits deserializes to something else, or falls through to the core map
        (ISSUE-3242).  Semantic aliases present an ancestor's ``type`` and are
        out of scope by construction; the rest are in ``_UNREGISTERED_WIRE_TYPES``.
        """
        unreachable = sorted(
            f"{cls.__module__}.{cls.__name__} presents {value!r}; "
            f"WIRE_TYPE_MAP[{value!r}] is "
            f"{getattr(WIRE_TYPE_MAP.get(value), '__name__', None)}"
            for cls, value in _classes_presenting_own_type()
            if WIRE_TYPE_MAP.get(value) is not cls
            and cls.__name__ not in _UNREGISTERED_WIRE_TYPES
        )
        assert unreachable == [], (
            "VM-01-007: these classes present their own class-name-derived "
            "`type` but are not reachable under it. Narrow `type_` to a "
            "`Literal` (VM-03-002), or add the class to "
            "_UNREGISTERED_WIRE_TYPES with the requirement that exempts it:\n"
            + "\n".join(unreachable)
        )

    @pytest.mark.spec("VM-01-007")
    def test_every_exemption_is_live(self):
        """VM-01-007: an exemption names a class that still needs one.

        An entry for a class that no longer exists, no longer presents its own
        ``type``, or has since become reachable is a stale licence: it would
        silently cover a *new* class that reused the name.
        """
        needing = {
            cls.__name__
            for cls, value in _classes_presenting_own_type()
            if WIRE_TYPE_MAP.get(value) is not cls
        }
        assert set(_UNREGISTERED_WIRE_TYPES) - needing == set()

    @pytest.mark.spec("VM-03-002")
    @pytest.mark.spec("VM-06-008")
    @pytest.mark.parametrize(
        "type_value,expected",
        [
            ("Collection", "as_Collection"),
            ("OrderedCollection", "as_OrderedCollection"),
            ("Link", "as_Link"),
        ],
    )
    def test_collection_and_link_types_resolve_to_the_wire_class(
        self, type_value, expected
    ):
        """VM-03-002: these names resolve to the wire class, not the core map.

        ``OrderedCollection`` used to answer a wire caller with a core class
        (ISSUE-3217, ISSUE-3242).  Asserting identity, not merely that the
        lookup succeeds, is what distinguishes the two.
        """
        from vultron.wire.as2.vocab.base.base import as_Base

        cls = find_in_vocabulary(type_value)
        assert cls.__name__ == expected
        assert issubclass(cls, as_Base)
        assert WIRE_TYPE_MAP[type_value] is cls


#: Classes that present their own class-name-derived ``type`` but are
#: deliberately not what that value deserializes to, each with the reason
#: (VM-01-007).  ``test_every_exemption_is_live`` keeps this set from outliving
#: its members.
_UNREGISTERED_WIRE_TYPES: dict[str, str] = {
    "as_Object": "abstract root of the AS2 object branch; the class an "
    "unresolved inline object is left to, not a type Vultron emits",
    "as_VultronObject": "abstract root of the Vultron wire object branch; "
    "every concrete subclass declares its own `type_` (VM-05-001)",
    "as_VultronActorMixin": "mixin carrying Vultron actor extension fields; "
    "never instantiated on its own",
    "as_Person": "VM-01-008 sanctioned shadow: as_VultronPerson owns `Person`",
    "as_Organization": "VM-01-008 sanctioned shadow: as_VultronOrganization "
    "owns `Organization`",
    "as_Service": "VM-01-008 sanctioned shadow: as_VultronService owns "
    "`Service`",
    "as_Application": "VM-01-008 sanctioned shadow: as_VultronApplication "
    "owns `Application`",
    "as_Group": "VM-01-008 sanctioned shadow: as_VultronGroup owns `Group`",
}


def _classes_presenting_own_type() -> list[tuple[type, str]]:
    """Return every production ``as_Base`` subclass presenting its own ``type``.

    Walks ``__subclasses__`` from ``as_Base`` after importing every vocabulary
    package, keeping classes defined under ``vultron.`` so throwaway subclasses
    other tests declare are not mistaken for production vocabulary.
    """
    import vultron.wire.as2.vocab.activities  # noqa: F401
    import vultron.wire.as2.vocab.objects  # noqa: F401
    from vultron.wire.as2.vocab.base.base import as_Base
    from vultron.wire.as2.vocab.base.registry import wire_type_value

    found: list[tuple[type, str]] = []
    seen: set[type] = set()
    pending: list[type] = list(as_Base.__subclasses__())
    while pending:
        cls = pending.pop()
        if cls in seen:
            continue
        seen.add(cls)
        pending.extend(cls.__subclasses__())
        if not cls.__module__.startswith("vultron."):
            continue
        value = wire_type_value(cls)
        if value == cls.__name__.removeprefix("as_"):
            found.append((cls, value))
    return found


class TestSetTypeFromClassName:
    """VM-03-003: set_type_from_class_name must use removeprefix, not lstrip."""

    def test_removeprefix_not_lstrip_for_normal_class(self):
        """set_type_from_class_name strips 'as_' prefix exactly once."""
        from pydantic import Field
        from typing import Literal
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        class as_Widget(as_Object):
            type_: Literal["Widget"] = Field(
                default="Widget",
                validation_alias="type",
                serialization_alias="type",
            )

        obj = as_Widget()
        assert obj.type_ == "Widget"

        del VOCABULARY["as_Widget"]
        del WIRE_TYPE_MAP["Widget"]

    def test_removeprefix_not_lstrip_for_ambiguous_class(self):
        """set_type_from_class_name does NOT strip extra leading 'a'/'s'/'_' chars.

        lstrip('as_') would incorrectly strip leading 'a', 's', or '_' chars
        from the post-prefix remainder (e.g. 'as_SomeThing' via lstrip would
        strip 'S'... actually 'a','s','_' are lowercase, so this demonstrates
        the boundary). The key risk is a class like as_assign (stripped name
        'assign' starts with 'a'/'s'); lstrip would give 'ign'.
        """
        from vultron.wire.as2.vocab.base.base import as_Base

        class as_satellite(as_Base):
            pass

        obj = as_satellite()
        # removeprefix gives 'satellite'; lstrip would give 'tellite'
        assert (
            obj.type_ == "satellite"
        ), f"Expected 'satellite', got {obj.type_!r} — lstrip bug not fixed?"
