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

"""Which core class a dumped object's ``type`` value names.

A core object's dump carries its AS2 ``type`` value, not its class name, and
the two differ for a class such as ``VultronNote`` (``"Note"``).  Reading a
dump back, whether a stored row (DL-05-006) or an object embedded in an
activity's slot (#6305), needs the one class that presents that value.
"""

import importlib
import pkgutil
from functools import cache

from pydantic import BaseModel

from vultron.core.models.registry import (
    CORE_VOCABULARY,
    declared_type_value,
    find_in_core_vocabulary,
)


@cache
def _register_every_core_model() -> None:
    """Import every module under ``vultron.core.models`` once.

    A core class registers when its module is imported, so without this the
    answer would depend on what the process happened to import: a dumped
    ``Create(Note)`` read in a process that never imported the note module
    would read its note back as a bare ``CoreObject``, with no error.
    """
    models_pkg = importlib.import_module("vultron.core.models")
    for module in pkgutil.walk_packages(
        models_pkg.__path__, models_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)


class _TypeValueIndexCache:
    """The ``type``-value → core class index, with the registry it was built from.

    Rebuilt when a core class registers or replaces another after the first
    read, since registration happens at class definition. Keyed on the
    classes, not the count: re-registering a name swaps the class without
    changing the size.
    """

    __slots__ = ("index", "registered")

    def __init__(self) -> None:
        self.registered: tuple[type[BaseModel], ...] = ()
        self.index: dict[str, type[BaseModel] | None] = {}


_TYPE_VALUE_INDEX = _TypeValueIndexCache()


def _core_classes_by_type_value() -> dict[str, type[BaseModel] | None]:
    """Map each declared ``type`` value to its core class, ``None`` if shared.

    Built once per registry state rather than per read: every activity row
    misses the class-name lookup and would otherwise rescan the registry.
    """
    registered = tuple(CORE_VOCABULARY.values())
    if _TYPE_VALUE_INDEX.registered == registered:
        return _TYPE_VALUE_INDEX.index
    index: dict[str, type[BaseModel] | None] = {}
    for cls in registered:
        if getattr(cls, "type_names_no_class", False):
            continue
        value = declared_type_value(cls)
        if value is None:
            continue
        index[value] = None if value in index else cls
    # Index before key, so a reader that matches the new key never gets the
    # stale index.
    _TYPE_VALUE_INDEX.index = index
    _TYPE_VALUE_INDEX.registered = registered
    return index


def core_class_for_type(type_: str) -> type[BaseModel]:
    """Return the core class an object dumped under *type_* reads back as.

    ``CORE_VOCABULARY`` is keyed by class name, but a dump carries the
    object's ``type`` value, and the two differ for a type such as
    ``VultronNote`` (dumped as ``"Note"``). So after the class-name lookup
    this falls back to a match on declared ``type`` values over
    ``CORE_VOCABULARY`` (DL-05-006) — without it a stored note read back as
    the unpaired wire ``as_Note`` (ISSUE-3647). A dump does not record which
    branch wrote it, so an inbound wire ``as_Note`` persisted verbatim — and
    the note embedded in a stored ``Add(Note)`` — reads back as
    ``VultronNote`` too.

    The match leaves two kinds of class out, and both are deliberate:

    - A core *activity* (``VultronOffer`` dumps as ``"Offer"``), or any class
      that sets ``type_names_no_class``. Persisted
      activities stay on the wire path, which the DL-05-004 ratchet exempts;
      moving them is the activity read-back migration (#1506), not this lookup.
    - A class whose ``type`` value another core class also presents. The dump
      cannot say which it was, so neither is guessed.

    Raises:
        KeyError: If no core class reads back dumps of *type_*.
    """
    _register_every_core_model()
    try:
        return find_in_core_vocabulary(type_)
    except KeyError:
        pass
    cls = _core_classes_by_type_value().get(type_)
    if cls is None:
        raise KeyError(f"No unique core class for type {type_!r}")
    return cls
