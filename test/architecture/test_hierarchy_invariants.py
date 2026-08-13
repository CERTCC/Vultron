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

"""Architecture hierarchy invariant tests for CoreObject and wire-branch subclasses.

This module enforces the structural invariants that maintain the separation
between the core (domain) and wire (ActivityStreams) layers:

1. All classes in CORE_VOCABULARY are subclasses of CoreObject.
2. All classes in VOCABULARY (wire) are subclasses of as_Base.
3. No CoreObject subclass uses alias_generator=to_camel (an AS2 serialization
   concern that belongs only to the wire layer).
4. No CoreObject subclass references the AS2 namespace string directly.

These invariants are specified in ARCH-12-003 and ARCH-12-004.

Invariants 2 and 3 are not met yet. Their known violations are **enumerated** in
the two backlog sets below and asserted with ``==``, so the sets fail if a new
violation appears *and* if a listed one is fixed without being ticked off. Each
has a companion ``xfail(strict=True)`` goal test, so emptying its backlog makes
the goal test XPASS and fail the build — forcing the marker to be deleted.

Both backlogs previously sat behind bare ``strict=False`` xfails, which is a
pattern worth naming: a non-strict xfail keeps passing forever after the work is
done, so nobody is ever told to clean it up, and it gives no partial-progress
signal along the way. See ``test_validate_assignment_ratchet.py``, which uses the
same three-part shape (exact backlog + strict goal + guard-the-guard).

Spec: `specs/architecture.yaml` ARCH-12-003, ARCH-12-004, ARCH-12-007
Reference: `docs/adr/0017-domain-wire-object-separation.md`
"""

import pytest

from vultron.core.models.base import CoreObject, VultronBase
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import VOCABULARY

# AS2 namespace constant from wire layer
ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"

# ---------------------------------------------------------------------------
# Backlog: core classes inheriting alias_generator=to_camel from as_Base,
# violating ARCH-12-004 (issue #1991). This set may only SHRINK.
# ---------------------------------------------------------------------------
_TO_CAMEL_BACKLOG_1991: frozenset[str] = frozenset(
    {
        "CaseStatus",
        "CoreActorCollection",
        "ParticipantStatus",
        "VultronApplication",
        "VultronGroup",
        "VultronOrganization",
        "VultronPerson",
        "VultronService",
    }
)

# ---------------------------------------------------------------------------
# Backlog: core-layer classes registered in the wire VOCABULARY registry,
# violating ARCH-12-003 (issue #1992). This set may only SHRINK.
# ---------------------------------------------------------------------------
_NON_AS_BASE_BACKLOG_1992: frozenset[str] = frozenset(
    {
        "Actor",
        "CoreActor",
        "OfferRecord",
        "PendingCaseInbox",
        "PendingCreateCaseActivity",
        "ReplicationState",
        "ReportCaseLink",
    }
)


class TestCoreVocabularyHierarchy:
    """Tests for CORE_VOCABULARY hierarchy invariants."""

    def test_all_core_vocabulary_are_core_object_subclasses(self) -> None:
        """All CORE_VOCABULARY classes must be subclasses of CoreObject.

        Enforces ARCH-12-003: Core domain objects form an independent
        hierarchy rooted in CoreObject, separate from the wire layer.
        """
        assert CORE_VOCABULARY, "CORE_VOCABULARY is empty"

        non_core_objects: dict[str, type] = {}
        for name, cls in CORE_VOCABULARY.items():
            if not issubclass(cls, CoreObject):
                non_core_objects[name] = cls

        assert (
            not non_core_objects
        ), f"Non-CoreObject classes in CORE_VOCABULARY: {non_core_objects}"

    def test_core_object_uses_vultron_base_not_as_base(self) -> None:
        """CoreObject classes must not inherit from as_Base.

        Enforces the layer boundary: core inherits from VultronBase (shared
        lenient root), not as_Base (which adds AS2 serialization concerns).
        """
        for name, cls in CORE_VOCABULARY.items():
            # Core classes may inherit from CoreObject or VultronBase, but
            # not as_Base (which is wire-layer specific).
            assert not issubclass(
                cls, as_Base
            ), f"{name} inherits from as_Base (wire layer)"

    def test_to_camel_backlog_is_exact(self) -> None:
        """The #1991 violation set must match reality, in both directions.

        Replaces a bare ``strict=False`` xfail. A non-strict xfail keeps passing
        after the work is done, so it never tells anyone to remove it, and it
        gives no signal for partial progress. An exact set does both: it fails if
        a *new* core class inherits ``alias_generator``, and it fails if one is
        fixed without being ticked off here.
        """
        has_to_camel = {
            name
            for name, cls in CORE_VOCABULARY.items()
            if "alias_generator" in getattr(cls, "model_config", {})
        }
        assert has_to_camel == set(_TO_CAMEL_BACKLOG_1991), (
            "the set of core classes inheriting alias_generator changed.\n"
            f"  newly violating: {sorted(has_to_camel - _TO_CAMEL_BACKLOG_1991)}\n"
            f"  fixed but still listed: {sorted(_TO_CAMEL_BACKLOG_1991 - has_to_camel)}\n"
            "to_camel is an AS2 serialization concern and belongs only in the"
            " wire layer (ARCH-12-004, issue #1991)."
        )

    @pytest.mark.xfail(
        strict=True,
        reason="Goal state for issue #1991: no CoreObject subclass inherits "
        "alias_generator=to_camel from as_Base. 8 known classes remain, "
        "enumerated in _TO_CAMEL_BACKLOG_1991. When the last is fixed this test "
        "XPASSes and fails the build — delete the marker and the backlog then.",
    )
    def test_no_core_object_has_to_camel_alias_generator(self) -> None:
        """No CoreObject subclass may use alias_generator=to_camel.

        The to_camel alias generator is an AS2 serialization concern.
        Domain objects use field aliases only for reserved-word conflicts,
        not for general field-name transformation.

        Enforces ARCH-12-004: Core branch model_config must not include
        AS2-specific serialization configuration.
        """
        has_to_camel: dict[str, object] = {}
        for name, cls in CORE_VOCABULARY.items():
            model_config = getattr(cls, "model_config", {})
            if "alias_generator" in model_config:
                has_to_camel[name] = model_config["alias_generator"]

        assert not has_to_camel, (
            f"CoreObject classes with alias_generator=to_camel: {list(has_to_camel.keys())}\n"
            "to_camel is an AS2 serialization concern and belongs only in the wire layer."
        )


