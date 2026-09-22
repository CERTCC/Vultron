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

"""Every wire class is recognisable as one from its name alone.

A class under ``vultron/wire/`` that participates in the AS2 hierarchy MUST be
named ``as_*`` or be private (leading underscore). The point is that a reader —
human or agent — can tell a wire object from a core object without looking up
where it is defined. Conflating the two is the original defect the domain/wire
split was introduced to fix (#2232, #2264).

Spec: ARCH-14-001. Issue: #3484. ADR-0099.

Why classification is by module path, not by name
-------------------------------------------------
This test asks "is every wire class named like one?", so it MUST determine
*wire-ness* from ``cls.__module__``, never from the name. Classifying by name
prefix assumes the answer and is exactly the mistake being guarded against: a
survey written during the ADR-0099 analysis sorted classes by name prefix and
silently mis-filed all 51 non-``as_`` wire classes as core classes, producing
counts that had to be re-derived.

Relationship to ``test_wire_vocab_naming.py``
---------------------------------------------
That test asks a different question — whether a wire class *shadows* a core
model name — and it scans ``class`` statements with the AST. It therefore has a
blind spot this test does not: a core name introduced by **assignment** rather
than by a ``class`` statement is invisible to it. ``VultronActorMixin`` lived in
both layers for exactly that reason — a wire class in
``vocab/objects/vultron_actor.py`` and, in core, the alias
``VultronActorMixin = CoreActor`` in ``core/models/actor.py``. The collision
ratchet reported zero collisions throughout. ``test_no_wire_class_name_is_also_a_core_name``
below closes that gap by comparing against the core package's runtime namespace,
which sees aliases.
"""

import importlib
import pkgutil

import pytest

from vultron.wire.as2.vocab.base.base import as_Base


def _import_tree(package: str) -> None:
    """Import every module in *package* so self-registering classes exist."""
    mod = importlib.import_module(package)
    for _, name, _ in pkgutil.walk_packages(mod.__path__, package + "."):
        try:
            importlib.import_module(name)
        except (
            Exception
        ):  # pragma: no cover - a broken module is another test's problem
            continue


def _all_subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _all_subclasses(sub)
    return found


@pytest.fixture(scope="module")
def wire_classes() -> dict[str, type]:
    """Every ``as_Base`` subclass whose *module* is under ``vultron.wire``."""
    _import_tree("vultron.wire.as2.vocab")
    return {
        cls.__name__: cls
        for cls in _all_subclasses(as_Base)
        if cls.__module__.startswith("vultron.wire")
    }


def _is_conventional(name: str) -> bool:
    """``as_Foo`` is public wire vocabulary; ``_Foo`` is a private message shape."""
    return name.startswith("as_") or name.startswith("_")


@pytest.mark.spec("ARCH-14-001")
def test_every_wire_class_is_named_as_or_private(wire_classes):
    """A wire class must be identifiable as one from its name."""
    offenders = sorted(
        f"{cls.__module__}.{name}"
        for name, cls in wire_classes.items()
        if not _is_conventional(name)
    )
    assert not offenders, (
        "Classes under vultron/wire/ that subclass as_Base but are named like"
        " core classes. Rename to 'as_<Name>', or make it private with a leading"
        " underscore if it is an internal message shape:\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.spec("ARCH-14-001")
def test_the_generated_activity_shapes_are_private(wire_classes):
    """The generated per-message activity classes stay private, not ``as_``-prefixed.

    They are an implementation detail of the message set, reached through the
    factories, and there are enough of them that promoting them to public
    ``as_`` names would drown the vocabulary they sit beside.
    """
    private = [n for n in wire_classes if n.startswith("_")]
    assert private, "expected the generated _XxxActivity shapes to be present"
    assert all(
        n.endswith(("Activity", "Mixin")) or "Activity" in n for n in private
    ), (
        "a private wire class that is not an activity shape — check whether it"
        " should be public 'as_' vocabulary instead:\n  "
        + "\n  ".join(sorted(n for n in private if "Activity" not in n))
    )


@pytest.mark.spec("ARCH-14-001")
def test_no_wire_class_name_is_also_a_core_name(wire_classes):
    """No wire class name may also name something in ``vultron.core.models``.

    Compared against the core package's **runtime namespace**, not its ``class``
    statements, so a name introduced by assignment is caught too. That is the
    case ``test_wire_vocab_naming.py`` cannot see, and the one that let
    ``VultronActorMixin`` exist in both layers undetected.
    """
    _import_tree("vultron.core.models")
    core = importlib.import_module("vultron.core.models")
    core_names = set(dir(core))

    collisions = sorted(name for name in wire_classes if name in core_names)
    assert not collisions, (
        "Name(s) that refer to a wire class AND to something exported from"
        " vultron.core.models. A reader cannot tell which layer they are in:\n  "
        + "\n  ".join(collisions)
    )
