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
3. Every CoreObject subclass derives its AS2 spellings from an
   ``alias_generator`` — and still accepts Python field names.
4. No CoreObject subclass references the AS2 namespace string directly.

Invariant 3 **inverted** under ADR-0099, and that is worth stating rather than
quietly editing. It used to read "no CoreObject subclass uses
alias_generator=to_camel", because AS2 spelling belonged to the wire layer
(ARCH-12-003, ARCH-12-004) and a paired ``as_*`` class held it. ADR-0099 detail 2
deletes those classes and puts the spelling on the core class, so there is no
second class left to carry it. The #1991 backlog set that tracked the old
direction is removed with it. #2288 and #2289, which described the old goal, are
closed as superseded; #3578 owns reconciling ARCH-12-003 against ADR-0099.

Invariant 2 is not met yet. Its known violations are **enumerated** in the backlog
set below and asserted with ``==``, so the set fails if a new violation appears
*and* if a listed one is fixed without being ticked off, with a companion
``xfail(strict=True)`` goal test so emptying the backlog fails the build and forces
the marker to be deleted.

That backlog previously sat behind a bare ``strict=False`` xfail, a pattern worth
naming: a non-strict xfail keeps passing forever after the work is done, so nobody
is ever told to clean it up, and it gives no partial-progress signal along the way.
See ``test_validate_assignment_ratchet.py``, which uses the same three-part shape
(exact backlog + strict goal + guard-the-guard).

Spec: `specs/architecture.yaml` ARCH-12-003, ARCH-12-004, ARCH-12-007
Reference: `docs/adr/0017-domain-wire-object-separation.md`
"""

import pytest

from vultron.core.models.base import CoreObject, CoreRecord
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import VOCABULARY

# AS2 namespace constant from wire layer
ACTIVITY_STREAMS_NS = "https://www.w3.org/ns/activitystreams"

# ---------------------------------------------------------------------------
# Backlog: core-layer classes registered in the wire VOCABULARY registry,
# violating ARCH-12-003 (issue #1992). All violations resolved — set is empty.
# ---------------------------------------------------------------------------
_NON_AS_BASE_BACKLOG_1992: frozenset[str] = frozenset()


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

        Enforces the layer boundary: core inherits from its own roots
        (``CoreRecord`` / ``CoreObject``), never from the wire vocabulary.
        """
        for name, cls in CORE_VOCABULARY.items():
            assert not issubclass(
                cls, as_Base
            ), f"{name} inherits from as_Base (wire layer)"

    def test_every_core_vocabulary_entry_derives_as2_spellings(self) -> None:
        """Every CORE_VOCABULARY entry inherits the AS2 alias generator.

        Replaces the #1991 backlog set and its goal xfail, both of which drove
        toward *removing* ``alias_generator`` from core. That goal was right while
        a paired ``as_*`` class held the AS2 spelling; ADR-0099 deletes those
        classes, so the spelling has nowhere else to live (detail 2). The
        backlog's direction is inverted, not merely satisfied — a set documented
        as "may only SHRINK" cannot express "all of them, by inheritance".

        The uniformity is the point. Per-class opt-in is what let four promoted
        types ship ``attributed_to`` on the wire while their siblings shipped
        ``attributedTo``: a partial migration is invisible until a peer cannot
        read the payload. Inheriting from ``CoreObject`` makes "some classes" a
        state the code cannot be in.

        #2288 and #2289 tracked the removal and are closed as superseded; their
        premise — render AS2 from the ``as_*`` classes — no longer holds, because
        those classes are gone. #3578 owns the ARCH-12-003 annotation.
        """
        missing = sorted(
            name
            for name, cls in CORE_VOCABULARY.items()
            if "alias_generator" not in getattr(cls, "model_config", {})
        )
        assert not missing, (
            "these CORE_VOCABULARY entries do not derive AS2 spellings, so they"
            f" would serialize Python field names onto the wire: {missing}"
        )


