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

"""What a replica slot of ``AnnounceLogEntryReceivedBT`` reaches.

Shared by the copy-only ratchets (CM-23-016, ADR-0124):
``test_embargo_replica_slots_copy.py`` for the embargo register and consent
rows, ``test_participant_replica_slots_copy.py`` for participant records,
participant statuses and case statuses.  Both ask the same question — which
names does a slot's code use, its own classes and every codebase helper and
core model method it reaches — so the walk lives here once (CS-22-001).
"""

import ast
import functools
import importlib
import inspect
import pkgutil
import sys
import textwrap
import types
from collections.abc import Iterable
from typing import Any, cast

import vultron.core.models as core_models
from test.architecture import _corpus
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)


def _names_used(obj: object) -> set[str]:
    """Every bare name and attribute name *obj*'s source uses."""
    source = inspect.getsource(cast(Any, obj))
    tree = _corpus.parse_inline(textwrap.dedent(source))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _own_classes(slot: type) -> list[type]:
    return [c for c in slot.__mro__ if c.__module__.startswith("vultron.")]


#: The core model writes behind the one apply function, deliberately not
#: followed (see :func:`_functions_reached`).
_UNWALKED_MODEL_WRITES = frozenset(
    {
        "VulnerabilityCase.apply_embargo_register_step",
        "VulnerabilityCase.add_participant",
    }
)


def _function_of(attr: object) -> types.FunctionType | None:
    """The function a class attribute runs, unwrapping a descriptor."""
    if isinstance(attr, (staticmethod, classmethod)):
        attr = attr.__func__
    elif isinstance(attr, property):
        attr = attr.fget
    return attr if isinstance(attr, types.FunctionType) else None


@functools.cache
def _model_methods() -> dict[str, tuple[types.FunctionType, ...]]:
    """Every method a ``vultron.core.models`` class defines, by name.

    Static and class methods and property getters count too.  A call is
    matched to every method of its name, whatever the receiver, so a name
    two models share follows both: the walk over-follows rather than misses.
    """
    methods: dict[str, list[types.FunctionType]] = {}
    for info in pkgutil.walk_packages(
        core_models.__path__, f"{core_models.__name__}."
    ):
        module = importlib.import_module(info.name)
        for cls in vars(module).values():
            if not inspect.isclass(cls) or cls.__module__ != module.__name__:
                continue
            for name, attr in vars(cls).items():
                function = _function_of(attr)
                if (
                    function is not None
                    # Methods compiled elsewhere (dataclass- or
                    # pydantic-generated dunders) have no source here to walk.
                    and function.__code__.co_filename == module.__file__
                    and function.__qualname__ not in _UNWALKED_MODEL_WRITES
                ):
                    methods.setdefault(name, []).append(function)
    return {name: tuple(found) for name, found in methods.items()}


def _functions_reached(
    cls: type, *, follow_methods: bool = True
) -> dict[str, set[str]]:
    """Each codebase function *cls* reaches, and the names it uses.

    Starts from every class in *cls*'s MRO that this codebase defines.
    """
    return _reach(_own_classes(cls), follow_methods=follow_methods)


def _reach(
    roots: Iterable[object], *, follow_methods: bool = True
) -> dict[str, set[str]]:
    """Each codebase function *roots* reach by name, and the names it uses.

    Follows every name a class body or function body uses that resolves, in
    its module, to a module-level function this codebase defines, and every
    attribute name that a core model method bears
    (:func:`_model_methods`, unless *follow_methods* is false), and so on
    from there.  So a slot calling
    ``record.sign_embargo(...)`` reaches the PEC transition inside it.
    Classes are not followed: a slot's own classes are walked by MRO, and a
    lifecycle-running node class is forbidden by name.

    Blind spots, by construction: a function reached as ``module.func`` (an
    attribute that names no model method is not resolved); a method of a
    class outside ``vultron.core.models``, or of a class nested inside
    another; a ``functools.cached_property`` (not unwrapped by
    :func:`_function_of`); and a lifecycle-running node class outside
    ``embargo/nodes`` (:func:`_lifecycle_nodes`).  None of the nested or
    cached kinds exists in ``vultron.core.models`` today.

    Two model writes behind the one apply function stay unwalked, on
    purpose (:data:`_UNWALKED_MODEL_WRITES`):
    ``VulnerabilityCase.apply_embargo_register_step`` gives an *inline*
    participant its ``UNINVITED`` rows so the register assignment validates,
    and ``VulnerabilityCase.add_participant`` gives a seated record a row
    for each register entry it lacks.  A carried record already holds every
    row, so on a replica neither writes one; the rebuild-from-ledger check
    (``test/support/ledger_rebuild.py``) compares every record whole and
    would fail if one did.
    """
    return {
        f"{function.__module__}.{function.__qualname__}": names
        for function, names in _walk(roots, follow_methods=follow_methods)
    }


def _reached_functions(
    cls: type, *, follow_methods: bool = True
) -> list[types.FunctionType]:
    """The codebase functions *cls* reaches, as objects (see :func:`_reach`)."""
    return [
        function
        for function, _ in _walk(
            _own_classes(cls), follow_methods=follow_methods
        )
    ]


def _walk(
    roots: Iterable[object], *, follow_methods: bool
) -> list[tuple[types.FunctionType, set[str]]]:
    """Each function :func:`_reach` reaches, with the names its source uses."""
    reached: list[tuple[types.FunctionType, set[str]]] = []
    pending: list[object] = list(roots)
    seen: set[int] = set()
    while pending:
        obj = pending.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        names = _names_used(obj)
        if isinstance(obj, types.FunctionType):
            reached.append((obj, names))
        module_globals = vars(sys.modules[cast(Any, obj).__module__])
        for name in names:
            value = module_globals.get(name)
            if isinstance(
                value, types.FunctionType
            ) and value.__module__.startswith("vultron."):
                pending.append(value)
            if follow_methods:
                pending.extend(_model_methods().get(name, ()))
    return reached


def _tree_slot_classes() -> set[type]:
    """Every apply node class ``AnnounceLogEntryReceivedBT`` runs."""
    return {
        type(node)
        for node in create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        ).iterate()
        if type(node).__name__.startswith("Apply")
    }
