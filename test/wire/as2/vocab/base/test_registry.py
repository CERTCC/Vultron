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

        # VOCABULARY is keyed by full wire class name
        assert "as_VulnerabilityReport" in VOCABULARY
        assert "as_VulnerabilityCase" in VOCABULARY
        assert VOCABULARY["as_VulnerabilityReport"] is as_VulnerabilityReport
        assert VOCABULARY["as_VulnerabilityCase"] is as_VulnerabilityCase


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