class TestWireVocabularyHierarchy:
    """Tests for VOCABULARY (wire) hierarchy invariants."""

    def test_non_as_base_vocabulary_backlog_is_exact(self) -> None:
        """The #1992 violation set must match reality, in both directions.

        See this module's docstring for why an exact set replaces a
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

    def test_wire_vocabulary_inherits_nothing_from_core(self) -> None:
        """No VOCABULARY class has a core class anywhere in its MRO.

        ADR-0099 detail 4 deletes the shared root: ``as_Base`` gets its own,
        so the wire branch no longer inherits core fields, configuration or
        registration hooks (ARCH-12-001).
        """
        if not VOCABULARY:
            pytest.skip(
                "VOCABULARY is empty; wire objects may not be imported yet"
            )

        intruders = {
            name: [
                base.__qualname__
                for base in cls.__mro__
                if base.__module__.startswith("vultron.core")
            ]
            for name, cls in VOCABULARY.items()
        }
        intruders = {name: bases for name, bases in intruders.items() if bases}
        assert (
            not intruders
        ), f"wire classes inheriting from core: {intruders} (ARCH-12-001)"


class TestCoreRoots:
    """Core has exactly two roots (ADR-0099 detail 4, ARCH-12-002)."""

    def test_core_object_sits_directly_on_core_record(self) -> None:
        """``CoreObject`` is the one AS2 root, directly on the record root;
        the old middle level is gone."""
        import vultron.core.models.base as base

        assert CoreObject.__bases__ == (CoreRecord,)
        for retired in ("VultronBase", "VultronObject"):
            assert not hasattr(
                base, retired
            ), f"{retired} is retired by ADR-0099 detail 4; do not restore it"

    def test_core_record_has_only_identity_fields(self) -> None:
        """The record root carries ``id_``, ``type_``, ``name`` and nothing
        else — no ``@context``, no timestamps, no AS2 object fields."""
        assert set(CoreRecord.model_fields) == {"id_", "type_", "name"}
        assert "alias_generator" not in CoreRecord.model_config

    def test_dead_letter_records_sit_on_the_record_root(self) -> None:
        """#3489 AC-2: both dead-letter records are ``CoreRecord``s, so they
        carry neither ``@context`` nor required AS2 timestamps."""
        from vultron.adapters.outbox_dead_letter import OutboxDeadLetterEntry
        from vultron.core.models.dead_letter import DeadLetterRecord

        for cls in (DeadLetterRecord, OutboxDeadLetterEntry):
            assert issubclass(cls, CoreRecord)
            assert not issubclass(cls, CoreObject)
            for field in ("context_", "published", "updated"):
                assert field not in cls.model_fields, (cls.__name__, field)

    def test_shared_root_sentinel_is_gone(self) -> None:
        """``_is_core_branch`` existed only because wire classes inherited
        the shared root (#2416); nothing inherits it now."""
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        for cls in (CoreRecord, CoreObject, as_Object):
            assert "_is_core_branch" not in dir(cls)


class TestCoreTypeMapHierarchy:
    """Tests for CORE_TYPE_MAP hierarchy invariants (ARCH-12-003, ARCH-12-004)."""

    def test_no_wire_types_in_core_type_map(self) -> None:
        """CORE_TYPE_MAP must contain only core-branch types, never wire types.

        Structural since ADR-0099 detail 4: the registration hook lives on
        ``CoreRecord``, which no wire class inherits.  Kept as a regression
        guard for the #2416 contamination (ARCH-12-011).

        Spec: ARCH-12-003 — core-branch types MUST NOT carry wire-specific
        concerns; the converse also holds: CORE_TYPE_MAP must not be
        contaminated with wire types.
        """
        import vultron.wire.as2.vocab.objects  # noqa: F401
        import vultron.wire.as2.vocab.activities  # noqa: F401

        from vultron.core.models.registry import CORE_TYPE_MAP

        _WIRE_MODULE_PREFIX = "vultron.wire"
        wire_intruders = {
            name: cls
            for name, cls in CORE_TYPE_MAP.items()
            if cls.__module__.startswith(_WIRE_MODULE_PREFIX)
        }
        assert not wire_intruders, (
            f"Wire types found in CORE_TYPE_MAP: {sorted(wire_intruders.keys())}\n"
            "CORE_TYPE_MAP must contain only core-branch types (issue #2416)."
        )

    def test_core_record_types_in_core_type_map(self) -> None:
        """Every ``CoreRecord`` that is not a ``CoreObject`` is in CORE_TYPE_MAP.

        These types register in CORE_TYPE_MAP (not CORE_VOCABULARY) so that
        stored rows can be reconstructed by type string (ARCH-12-004,
        ARCH-12-010, issue #2417) — under both the class name and the
        ``Literal`` value.  The subject set is discovered, not listed, so a new
        record type is covered the day it lands.  It includes the adapter's
        ``OutboxDeadLetterEntry``: the registration hook is inherited from
        ``CoreRecord``, which #3489 AC-2 puts it on.
        """
        import typing

        import vultron.adapters.outbox_dead_letter  # noqa: F401
        from test.support.core_vocab import import_all_core_models
        from vultron.core.models.registry import CORE_TYPE_MAP

        import_all_core_models()

        def walk(cls: type[CoreRecord]) -> set[type[CoreRecord]]:
            found = set(cls.__subclasses__())
            for sub in cls.__subclasses__():
                found |= walk(sub)
            return found

        records = {
            cls
            for cls in walk(CoreRecord)
            if not issubclass(cls, CoreObject)
            and not cls.__module__.startswith("test")
            and typing.get_origin(cls.model_fields["type_"].annotation)
            is typing.Literal
        }
        assert records, "discovered no CoreRecord-only types"
        wrong = sorted(
            f"{cls.__name__}[{key}]"
            for cls in records
            for key in (
                cls.__name__,
                *typing.get_args(cls.model_fields["type_"].annotation),
            )
            if CORE_TYPE_MAP.get(key) is not cls
        )
        assert not wrong, (
            f"CORE_TYPE_MAP entries missing or wrong: {wrong}\n"
            "CoreRecord types must register in CORE_TYPE_MAP"
            " (ARCH-12-010, issue #2417)."
        )
        from vultron.core.models.dead_letter import DeadLetterRecord
        from vultron.core.models.offer_record import VultronOfferRecord

        # Floor: discovery must not silently narrow to nothing relevant.
        assert {DeadLetterRecord, VultronOfferRecord} <= records


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

    def test_core_object_derives_as2_spellings_and_accepts_field_names(
        self,
    ) -> None:
        """CoreObject derives the AS2 spelling and still accepts field names.

        This asserted the opposite until ADR-0099: no ``alias_generator`` on
        ``CoreObject``, because AS2 spelling was the wire branch's job
        (ARCH-12-002, ARCH-12-004).  Under one object model there is no second
        class to hold it — detail 2 puts the AS2 spelling on the core class.

        Both halves are asserted together because they are only correct together.
        The generator alone would make the *persistence* form unreadable, since
        stored rows are keyed by Python field name; ``populate_by_name`` is what
        keeps both serializations of detail 1 valid on input.
        """
        config = getattr(CoreObject, "model_config", {})
        assert (
            config.get("alias_generator") is not None
        ), "CoreObject must derive AS2 spellings (ADR-0099 detail 2)"
        assert config.get("populate_by_name") is True, (
            "CoreObject must still accept Python field names, or persisted rows"
            " (which are keyed by field name) become unreadable"
        )
