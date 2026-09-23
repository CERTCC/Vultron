"""Ratchet: the two wire vocabulary registries keep their declared key forms.

``VOCABULARY`` is keyed by wire class name (``as_VultronPerson``), ``WIRE_TYPE_MAP``
by the emitted wire ``type`` value (``Person``). The forms are deliberately
different because the questions are: *which class is named this?* versus *which
class does this inbound ``type`` value deserialize to?* Keeping them apart is also
what keeps ``VOCABULARY`` disjoint from ``CORE_VOCABULARY`` (ARCH-23-002).

A ``WIRE_TYPE_MAP`` key that is not a ``type`` value any object carries is
unreachable from the wire, and it lets a caller holding a *class* name resolve a
wire class by name coincidence, which ARCH-23-001 forbids. Both were true of six
keys before #2982: the five ``as_Vultron*`` actor classes registered under their
stripped class names (``VultronPerson`` — also the name of a core type) as well as
their ``type`` values (``Person``), and ``as_VulnerabilityCaseStub`` registered
under ``VulnerabilityCaseStub`` while emitting ``type: "VulnerabilityCase"``.

Spec: `specs/vocabulary-model.yaml` VM-01-004, VM-01-007.
See: GitHub issue #2982.
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

import importlib
import pkgutil

import vultron.wire.as2.vocab as _vocab
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.registry import (
    VOCABULARY,
    WIRE_TYPE_MAP,
    declared_wire_type,
    declares_registrable_type,
    is_wire_type_alias,
    wire_type_value,
)

#: Lower bound on registry size, so a broken import cannot make the ratchet pass
#: vacuously: registration is a submodule import side effect (VM-01-005), and a
#: bare ``from ... import WIRE_TYPE_MAP`` yields an empty dict.
_MIN_REGISTERED_TYPES = 50

#: The only ``type`` values two unflagged classes may share (VM-01-007): the
#: Vultron actor subtypes deliberately shadow their base AS2 actor classes so an
#: inbound actor keeps its extension fields. Maps each value to the class that
#: MUST win the key.
_SANCTIONED_SHADOWS = {
    "Person": "as_VultronPerson",
    "Organization": "as_VultronOrganization",
    "Service": "as_VultronService",
    "Application": "as_VultronApplication",
    "Group": "as_VultronGroup",
}


def _force_full_registration() -> None:
    """Import every wire vocabulary submodule so the registry is populated."""
    for module in pkgutil.walk_packages(
        _vocab.__path__, f"{_vocab.__name__}."
    ):
        importlib.import_module(module.name)


def _declared_type_wire_classes() -> list[type[as_Base]]:
    """Return every wire class that declares a concrete ``type`` default.

    Abstract and intermediate bases (``as_Object``, ``as_VultronObject``,
    ``as_VultronActorMixin``) declare none and are excluded — they are never the
    target of a ``type``-value lookup.
    """
    found: list[type[as_Base]] = []

    def walk(cls: type[as_Base]) -> None:
        for sub in cls.__subclasses__():
            if sub.__module__.startswith(
                "vultron.wire.as2.vocab"
            ) and declared_wire_type(sub):
                found.append(sub)
            walk(sub)

    walk(as_Base)
    return found


def test_registries_are_populated() -> None:
    """The ratchets below are only meaningful against populated registries."""
    _force_full_registration()
    for name, registry in (
        ("VOCABULARY", VOCABULARY),
        ("WIRE_TYPE_MAP", WIRE_TYPE_MAP),
    ):
        assert len(registry) >= _MIN_REGISTERED_TYPES, (
            f"{name} has only {len(registry)} entries; dynamic discovery did "
            "not run, so the key-form ratchets would pass vacuously."
        )


def test_every_vocabulary_key_is_its_class_name() -> None:
    """VM-01-004: the key is the wire class name, ``as_`` prefix included."""
    _force_full_registration()

    divergent = {
        key: cls.__name__
        for key, cls in VOCABULARY.items()
        if key != cls.__name__
    }

    assert not divergent, (
        "VOCABULARY keys must equal their registered class's __name__ "
        "(VM-01-004). Divergent entries {key: class}: " + repr(divergent)
    )


def test_every_wire_type_map_key_is_its_class_wire_type_value() -> None:
    """VM-01-007: the key is the ``type`` value, never the class name."""
    _force_full_registration()

    divergent = {
        key: (cls.__name__, wire_type_value(cls))
        for key, cls in WIRE_TYPE_MAP.items()
        if key != wire_type_value(cls)
    }

    assert not divergent, (
        "WIRE_TYPE_MAP keys must equal the wire 'type' value their class "
        "emits (VM-01-007). Divergent entries "
        "{key: (class, type value)}: " + repr(divergent)
    )


def test_every_declared_wire_type_resolves() -> None:
    """Every declared ``type`` value resolves to *some* registered class.

    A class may legitimately not own its own ``type`` value — ``as_Person`` is
    shadowed by ``as_VultronPerson``, and ``as_VulnerabilityCaseStub`` declares
    itself an alias of ``as_VulnerabilityCase``. What must never happen is a
    ``type`` value the project emits that resolves to nothing.
    """
    _force_full_registration()

    unresolvable = {
        cls.__name__: wire_type_value(cls)
        for cls in _declared_type_wire_classes()
        if wire_type_value(cls) not in WIRE_TYPE_MAP
    }

    assert not unresolvable, (
        "These wire classes emit a 'type' value that WIRE_TYPE_MAP cannot "
        "resolve {class: type value}: " + repr(unresolvable)
    )


def test_declared_aliases_do_not_own_a_registry_key() -> None:
    """A class flagged an alias must not appear in ``WIRE_TYPE_MAP`` at all."""
    _force_full_registration()

    registered_aliases = {
        key: cls.__name__
        for key, cls in WIRE_TYPE_MAP.items()
        if is_wire_type_alias(cls)
    }

    assert not registered_aliases, (
        "A class declaring `_wire_type_alias = True` shares another class's "
        "wire 'type' value and must not hold a registry key of its own "
        "{key: class}: " + repr(registered_aliases)
    )


def _registrable_wire_classes() -> list[type[as_Base]]:
    """Return every wire class that passes the registration gate, deduplicated."""
    found: dict[type[as_Base], None] = {}

    def walk(cls: type[as_Base]) -> None:
        for sub in cls.__subclasses__():
            if (
                sub.__module__.startswith("vultron.wire.as2.vocab")
                and declares_registrable_type(sub)
                and not is_wire_type_alias(sub)
            ):
                found[sub] = None
            walk(sub)

    walk(as_Base)
    return list(found)


def test_no_unsanctioned_wire_type_collisions() -> None:
    """VM-01-007: exactly one class owns each ``type`` value.

    Without this, a new class that declares an existing value (say ``"Note"``)
    silently takes the key for the whole process, decided by import order, and
    every other ratchet still passes — the displaced class merely stops being
    what that value deserializes to.
    """
    _force_full_registration()

    claimants: dict[str, list[str]] = {}
    for cls in _registrable_wire_classes():
        claimants.setdefault(wire_type_value(cls), []).append(cls.__name__)

    collisions = {
        value: sorted(names)
        for value, names in claimants.items()
        if len(names) > 1 and value not in _SANCTIONED_SHADOWS
    }
    assert not collisions, (
        "These wire 'type' values are claimed by more than one class. Mark "
        "the non-owner `_wire_type_alias = True` (VM-01-007) {value: "
        "classes}: " + repr(collisions)
    )

    wrong_winner = {
        value: WIRE_TYPE_MAP[value].__name__
        for value, owner in _SANCTIONED_SHADOWS.items()
        if WIRE_TYPE_MAP[value].__name__ != owner
    }
    assert not wrong_winner, (
        "A sanctioned shadow lost its key to the class it should replace "
        "{value: actual owner}: " + repr(wrong_winner)
    )
