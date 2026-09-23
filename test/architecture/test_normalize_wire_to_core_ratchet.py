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

**This module used to be a grow-only ratchet, and the direction inverted.** The
set was a list of *already migrated* write paths, so dropping an entry silently
re-opened the shape duality of issue #2232 — core nesting ``rm: RmDimension``
where the wire class had a flat ``rm_state``, so a wire-shaped row yielded
``None`` for ``status.rm.state``. Growing the set was progress.

ADR-0099 detail 3 removes the duality rather than containing it: one class per
concept, so the stored object and the transmitted object are the same object and
there is nothing to project. The set is therefore *empty*, and empty is the goal
state the ratchet was protecting the road to — not a lost ratchet.

The assertions were rewritten accordingly, in both a negative and a positive
form: the set must stay empty, and no wire class may share a ``type_`` value with
a distinct core class. The second catches a reintroduced shadowing class where it
is declared, rather than waiting for someone to add it to a set. Deleting the
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


def test_nothing_needs_wire_to_core_normalisation_any_more():
    """``_NORMALIZE_WIRE_TO_CORE`` must be empty, and empty is the goal state.

    **The ratchet direction inverted, so the assertion had to.** This set may
    previously only *grow*: each entry recorded a shadowing wire class whose shape
    was structurally incompatible with its core counterpart — core nests
    ``rm: RmDimension`` where wire had a flat ``rm_state``, so a wire-shaped row
    silently yielded ``None`` for ``status.rm.state`` (#2232). Normalising on
    write contained that, and dropping an entry silently re-opened it.

    ADR-0099 detail 3 removes the incompatibility instead of containing it. With
    the paired classes deleted there is one class per concept, so the stored and
    transmitted objects are the same object and there is nothing to project.
    Emptiness is therefore not a lost ratchet — it is the condition the ratchet
    was protecting the road to.

    Asserting *empty* rather than deleting the test keeps a live check: an entry
    reappearing means a shadowing wire class was reintroduced, which is the
    duality ADR-0099 exists to prevent. The mechanism's removal is #2940 AC-5.
    """
    assert _NORMALIZE_WIRE_TO_CORE == frozenset(), (
        "_NORMALIZE_WIRE_TO_CORE is non-empty"
        f" ({sorted(_NORMALIZE_WIRE_TO_CORE)}), which means a wire class shadows"
        " a core type again. Under ADR-0099 there should be one class per"
        " concept; collapse the pair rather than normalising it on write."
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
