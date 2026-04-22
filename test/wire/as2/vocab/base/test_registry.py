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

from vultron.wire.as2.vocab.base.registry import VOCABULARY, find_in_vocabulary


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

        assert "TestAutoRegType" in VOCABULARY
        assert VOCABULARY["TestAutoRegType"] is as_TestAutoRegType

        # Cleanup to avoid polluting VOCABULARY across tests
        del VOCABULARY["TestAutoRegType"]

    def test_abstract_base_without_type_not_registered(self):
        """Classes with no type_ override in own annotations are not registered."""
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        # as_Object itself has no concrete type_ annotation
        assert (
            "Object" not in VOCABULARY
            or VOCABULARY.get("Object") is not as_Object
        )

    def test_union_type_annotation_not_registered(self):
        """Classes with type_: str | None are skipped (abstract bases)."""
        from pydantic import Field
        from vultron.wire.as2.vocab.base.base import as_Base

        class as_AbstractLike(as_Base):
            type_: str | None = Field(default=None)

        # Should NOT be registered
        assert "AbstractLike" not in VOCABULARY


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
        """Core ActivityStreams 2.0 types are present after discovery."""
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
            assert (
                type_name in VOCABULARY
            ), f"Expected AS2 type '{type_name}' in vocabulary"

    def test_vocab_bug_26040902_regression(self):
        """VulnerabilityReport and VulnerabilityCase are in the vocab.

        Regression test for BUG-26040902: empty vocab registry caused
        ReceiveReportCaseBT to silently fail in Docker (where no test
        conftest imports populated the registry as a side effect).

        With VOCAB-REG-1.2, importing vultron.wire.as2.vocab triggers
        dynamic module discovery which registers all types automatically.
        """
        # This import triggers dynamic discovery — no explicit VulnerabilityCase
        # or VulnerabilityReport import is needed.
        import vultron.wire.as2.vocab  # noqa: F401

        assert (
            "VulnerabilityReport" in VOCABULARY
        ), "BUG-26040902: VulnerabilityReport missing from vocabulary"
        assert (
            "VulnerabilityCase" in VOCABULARY
        ), "BUG-26040902: VulnerabilityCase missing from vocabulary"
        # Verify the classes are actually correct
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        assert VOCABULARY["VulnerabilityReport"] is VulnerabilityReport
        assert VOCABULARY["VulnerabilityCase"] is VulnerabilityCase
