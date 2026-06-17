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

from .datalayer import SqliteDataLayer
from .schema import VultronObjectRecord, QueueEntry

__all__ = [
    "SqliteDataLayer",
    "VultronObjectRecord",
    "QueueEntry",
    "get_datalayer",
    "get_shared_dl",
    "get_all_actor_datalayers",
    "reset_datalayer",
]


# ---------------------------------------------------------------------------
# Module-level factory / singleton management
# ---------------------------------------------------------------------------

_shared_instance: SqliteDataLayer | None = None
_actor_instances: dict[str, SqliteDataLayer] = {}


def get_datalayer(
    actor_id: str | None = None, db_url: str | None = None
) -> SqliteDataLayer:
    """Factory that returns (or creates) a :class:`SqliteDataLayer` instance.

    When ``actor_id`` is provided, returns (or creates) an actor-scoped
    instance whose rows are filtered by ``actor_id``.  Different actors get
    fully isolated DataLayer views backed by the same SQLite file.

    When ``actor_id`` is ``None``, returns (or creates) a shared/admin
    instance with no actor filtering.  Admin endpoints and health checks use
    this form.

    In tests, use dependency injection to override this function, or pass an
    explicit ``db_url="sqlite:///:memory:"`` argument.

    Args:
        actor_id: The actor whose scoped DataLayer to return.  ``None`` for
            the shared/admin DataLayer.
        db_url: SQLAlchemy connection URL.  Defaults to
            ``get_config().database.db_url`` (``"sqlite:///vultron.db"``
            unless overridden via ``VULTRON_DATABASE__DB_URL`` or
            ``config.yaml``).

    Returns:
        :class:`SqliteDataLayer` — actor-scoped or shared instance.
    """
    from vultron.config import get_config

    global _shared_instance
    _url = db_url if db_url is not None else get_config().database.db_url
    if actor_id is None:
        if _shared_instance is None:
            _shared_instance = SqliteDataLayer(db_url=_url)
        return _shared_instance
    if actor_id not in _actor_instances:
        # Ensure the shared instance exists so we can clone from it.
        # Cloning shares the underlying engine, which is critical for
        # in-memory SQLite (each Engine gets its own isolated database).
        if _shared_instance is None:
            _shared_instance = SqliteDataLayer(db_url=_url)
        _actor_instances[actor_id] = _shared_instance.clone_for_actor(actor_id)
    return _actor_instances[actor_id]


def get_shared_dl() -> "SqliteDataLayer":
    """FastAPI dependency: always returns the shared (non-actor-scoped) DataLayer.

    Use this function in ``Depends()`` instead of a local ``_shared_dl``
    wrapper.  Override via ``app.dependency_overrides[get_shared_dl]`` in
    tests to inject an isolated in-memory DataLayer per application instance.
    """
    return get_datalayer()


def get_all_actor_datalayers() -> dict[str, SqliteDataLayer]:
    """Return a snapshot of all registered actor-scoped DataLayer instances.

    Used by :class:`~vultron.adapters.driving.fastapi.outbox_monitor.OutboxMonitor`
    to iterate over all actors' outboxes without exposing the mutable
    module-level cache directly.

    Returns:
        A shallow copy of the ``actor_id → SqliteDataLayer`` mapping for
        every actor that has called :func:`get_datalayer` with an
        ``actor_id``.
    """
    return dict(_actor_instances)


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
            If ``None``, resets all instances (shared + all per-actor).
    """
    global _shared_instance, _actor_instances

    instances_to_close: list[SqliteDataLayer] = []

    if actor_id is None:
        if _shared_instance is not None:
            instances_to_close.append(_shared_instance)
        instances_to_close.extend(_actor_instances.values())
        _shared_instance = None
        _actor_instances = {}
    else:
        if actor_id in _actor_instances:
            instances_to_close.append(_actor_instances.pop(actor_id))

    for inst in instances_to_close:
        inst.close()
