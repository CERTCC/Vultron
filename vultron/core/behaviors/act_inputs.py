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

"""A tree's declared per-act inputs, and how the runners seed them (ADR-0207).

Three pieces, used by every tree factory and both runners:

1. **The declaration** (BT-25-006).  A factory states the per-act keys
   (:mod:`vultron.core.behaviors.act_keys`) its tree needs with
   :func:`declare_inputs`, and for each one where its value comes from:
   :attr:`KeySource.SEEDED` — the runner copies it from the act's event or
   trigger request — or :attr:`KeySource.PUBLISHED` — one lookup node in the
   tree finds it (BT-25-009).  The declaration rides on the node the factory
   returns, so a factory that composes another's subtree inherits the
   subtree's declaration; :func:`tree_inputs` collects them all.
2. **The seeding declaration** (BT-25-007).  For each received event type
   and trigger request type, :func:`seeding_declaration` maps vocabulary
   keys onto the type's attributes.  By default a key is seeded from the
   attribute of the same name, so ``CaseTriggerRequest.case_id`` and
   ``AddNoteToCaseReceivedEvent.case_id`` seed ``/case_id`` with no
   declaration of their own; :func:`declare_seeds` adds a key the type
   carries under another name, or withholds one whose same-named attribute
   means something else.  Subclasses inherit their bases' entries.
3. **The seeding** (BT-25-007, BT-25-008, BT-25-011).  Before the first tick,
   both runners call :func:`seed_act_inputs`, which checks that every
   declared key has exactly one source and returns the seeded values for the
   run's blackboard.  A missing value or a second source is a wiring fault,
   so it raises :class:`~vultron.errors.VultronWiringError` naming the key,
   and no node ticks.

Seeded values are passed to ``BTBridge.execute_with_setup`` as context keys,
which the bridge restores when the run ends (BT-17-007).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

import py_trees

from vultron.core.behaviors.act_keys import (
    ACT_KEYS,
    SENDER_ID,
    ActKey,
    require_act_key,
)
from vultron.core.models.events.base import VultronEvent
from vultron.errors import VultronWiringError

__all__ = [
    "KeySource",
    "PublishesActKeys",
    "TreeInputs",
    "act_key_bindings",
    "declare_inputs",
    "declare_seeds",
    "declared_inputs",
    "published_act_keys",
    "seed_act_inputs",
    "seeding_declaration",
    "tree_inputs",
]


class KeySource(StrEnum):
    """Where a declared per-act key gets its value in a tree (BT-25-011)."""

    #: The runner copies it from the act's event or trigger request
    #: (BT-25-007).
    SEEDED = "seeded"
    #: One lookup node in the tree publishes it (BT-25-009).
    PUBLISHED = "published"


@dataclass(frozen=True)
class TreeInputs:
    """The per-act keys a tree declares, each with its one source.

    Attributes:
        sources: Each declared key and where its value comes from.
    """

    sources: Mapping[ActKey, KeySource] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def seeded(self) -> frozenset[ActKey]:
        """The keys the runner seeds."""
        return self._with(KeySource.SEEDED)

    @property
    def published(self) -> frozenset[ActKey]:
        """The keys a node of the tree publishes."""
        return self._with(KeySource.PUBLISHED)

    def _with(self, source: KeySource) -> frozenset[ActKey]:
        return frozenset(k for k, s in self.sources.items() if s is source)

    def merged(self, other: TreeInputs, *, where: str) -> TreeInputs:
        """These declarations and *other*'s together.

        Raises:
            VultronWiringError: A key is declared with both sources
                (BT-25-011); *where* names the tree in the message.
        """
        sources = dict(self.sources)
        for key, source in other.sources.items():
            if sources.setdefault(key, source) is not source:
                raise VultronWiringError(
                    f"{where}: '{key.path}' is declared both seeded by the"
                    " runner and published by a node; a key has one source"
                    " in a tree (BT-25-011)"
                )
        return TreeInputs(MappingProxyType(sources))


#: The attribute a declaration rides on.  Read only through this module.
_INPUTS_ATTR = "_vultron_act_inputs"


def declare_inputs[NodeT: py_trees.behaviour.Behaviour](
    tree: NodeT,
    *,
    seeded: Iterable[ActKey] = (),
    published: Iterable[ActKey] = (),
) -> NodeT:
    """Declare the per-act keys *tree* needs and return *tree* (BT-25-006).

    A factory calls it on the node it returns.  Calling it again on the same
    node adds to that node's declaration.

    Args:
        tree: The tree (or subtree) the factory built.
        seeded: Keys the runner seeds from the act (BT-25-007).
        published: Keys one lookup node of the tree publishes (BT-25-009).

    Raises:
        VultronWiringError: A key is given both sources (BT-25-011).
        TypeError: A key is not an :class:`ActKey` of the vocabulary.
    """
    declaration = declared_inputs(tree)
    for keys, source in (
        (seeded, KeySource.SEEDED),
        (published, KeySource.PUBLISHED),
    ):
        declaration = declaration.merged(
            TreeInputs(
                MappingProxyType(
                    {require_act_key(key, tree.name): source for key in keys}
                )
            ),
            where=tree.name,
        )
    setattr(tree, _INPUTS_ATTR, declaration)
    return tree


def declared_inputs(node: py_trees.behaviour.Behaviour) -> TreeInputs:
    """The declaration made on *node* itself, ignoring its descendants."""
    declaration = getattr(node, _INPUTS_ATTR, None)
    return declaration if isinstance(declaration, TreeInputs) else TreeInputs()


def tree_inputs(root: py_trees.behaviour.Behaviour) -> TreeInputs:
    """Every declaration made on *root* or any node below it.

    Raises:
        VultronWiringError: Two declarations give one key different sources
            (BT-25-011).
    """
    inputs = TreeInputs()
    for node in root.iterate():
        inputs = inputs.merged(declared_inputs(node), where=root.name)
    return inputs


# --- Which nodes publish a key ------------------------------------------------


@runtime_checkable
class PublishesActKeys(Protocol):
    """A node that writes per-act keys by a means other than an output port.

    A seeder that writes a key for its child's tick (such as
    :class:`~vultron.core.behaviors.act_key_scope.ActKeyScope`) implements
    it, so :func:`seed_act_inputs` counts it as the key's source.
    """

    def published_act_keys(self) -> frozenset[ActKey]:
        """The per-act keys this node writes."""
        ...


def act_key_bindings(node: object) -> dict[str, str]:
    """The absolute keys *node*'s ports are bound to, by port name.

    Read without setting the node up, from the merge of the two hooks that
    ``setup()`` passes to ``setup_ports()``: ``bound_port_remappings()`` of
    :class:`~vultron.core.behaviors.helpers.ports_base.PortRemappingHooks`
    (BTND-03-010, BTND-03-019).  Only absolute (``/``-prefixed) targets are
    returned; a node without the hooks binds nothing.
    """
    method = getattr(node, "bound_port_remappings", None)
    remaps = method() if callable(method) else None
    if not isinstance(remaps, Mapping):
        return {}
    return {
        port: target
        for port, target in remaps.items()
        if isinstance(target, str) and target.startswith("/")
    }


def published_act_keys(node: object) -> frozenset[ActKey]:
    """The per-act keys *node* writes: its bound output ports, or its own say.

    A :class:`PublishesActKeys` node answers for itself; any other node
    publishes the vocabulary keys its ``OUTPUT_PORTS`` are bound to.
    """
    if isinstance(node, PublishesActKeys):
        return node.published_act_keys()
    outputs = getattr(type(node), "OUTPUT_PORTS", {})
    return frozenset(
        key
        for port, target in act_key_bindings(node).items()
        if port in outputs
        and (key := ACT_KEYS.get(target.removeprefix("/"))) is not None
    )


def _publishers(
    root: py_trees.behaviour.Behaviour,
) -> dict[ActKey, list[str]]:
    """Each per-act key some node of *root* publishes, with those nodes."""
    found: dict[ActKey, list[str]] = {}
    for node in root.iterate():
        for key in published_act_keys(node):
            found.setdefault(key, []).append(node.name)
    return found


# --- Which attribute of an act seeds a key ------------------------------------

#: Explicit seeding entries, by act type: the attribute a key is seeded
#: from, or ``None`` to withhold a key the default would seed.
_EXPLICIT_SEEDS: dict[type, dict[ActKey, str | None]] = {}


def declare_seeds(act_type: type, seeds: Mapping[ActKey, str | None]) -> None:
    """Add explicit entries to *act_type*'s seeding declaration (BT-25-007).

    Subclasses of *act_type* inherit them, and a subclass's own entry wins.

    Args:
        act_type: A received event type or trigger request type.
        seeds: Each key and the attribute of *act_type* it is seeded from,
            or ``None`` to withhold a key whose same-named attribute means
            something else.

    Raises:
        ValueError: A named attribute does not exist on *act_type*.
    """
    for key, attribute in seeds.items():
        if attribute is not None and not _has_attribute(act_type, attribute):
            raise ValueError(
                f"{act_type.__name__} has no attribute {attribute!r} to seed"
                f" '{key.path}' from"
            )
    _EXPLICIT_SEEDS.setdefault(act_type, {}).update(seeds)


def _has_attribute(act_type: type, attribute: str) -> bool:
    """Whether instances of *act_type* have *attribute* (field or property)."""
    fields = getattr(act_type, "model_fields", None)
    if isinstance(fields, Mapping) and attribute in fields:
        return True
    return hasattr(act_type, attribute)


def seeding_declaration(act_type: type) -> Mapping[ActKey, str]:
    """The attribute of *act_type* each per-act key is seeded from.

    Every vocabulary key that names an attribute of *act_type* is seeded
    from it; then the explicit entries of :func:`declare_seeds` along the
    MRO, base first, add or withhold keys.
    """
    seeds: dict[ActKey, str | None] = {
        key: key.name
        for key in ACT_KEYS.values()
        if _has_attribute(act_type, key.name)
    }
    for klass in reversed(act_type.__mro__):
        seeds.update(_EXPLICIT_SEEDS.get(klass, {}))
    return MappingProxyType(
        {key: attr for key, attr in seeds.items() if attr is not None}
    )


#: A received event's ``actor_id`` is its sender; the vocabulary names the
#: sender ``sender_id``, never ``actor_id``, which is the executing actor.
declare_seeds(VultronEvent, {SENDER_ID: "actor_id"})


# --- Seeding a run ------------------------------------------------------------


def _seed_value(
    act: object, key: ActKey, attribute: str, where: str
) -> object:
    """Read *key*'s value off *act*, or raise naming the key (BT-25-008)."""
    act_name = type(act).__name__
    try:
        value = getattr(act, attribute)
    except (AttributeError, ValueError, TypeError) as exc:
        raise VultronWiringError(
            f"{where}: declared input '{key.path}' could not be read from"
            f" {act_name}.{attribute}: {exc} (BT-25-008)"
        ) from exc
    # An empty string is no value either ("if present, then non-empty",
    # CS-08-002).
    if value is None or value == "":
        raise VultronWiringError(
            f"{where}: declared input '{key.path}' has no value: this"
            f" {act_name} carries no {attribute} (BT-25-008)"
        )
    if not key.admits(value):
        raise VultronWiringError(
            f"{where}: declared input '{key.path}' got a"
            f" {type(value).__name__} from {act_name}.{attribute}, not"
            f" {key.value_type!r} (BTND-03-022)"
        )
    return value


