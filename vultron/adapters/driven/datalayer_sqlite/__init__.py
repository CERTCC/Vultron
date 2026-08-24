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

"""SQLite/SQLModel-backed activity store (driven adapter).

Concrete implementation of the ``vultron.core.ports.datalayer.DataLayer``
port for persisting and fetching ActivityStreams objects using SQLite via
SQLModel and SQLAlchemy.

The database URL is read from :func:`vultron.config.get_config` so that it
respects the unified configuration system (``VULTRON_DATABASE__DB_URL`` env
var or ``database.db_url`` in ``config.yaml``).  Pass an explicit ``db_url``
argument to :func:`get_datalayer` to override the config value, e.g. for
``"sqlite:///:memory:"`` in tests.
"""

import logging

from .datalayer import SqliteDataLayer
from .engine import dispose_actor_engines
from .schema import VultronObjectRecord, QueueEntry

__all__ = [
    "SqliteDataLayer",
    "VultronObjectRecord",
    "QueueEntry",
    "dispose_actor_engines",
    "get_datalayer",
    "get_all_actor_datalayers",
    "reset_datalayer",
]


# ---------------------------------------------------------------------------
# Module-level factory / instance management
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

#: Cached instances keyed by ``(actor_id, resolved db_url)``.
#:
#: The URL is part of the key because it selects a *different store*.  Keyed on
#: ``actor_id`` alone, a test that asked for ``db_url="sqlite:///:memory:"``
#: after any earlier call for the same actor got the previously-cached on-disk
#: instance back, silently, and then wrote its fixtures into the real database.
_actor_instances: dict[tuple[str, str], SqliteDataLayer] = {}


def get_datalayer(actor_id: str, db_url: str | None = None) -> SqliteDataLayer:
    """Factory that returns (or creates) the DataLayer for *actor_id*.

    Every actor gets its own store (ADR-0072).  There is no shared or
    "admin" DataLayer: an unscoped view would be able to read across actors,
    which CM-01-001 forbids.  Code that needs a node-wide picture must
    enumerate hosted actors and fan out.

    In tests, use dependency injection to override this function, or pass an
    explicit ``db_url="sqlite:///:memory:"`` argument.

    Args:
        actor_id: The canonical URI of the actor whose DataLayer to return.
        db_url: SQLAlchemy connection URL **template**.  Defaults to
            ``get_config().database.db_url`` (``"sqlite:///vultron.db"``
            unless overridden via ``VULTRON_DATABASE__DB_URL`` or
            ``config.yaml``).  The per-actor store is derived from it.

    Returns:
        :class:`SqliteDataLayer` for *actor_id*.

    Raises:
        ValueError: If *actor_id* is empty.
    """
    from vultron.config import get_config

    if not actor_id:
        raise ValueError(
            "get_datalayer requires a canonical actor URI; there is no "
            "unscoped DataLayer (ADR-0072, CM-01-001)"
        )
    _url = db_url if db_url is not None else get_config().database.db_url
    key = (actor_id, _url)
    if key not in _actor_instances:
        _actor_instances[key] = SqliteDataLayer(db_url=_url, actor_id=actor_id)
    return _actor_instances[key]


def get_all_actor_datalayers() -> dict[str, SqliteDataLayer]:
    """Return a snapshot of all registered actor-scoped DataLayer instances.

    Used by :class:`~vultron.adapters.driving.fastapi.outbox_monitor.OutboxMonitor`
    to iterate over all actors' outboxes without exposing the mutable
    module-level cache directly.

    Returns:
        An ``actor_id → SqliteDataLayer`` mapping for every actor that has
        called :func:`get_datalayer` with an ``actor_id``.

    The cache is keyed by ``(actor_id, db_url)``, so an actor could in
    principle appear under two URLs.  That does not happen in a running node —
    every call resolves the same configured URL — and it would mean two stores
    for one actor, which ADR-0072 forbids.  The last one registered wins and
    the collision is logged rather than passed over.
    """
    collapsed: dict[str, SqliteDataLayer] = {}
    for (actor_id, url), instance in _actor_instances.items():
        if actor_id in collapsed:
            logger.warning(
                "Actor %r has cached DataLayers under more than one db_url;"
                " using %r. Two stores for one actor contradicts ADR-0072.",
                actor_id,
                url,
            )
        collapsed[actor_id] = instance
    return collapsed


def reset_datalayer(actor_id: str | None = None) -> None:
    """Reset one or all cached DataLayer instances.

    Disposes the underlying SQLAlchemy engine for each cached instance that
    is being cleared, then removes it from the module-level cache.  The next
    call to :func:`get_datalayer` will create a new instance with a fresh,
    empty in-memory database.

    Engines are disposed *before* their references are dropped so that
    ``sqlite3.Connection`` objects are closed explicitly.  Without this,
    Python's cyclic GC may finalise the connection objects in an order that
    emits ``ResourceWarning`` during a later, unrelated test.

    .. note::
        Callers that created a ``SqliteDataLayer`` instance *directly* (not via
        :func:`get_datalayer`) are responsible for calling :meth:`close` on
        those instances themselves; ``reset_datalayer`` cannot track them.

    Args:
        actor_id: If provided, resets only the instance for that actor.
            If ``None``, resets every per-actor instance.
    """
    global _actor_instances

    instances_to_close: list[SqliteDataLayer] = []

    if actor_id is None:
        instances_to_close.extend(_actor_instances.values())
        _actor_instances = {}
    else:
        # Every ``db_url`` this actor was cached under, not just the configured
        # one: a reset that left one behind would hand the stale store back.
        for key in [k for k in _actor_instances if k[0] == actor_id]:
            instances_to_close.append(_actor_instances.pop(key))

    for inst in instances_to_close:
        inst.close()

    if actor_id is None:
        # Engines are cached independently of the instance registry (a
        # DataLayer built directly, not via get_datalayer, still caches one),
        # so a full reset must clear the engine cache too or an in-memory
        # store would survive into the next test.
        dispose_actor_engines()
