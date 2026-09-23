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
"""Architecture check: nothing needs write-side wire→core normalisation.

``_NORMALIZE_WIRE_TO_CORE`` in ``vultron/adapters/driven/db_record.py`` lists the
``type_`` strings whose wire class is projected to its core counterpart before a
row is written.

**This is still a grow-only ratchet. What the entries mean changed, not the
direction.** They used to name shadowing wire classes projected to core via
``to_core()``, because core nested ``rm: RmDimension`` where the wire class had a
flat ``rm_state``, so a wire-shaped row yielded ``None`` for ``status.rm.state``
(#2232).

ADR-0099 detail 3 collapses the pairs, so there is no projection left to perform
and the listed classes no longer have ``to_core()``. But the *re-keying* half of
the job survives: detail 1 keeps persistence on Python field names, and a payload
can still arrive wire-spelled, so ``_storable_to_record`` round-trips it —
validating by alias, dumping without one — to land the canonical key. Dropping an
entry lets a wire-spelled row persist, which ``test_sqlite_crud`` forbids.

Only the ``to_core``-projection assertions are gone, since the methods are. A
positive check is added alongside: no wire class may share a ``type_`` value with a
*distinct* core class, which catches a reintroduced shadowing class where it is
declared rather than waiting for someone to add it to a set. Deleting the
mechanism entirely is #2940 AC-5.

Related: issue #2232 (the shape duality), #3487/#3488 (the last three pairs).
"""

# Importing the SQLite adapter transitively imports the core and wire vocabulary
# modules, which is what populates both registries via ``__init_subclass__``.
# Without it the registries are nearly empty and this test would vacuously pass.
import vultron.adapters.driven.datalayer_sqlite  # noqa: F401
from vultron.adapters.driven.db_record import _NORMALIZE_WIRE_TO_CORE
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.wire.as2.vocab.base.registry import VOCABULARY, WIRE_TYPE_MAP

_WIRE_MODULE_PREFIX = "vultron.wire.as2"


def _shadowing_types() -> dict[str, type]:
    """Return wire classes whose type_ value collides with a core type name.

    After ARCH-23-002 (VOCABULARY/CORE_VOCABULARY keys disjoint), the collision
    check moves from VOCABULARY to WIRE_TYPE_MAP, which is keyed by wire type_
    values and contains all 15 formerly-shadowing wire classes.
    """
    return {
        type_: cls
        for type_, cls in WIRE_TYPE_MAP.items()
        if type_ in CORE_VOCABULARY
        and cls.__module__.startswith(_WIRE_MODULE_PREFIX)
    }


def test_registries_are_populated():
    """Guard the guard: an empty registry would make every assertion vacuous.

    The VOCABULARY threshold dropped from 50 to 40 because collapsing the paired
    classes removes them from the wire registry — the count falling is the change
    working, not a regression. It is still asserted, so a registry that failed to
    populate at all would be caught.
    """
    assert len(CORE_VOCABULARY) > 10
    assert len(VOCABULARY) > 40
    assert len(WIRE_TYPE_MAP) > 40


_RE_KEYED_TYPES: frozenset[str] = frozenset(
    {
        "CaseParticipant",
        "CaseStatus",
        "ParticipantStatus",
    }
)


def test_normalize_set_may_only_grow():
    """Every type re-keyed on write must still be re-keyed.

    **The ratchet direction survives ADR-0099; what the entries mean changed.**
    They used to name shadowing wire classes projected via ``to_core()``, because
    core nested ``rm: RmDimension`` where wire had a flat ``rm_state`` and a
    wire-shaped row silently yielded ``None`` for ``status.rm.state`` (#2232).
    Detail 3 collapses the pairs, so there is no projection left and these classes
    no longer have ``to_core()``.

    The re-keying half is still load-bearing, which is why this stays grow-only.
    Detail 1 keeps persistence on Python field names, and a payload can still
    arrive wire-spelled, so ``_storable_to_record`` round-trips it to land the
    canonical key. Dropping an entry lets a wire-spelled row persist —
    ``test_sqlite_crud`` asserts it must not.

    I emptied this set once on the reasoning that "nothing needs projecting any
    more", which was true and beside the point: it silently removed the re-keying
    too. Hence the explicit note.
    """
    missing = _RE_KEYED_TYPES - _NORMALIZE_WIRE_TO_CORE
    assert not missing, (
        f"_NORMALIZE_WIRE_TO_CORE lost entries {sorted(missing)} — a"
        " wire-spelled row for those types would persist unchanged, and core"
        " readers would see the start-state default instead (#2232). The set may"
        " only grow."
    )


def test_no_wire_class_shadows_a_core_type_any_more():
    """No wire class may share a ``type_`` value with a distinct core class.

    The positive form of the invariant above: it catches the reintroduction of a
    shadowing class at the point it is declared, rather than waiting for someone
    to add it to the normalisation set.
    """
    shadowing = {
        type_: cls.__name__
        for type_, cls in _shadowing_types().items()
        if cls is not CORE_VOCABULARY.get(type_)
    }
    assert not shadowing, (
        "these wire classes shadow a CORE_VOCABULARY type without being the same"
        f" class: {shadowing}. ADR-0099 detail 3 allows one class per concept."
    )
