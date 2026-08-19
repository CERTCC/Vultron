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
"""Architecture ratchet: the write-side wire→core normalization set may only grow.

``_NORMALIZE_WIRE_TO_CORE`` in ``vultron/adapters/driven/db_record.py`` lists the
``type_`` strings whose wire class is projected to its core counterpart before a
row is written.  It is the write-side analogue of ``KNOWN_WIRE_ESCAPES`` in
``test_dl_read_returns_core_objects.py`` (DL-05-004) and needs the same
protection, for the mirror-image reason:

- ``KNOWN_WIRE_ESCAPES`` is a list of *known bad* read paths, so it may only
  **shrink**.
- ``_NORMALIZE_WIRE_TO_CORE`` is a list of *already migrated* write paths, so it
  may only **grow**.  Silently dropping an entry re-opens the shape duality that
  issue #2232 closed, and it would do so without any test noticing: nothing else
  asserts that a given type is normalised.

Fifteen wire classes shadow a ``CORE_VOCABULARY`` entry (their ``type_`` is bare,
so the ``as_``-prefix guard in ``Record.from_obj`` never fires for them).  Two are
normalised today; the remaining thirteen are enumerated below so that a *new*
shadowing type has to be triaged rather than joining the backlog unnoticed.

Related: issue #2232 (the shape duality), issue #2268 (migrating the rest).
"""

# Importing the SQLite adapter transitively imports the core and wire vocabulary
# modules, which is what populates both registries via ``__init_subclass__``.
# Without it the registries are nearly empty and this test would vacuously pass.
import vultron.adapters.driven.datalayer_sqlite  # noqa: F401
from vultron.adapters.driven.db_record import _NORMALIZE_WIRE_TO_CORE
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.wire.as2.vocab.base.registry import VOCABULARY

_WIRE_MODULE_PREFIX = "vultron.wire.as2"

# ---------------------------------------------------------------------------
# Baseline: the types normalised as of issue #2232.  This set may only GROW.
# Adding a type here is the second half of migrating it; removing one is a
# regression, not a refactor.
# ---------------------------------------------------------------------------
_NORMALIZED_AS_OF_2232: frozenset[str] = frozenset(
    {
        "CaseParticipant",
        "ParticipantStatus",
    }
)

# ---------------------------------------------------------------------------
# Shadowing types NOT yet normalised (issue #2268).  This set may only SHRINK:
# migrating a type moves it out of here and into ``_NORMALIZE_WIRE_TO_CORE``.
#
# The ten object types differ from their core counterpart only by key spelling
# today, so a wire-shaped row is misspelled rather than structurally unreadable.
# The five actor types have no ``to_core()`` projection at all, so they cannot be
# normalised until one exists.
# ---------------------------------------------------------------------------
_NOT_YET_NORMALIZED: frozenset[str] = frozenset(
    {
        # No to_core() projection exists for these yet.
        "VultronApplication",
        "VultronGroup",
        "VultronOrganization",
        "VultronPerson",
        "VultronService",
    }
)


def _shadowing_types() -> dict[str, type]:
    """Return wire classes whose bare ``type_`` collides with a core type."""
    return {
        type_: cls
        for type_, cls in VOCABULARY.items()
        if type_ in CORE_VOCABULARY
        and cls.__module__.startswith(_WIRE_MODULE_PREFIX)
    }


def test_registries_are_populated():
    """Guard the guard: an empty registry would make every assertion vacuous."""
    assert len(CORE_VOCABULARY) > 10
    assert len(VOCABULARY) > 50


def test_normalize_set_may_only_grow():
    """Every type normalised as of #2232 must still be normalised."""
    missing = _NORMALIZED_AS_OF_2232 - _NORMALIZE_WIRE_TO_CORE
    assert not missing, (
        "_NORMALIZE_WIRE_TO_CORE lost entries"
        f" {sorted(missing)} — the write path would again persist a wire-shaped"
        " row for those types (issue #2232). The set may only grow."
    )


def test_every_normalized_type_actually_shadows_a_core_type():
    """A stale entry is dead weight — it normalises nothing."""
    shadowing = set(_shadowing_types())
    stale = _NORMALIZE_WIRE_TO_CORE - shadowing
    assert not stale, (
        f"_NORMALIZE_WIRE_TO_CORE entries {sorted(stale)} do not name a wire"
        " class that shadows a CORE_VOCABULARY type; remove them or fix the"
        " spelling."
    )


def test_every_normalized_type_has_a_to_core_projection():
    """Normalisation is implemented by ``to_core()``; without it the write raises."""
    shadowing = _shadowing_types()
    for type_ in sorted(_NORMALIZE_WIRE_TO_CORE):
        cls = shadowing[type_]
        assert hasattr(cls, "to_core"), (
            f"{cls.__name__} is listed in _NORMALIZE_WIRE_TO_CORE but exposes no"
            " to_core(), so every attempt to persist one raises instead of"
            " normalising (issue #2232)."
        )


def test_unmigrated_shadowing_types_are_enumerated():
    """A newly added shadowing type must be triaged, not silently deferred.

    Fails in both directions on purpose:

    - a **new** shadowing wire class appears → decide whether it needs
      normalising (issue #2232) and record the answer here;
    - a type is **migrated** → move it into ``_NORMALIZE_WIRE_TO_CORE`` and drop
      it from ``_NOT_YET_NORMALIZED`` so the backlog stays honest (issue #2268).
    """
    unmigrated = set(_shadowing_types()) - set(_NORMALIZE_WIRE_TO_CORE)
    assert unmigrated == set(_NOT_YET_NORMALIZED), (
        "the set of un-normalised shadowing types changed.\n"
        f"  newly un-normalised: {sorted(unmigrated - _NOT_YET_NORMALIZED)}\n"
        f"  no longer listed:    {sorted(_NOT_YET_NORMALIZED - unmigrated)}"
    )