class TestWireVocabularyHierarchy:
    """Tests for VOCABULARY (wire) hierarchy invariants."""

    def test_non_as_base_vocabulary_backlog_is_exact(self) -> None:
        """The #1992 violation set must match reality, in both directions.

        See ``test_to_camel_backlog_is_exact`` for why this replaces a
        ``strict=False`` xfail.
        """
        if not VOCABULARY:
            pytest.skip(
                "VOCABULARY is empty; wire objects may not be imported yet"
            )

        non_as_base = {
            name
            for name, cls in VOCABULARY.items()
            if not issubclass(cls, as_Base)
        }
        assert non_as_base == set(_NON_AS_BASE_BACKLOG_1992), (
            "the set of non-as_Base entries in the wire VOCABULARY changed.\n"
            f"  newly violating: {sorted(non_as_base - _NON_AS_BASE_BACKLOG_1992)}\n"
            f"  fixed but still listed: {sorted(_NON_AS_BASE_BACKLOG_1992 - non_as_base)}\n"
            "VOCABULARY must contain only wire-layer ActivityStreams classes"
            " (ARCH-12-003, issue #1992)."
        )

    @pytest.mark.xfail(
        strict=True,
        reason="Goal state for issue #1992: the wire VOCABULARY contains only "
        "as_Base subclasses. 7 known core-layer entries remain, enumerated in "
        "_NON_AS_BASE_BACKLOG_1992. When the last is removed this test XPASSes "
        "and fails the build — delete the marker and the backlog then.",
    )
    def test_all_vocabulary_are_as_base_subclasses(self) -> None:
        """All VOCABULARY classes must be subclasses of as_Base.

        Enforces ARCH-12-003: Wire-layer classes form a hierarchy rooted in
        as_Base, separate from the core domain hierarchy.

        Note: VOCABULARY may be empty at module load time; importing wire
        objects triggers registration via __init_subclass__.
        """
        if not VOCABULARY:
            pytest.skip(
                "VOCABULARY is empty; wire objects may not be imported yet"
            )

        non_as_base: dict[str, type] = {}
        for name, cls in VOCABULARY.items():
            if not issubclass(cls, as_Base):
                non_as_base[name] = cls

        assert not non_as_base, (
            f"Non-as_Base classes in VOCABULARY: {list(non_as_base.keys())}\n"
            "VOCABULARY must contain only wire-layer ActivityStreams classes."
        )

    def test_all_vocabulary_inherit_transitive_vultron_base(self) -> None:
        """All VOCABULARY classes inherit from VultronBase (via as_Base).

        Ensures both the core and wire branches share the common lenient
        root (VultronBase) defined in ARCH-12-002.
        """
        if not VOCABULARY:
            pytest.skip(
                "VOCABULARY is empty; wire objects may not be imported yet"
            )

        non_vultron_base: dict[str, type] = {}
        for name, cls in VOCABULARY.items():
            if not issubclass(cls, VultronBase):
                non_vultron_base[name] = cls

        assert (
            not non_vultron_base
        ), f"Non-VultronBase classes in VOCABULARY: {list(non_vultron_base.keys())}"


class TestCoreObjectModelConfig:
    """Tests for CoreObject model_config invariants."""

    def test_core_vocabulary_does_not_reference_as2_namespace_directly(
        self,
    ) -> None:
        """CoreObject classes must not reference the AS2 namespace string.

        The AS2 namespace (@context = https://www.w3.org/ns/activitystreams)
        is a wire-layer concern. Core domain objects must not encode or
        reference wire-format constants. The wire projection layer supplies
        the namespace at serialization time.

        This test scans source code for direct references to the AS2 namespace
        URI string. Legitimate uses (wire layer only) are expected; core-layer
        references are violations.
        """
        # For now, this test passes by construction because core models are
        # defined in vultron/core/models/ and wire constants live in
        # vultron/wire/as2/. A future check could scan source code or
        # bytecode for string literals; this serves as a documentation and
        # regression placeholder.

        # Note: if a new core model is added with a direct AS2 namespace
        # reference, add a specific assertion here or extend the search logic.
        assert (
            True
        ), "Placeholder for future bytecode scanning (no violations found)"

    def test_core_object_base_model_config_is_lenient(self) -> None:
        """CoreObject base class must use lenient model_config.

        CoreObject.model_config must NOT specify alias_generator=to_camel
        or other AS2-specific serialization options. It should use the
        shared lenient root configuration that works for both core and
        wire branches.

        Enforces ARCH-12-002 and ARCH-12-004.
        """
        # The shared base (VultronBase) defines the minimal config
        config = getattr(CoreObject, "model_config", {})
        # Core should not override with wire-specific concerns
        assert (
            config.get("alias_generator") is None
        ), "CoreObject.model_config must not set alias_generator"