def seed_act_inputs(
    tree: py_trees.behaviour.Behaviour,
    act: object,
    *,
    context: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Check *tree*'s declared inputs and return the values to seed.

    Called by both runners after the tree is built and before its first
    tick.  For each key *tree* declares (:func:`tree_inputs`):

    - a seeded key must be read off *act* through its type's
      :func:`seeding_declaration`, have a value of the key's type, and have
      no node of the tree publishing it (BT-25-007, BT-25-008, BT-25-011);
    - a published key must have exactly one publishing node (BT-25-008,
      BT-25-011);
    - neither may also be passed by the caller in *context*, which would be
      a second source (BT-25-011).

    Args:
        tree: The built tree, before any tick.
        act: The received event or trigger request the tree runs for.
        context: The further keys the caller places on the run.

    Returns:
        ``{key name: value}`` for every seeded key, for the run's blackboard.

    Raises:
        VultronWiringError: A declared key has no value, no source, or more
            than one source; the message names the key.
    """
    where = tree.name
    inputs = tree_inputs(tree)
    if not inputs.sources:
        return {}
    publishers = _publishers(tree)
    passed = frozenset(context or {})
    declaration = seeding_declaration(type(act))
    # ``Any``, not ``object``: the values are the keys' own types, and they
    # go straight into ``execute_with_setup(**context_data: Any)``.
    seeds: dict[str, Any] = {}
    for key, source in sorted(inputs.sources.items(), key=lambda i: i[0].name):
        if key.name in passed:
            raise VultronWiringError(
                f"{where}: declared input '{key.path}' is also passed by the"
                " caller; a key has one source in a tree (BT-25-011)"
            )
        nodes = publishers.get(key, [])
        if source is KeySource.PUBLISHED:
            if not nodes:
                raise VultronWiringError(
                    f"{where}: declared input '{key.path}' is published by no"
                    " node of the tree (BT-25-008)"
                )
            if len(nodes) > 1:
                raise VultronWiringError(
                    f"{where}: declared input '{key.path}' is published by"
                    f" {len(nodes)} nodes ({', '.join(nodes)}); a key has one"
                    " source in a tree (BT-25-011)"
                )
            continue
        if nodes:
            raise VultronWiringError(
                f"{where}: declared input '{key.path}' is seeded by the"
                f" runner and also published by {', '.join(nodes)}; a key"
                " has one source in a tree (BT-25-011)"
            )
        attribute = declaration.get(key)
        if attribute is None:
            raise VultronWiringError(
                f"{where}: declared input '{key.path}' has no value: no"
                f" attribute of {type(act).__name__} seeds it (BT-25-008)"
            )
        seeds[key.name] = _seed_value(act, key, attribute, where)
    return seeds
