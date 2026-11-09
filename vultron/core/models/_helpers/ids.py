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

"""The one object id minter (OID-01-004), its id source, and the id reader.

The minter, :func:`new_object_id`, draws each UUID from the installed id
source (OID-01-011, ADR-0185).  The installed source is
:func:`system_id_source` until a run that needs repeatable ids replaces it for
a block with :func:`install_id_source`.  Nothing else may replace the draw
(OID-01-012): a patch of the ``uuid`` module's draw reaches every library that
draws from it, py_trees included.  Two runs still patch it, as listed
exemptions, until #6116 and #6117 move them to the scoped install.

The port lives here, beside the minter, and not in ``vultron.core.ports``,
because the wire layer's docs-example generator supplies a source and the wire
layer may import only ``vultron.core.models`` and ``vultron.core.states``
(ARCH-22-001).
"""

import threading
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    Protocol,
)

from vultron.errors import VultronIdSourceInstalledError

URN_UUID_PREFIX = "urn:uuid:"
"""The scheme and namespace every default minted object id starts with."""


class IdSource(Protocol):
    """The port the minter draws its UUIDs from (ADR-0185).

    One operation: calling the source returns the next version-4 UUID.  A
    source returns a different UUID on every call within one run; a
    reproducible run's source returns the same sequence from run to run.
    """

    def __call__(self) -> uuid.UUID: ...


def system_id_source() -> uuid.UUID:
    """Return a fresh random version-4 UUID: the system id source.

    The one function in ``vultron/`` that draws a random UUID for an object id
    (OID-01-004, OID-01-012), and the source every run uses unless it installs
    another with :func:`install_id_source`.
    """
    return uuid.uuid4()


@dataclass
class _IdSourceSlot:
    """The process-wide slot holding the source :func:`new_object_id` draws from.

    Holds :func:`system_id_source` except inside :func:`install_id_source`.
    The lock serializes installs, not draws: a draw reads ``source`` once.
    A dataclass, so it has no hand-written ``__init__`` for a scan that follows
    core-model methods by name to reach into the system source.
    """

    source: IdSource = system_id_source
    installed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


_SLOT = _IdSourceSlot()


@contextmanager
def install_id_source(source: IdSource) -> Iterator[IdSource]:
    """Make *source* the minter's id source for the block, then restore it.

    For a run that needs repeatable ids (a scenario recording, the docs
    example generator); production installs nothing, and ``create_app()``
    installs nothing either (ARCH-16-001).  The install is process-wide: every
    thread that mints while the block runs draws from *source*.

    The previous source comes back when the block ends, also when it raises.
    Yields *source*, so a caller may bind it with ``as``.

    Raises:
        VultronIdSourceInstalledError: another install is active.  Two
            reproducible runs in one block would take each other's ids, and
            nobody would see it.
    """
    with _SLOT.lock:
        if _SLOT.installed:
            raise VultronIdSourceInstalledError(
                "an id source is already installed; a reproducible run's "
                "install does not nest inside another"
            )
        _SLOT.installed = True
        previous = _SLOT.source
        _SLOT.source = source
    try:
        yield source
    finally:
        with _SLOT.lock:
            _SLOT.source = previous
            _SLOT.installed = False


def new_object_id(prefix: str | None = None) -> str:
    """Return a new, unique, full-URI object id: the one id minter (OID-01-004).

    Core models use it as their ``id_`` default factory, and the wire layer's
    ``generate_new_id`` is the same function, so every minted id has one form
    whichever layer mints it.  By default the id is ``urn:uuid:`` followed by
    the next version-4 UUID of the installed id source (OID-01-011; see
    :func:`install_id_source`), a valid AS2 identifier that needs no server
    configuration (OID-01-001).  When *prefix* is given the UUID is appended
    to it after a ``/``, which yields HTTPS-style ids such as
    ``https://example.org/reports/{uuid}``; the caller owns *prefix*, which
    must itself be a full URI for the result to be one.

    An id *derived* from what an activity answers is not minted; it comes from
    :func:`vultron.core.models.activity_ids.derived_activity_id`.
    """
    minted = str(_SLOT.source())
    if prefix is None:
        return f"{URN_UUID_PREFIX}{minted}"
    return f"{prefix}/{minted}"


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``id_`` attribute, returns ``obj.id_``.
    - If *obj* is a mapping (an inline object as stored, or as a received
      activity's read-only view hands it out), returns its ``id_`` or ``id``
      string, so an inline case is named by its URI rather than by the
      ``str()`` of the whole mapping.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    id_ = obj.get("id_") or obj.get("id") if isinstance(obj, Mapping) else None
    id_ = id_ or getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)
