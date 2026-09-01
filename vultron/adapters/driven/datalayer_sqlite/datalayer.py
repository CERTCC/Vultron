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

"""Main SqliteDataLayer class implementation.

One responsibility: be the ``DataLayer`` port's SQLite implementation — own the
actor's engine and its lifecycle, and route each protocol method to the
submodule that implements it.  The row ↔ object pipeline moved to
:mod:`.hydration` and ``find_protocol_pair``'s ledger scan to :mod:`.queries`
(CS-18-002); the private ``_from_row`` / ``_rehydrate_fields`` /
``_coerce_to_semantic_class`` methods remain as delegations because sibling
submodules and tests call them by those names.
"""

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from vultron.core.models.case import VulnerabilityCase

from sqlmodel import SQLModel

from vultron.adapters.outbox_dead_letter import OutboxDeadLetterEntry
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord

from .schema import VultronObjectRecord
from .engine import dispose_actor_engines, get_actor_engine
from . import crud, hydration, queries, queues

logger = logging.getLogger(__name__)


class SqliteDataLayer:
    """SQLite-backed implementation of the :class:`DataLayer` protocol."""

    def __init__(
        self,
        db_url: str = "sqlite:///:memory:",
        *,
        actor_id: str,
        enqueue_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Open the store belonging to *actor_id*.

        Args:
            db_url: The configured SQLAlchemy URL **template**.  Each actor
                gets its own store derived from it (ADR-0073), so this names a
                family of stores rather than one location.
            actor_id: The actor's canonical URI.  Required and keyword-only:
                there is no unscoped DataLayer, so there is no such thing as a
                store that is not some actor's own (CM-01-001).
            enqueue_callback: Optional callback invoked with ``actor_id`` when
                an item is appended to this actor's outbox.

        Raises:
            ValueError: If *actor_id* is empty or yields no usable slug.
        """
        self._db_url = db_url
        self._actor_id = actor_id
        self._engine = get_actor_engine(db_url, actor_id)
        self._enqueue_callback: Callable[[str], None] | None = enqueue_callback
        SQLModel.metadata.create_all(self._engine)

    @property
    def actor_id(self) -> str:
        """The canonical URI of the actor whose store this is.

        Public because callers legitimately need to ask *whose* store they
        hold: under ADR-0073 a store is never anonymous, so "which actor" is
        part of a DataLayer's identity rather than an implementation detail.
        :class:`~vultron.core.behaviors.bridge.BTBridge` uses it to keep the
        blackboard's ``datalayer`` and ``actor_id`` in agreement.
        """
        return self._actor_id

    @property
    def db_url(self) -> str:
        """The storage-deployment **template** this store was built from.

        Not the actor's own resolved URL — :func:`actor_db_url` derives that per
        actor — but the template every actor in the same deployment shares.  It
        is the deployment's identity the way :attr:`actor_id` is the store's, and
        callers that need to reach a *sibling* actor's store have to pass it back
        to :func:`get_datalayer` to land in the same deployment: the cache is
        keyed on ``(actor_id, db_url)``, so guessing wrong yields a valid,
        empty, and entirely separate database rather than an error.
        """
        return self._db_url

    def close(self) -> None:
        """Dispose this actor's engine, releasing its SQLite connections.

        Engines are cached per ``(db_url, actor_id)`` so that two instances for
        the same actor share one store; disposal therefore goes through the
        cache rather than the local reference.
        """
        dispose_actor_engines(self._db_url, self._actor_id)

    def clone_for_actor(self, actor_id: str) -> "SqliteDataLayer":
        """Return a DataLayer for *actor_id*, backed by that actor's own store.

        Under ADR-0073 this opens a **different** store rather than applying a
        filter to a shared one, so nothing the returned instance writes can be
        read through this instance, and vice versa.  Cloning for the actor this
        instance already serves returns an equivalent instance sharing the same
        cached engine.

        Args:
            actor_id: The canonical URI of the actor whose store to open.

        Returns:
            A :class:`SqliteDataLayer` on *actor_id*'s own store.
        """
        return SqliteDataLayer(
            self._db_url,
            actor_id=actor_id,
            enqueue_callback=self._enqueue_callback,
        )

    def set_enqueue_callback(
        self, callback: Callable[[str], None] | None
    ) -> None:
        """Set the callback invoked when an item is added to the outbox.

        Used by :class:`~vultron.adapters.driving.fastapi.outbox_monitor\
.OutboxMonitor` to register an event-driven wakeup notification.  Pass
        ``None`` to clear a previously registered callback.

        Args:
            callback: Callable that receives ``actor_id`` when an outbox
                item is enqueued, or ``None`` to disable notification.
        """
        self._enqueue_callback = callback

    def __enter__(self) -> "SqliteDataLayer":
        """Support ``with SqliteDataLayer(...) as dl:`` usage."""
        return self

    def __exit__(self, *_: object) -> None:
        """Close the data layer when exiting the ``with`` block."""
        self.close()

    def __del__(self) -> None:
        """Do not dispose on garbage collection.

        Engines are cached per ``(db_url, actor_id)`` and shared by every
        instance serving that actor, so disposing here would close a store that
        other live instances are still using.  Disposal is explicit, via
        :meth:`close` or ``reset_datalayer``.
        """

    # ------------------------------------------------------------------
    # Internal helpers - delegate to the hydration submodule
    # ------------------------------------------------------------------

    def _to_row(self, obj: PersistableModel) -> VultronObjectRecord:
        """Convert a domain object to a storage row."""
        return hydration.to_row(obj)

    def _from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
        """Convert a storage row back to a fully-typed domain object."""
        return hydration.from_row(self, row)

    def _rehydrate_fields(self, obj: PersistableModel) -> PersistableModel:
        """Expand dehydrated scalar object-reference fields to typed objects."""
        return hydration.rehydrate_fields(self, obj)

    def hydrate(self, obj: PersistableModel) -> PersistableModel:
        """Deep-hydrate all reference fields in *obj*, including list fields."""
        return hydration.hydrate(self, obj)

    def _coerce_to_semantic_class(
        self, obj: PersistableModel
    ) -> PersistableModel:
        """Coerce a base-vocabulary activity to its semantic subtype."""
        return hydration.coerce_to_semantic_class(obj)

    def _object_from_storage(
        self, stored_record: dict[str, Any]
    ) -> PersistableModel | None:
        """Reconstruct a domain object from a raw stored-record dict."""
        return hydration.object_from_storage(stored_record)

    # ------------------------------------------------------------------
    # DataLayer Protocol implementation - delegate to submodules
    # ------------------------------------------------------------------

    def create(self, record: "StorableRecord | PersistableModel") -> None:
        """Insert a new record; raises ``ValueError`` if it already exists."""
        crud.create(self, record)

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None:
        """Read an object by ID across all actor-scoped rows."""
        return crud.read(self, object_id, raise_on_missing)

    def read_case(
        self, case_id: str, raise_on_missing: bool = False
    ) -> "VulnerabilityCase | None":
        """Read a VulnerabilityCase by ID; returns None when not found."""
        from vultron.core.models.case import VulnerabilityCase as _VC

        result = self.read(case_id, raise_on_missing=raise_on_missing)
        if result is not None and not isinstance(result, _VC):
            if raise_on_missing:
                raise ValueError(
                    f"Object at {case_id!r} is not a VulnerabilityCase"
                )
            return None
        return result  # type: ignore[return-value]

    def get(
        self, table: str | None = None, id_: str | None = None
    ) -> PersistableModel | dict[str, Any] | None:
        """Retrieve a record by type and/or ID."""
        return crud.get(self, table, id_)

    def get_all(self, table: str) -> list[dict[str, Any]]:
        """Return all raw data dicts for a given object type."""
        return crud.get_all(self, table)

    def update(self, id_: str, record: StorableRecord) -> bool:
        """Update an existing record by ID."""
        return crud.update(self, id_, record)

    def save(self, obj: PersistableModel) -> None:
        """Persist a domain object, overwriting any existing record."""
        crud.save(self, obj)

    def save_many(self, objs: list[PersistableModel]) -> None:
        """Persist multiple domain objects in a single atomic transaction.

        All writes commit together; a failure in any serialisation rolls back
        the entire set so no partial state reaches storage (CM-21-004).
        """
        crud.save_many(self, objs)

    def delete(self, table: str, id_: str) -> bool:
        """Delete a record by type and ID."""
        return crud.delete(self, table, id_)

    def clear_table(self, table: str) -> None:
        """Remove all records of a given object type."""
        crud.clear_table(self, table)

    def clear_all(self) -> None:
        """Remove all object records (and queue entries) for this actor scope."""
        crud.clear_all(self)

    def ping(self) -> bool:
        """Probe storage; returns ``True`` when the backend is accessible."""
        return queries.ping(self)

    def exists(self, table: str, id_: str) -> bool:
        """Check whether a record exists."""
        return queries.exists(self, table, id_)

    def all(
        self, table: str | None = None
    ) -> list[StorableRecord] | dict[str, PersistableModel]:
        """Return all records, optionally filtered by type."""
        return queries.all(self, table)

    def count_all(self) -> dict[str, int]:
        """Return a dict mapping type → record count."""
        return queries.count_all(self)

    def by_type(self, type_: str) -> dict[str, dict[str, Any]]:
        """Return all records of a given type as a ``{id_: data_}`` dict."""
        return queries.by_type(self, type_)

    def list_objects(self, type_key: str) -> list[PersistableModel]:
        """Return fully rehydrated domain objects of the given type."""
        return queries.list_objects(self, type_key)

    def find_protocol_pair(
        self,
        case_id: str,
        request_event_type: str,
        object_id: str,
        reply_event_types: frozenset[str],
    ) -> ProtocolPair:
        """Return the open/closed state of a request/reply protocol pair."""
        return queries.find_protocol_pair(
            self, case_id, request_event_type, object_id, reply_event_types
        )

    def find_actor_by_short_id(self, short_id: str) -> PersistableModel | None:
        """Find an actor by the last path segment of its URI."""
        return queries.find_actor_by_short_id(self, short_id)

    def find_case_by_short_id(
        self, short_id: str
    ) -> "VulnerabilityCase | None":
        """Find a case by its URL-safe surrogate key."""
        from vultron.core.models.case import VulnerabilityCase as _VC

        result = queries.find_case_by_short_id(self, short_id)
        return result if isinstance(result, _VC) else None

    def find_case_by_report_id(
        self, report_id: str
    ) -> "VulnerabilityCase | None":
        """Find a ``VulnerabilityCase`` referencing the given report ID."""
        from vultron.core.models.case import VulnerabilityCase as _VC

        result = queries.find_case_by_report_id(self, report_id)
        return result if isinstance(result, _VC) else None

    # ------------------------------------------------------------------
    # Inbox / Outbox queue helpers - delegate to submodule
    # ------------------------------------------------------------------

    def inbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's inbox queue."""
        queues.inbox_append(self, activity_id)

    def inbox_list(self) -> list[str]:
        """Return all activity IDs in this actor's inbox, in insertion order."""
        return queues.inbox_list(self)

    def inbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from the inbox."""
        return queues.inbox_pop(self)

    def outbox_append(self, activity_id: str) -> None:
        """Append an activity ID to this actor's outbox queue."""
        queues.outbox_append(self, activity_id)

    def outbox_list(self) -> list[str]:
        """Return all activity IDs in this actor's outbox, in insertion order."""
        return queues.outbox_list(self)

    def outbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from the outbox."""
        return queues.outbox_pop(self)

    # ------------------------------------------------------------------
    # Per-activity outbox attempt counter (OX-13-001)
    # ------------------------------------------------------------------

    def get_outbox_attempt_count(self, activity_id: str) -> int:
        """Return this actor's cumulative delivery attempt count for *activity_id*."""
        return queues.get_outbox_attempt_count(self, activity_id)

    def set_outbox_attempt_count(self, activity_id: str, count: int) -> None:
        """Upsert this actor's delivery attempt count for *activity_id*."""
        queues.set_outbox_attempt_count(self, activity_id, count)

    def clear_outbox_attempt_count(self, activity_id: str) -> None:
        """Remove this actor's attempt count entry for *activity_id*."""
        queues.clear_outbox_attempt_count(self, activity_id)

    # ------------------------------------------------------------------
    # Dead-letter store (OX-13-002, OX-13-004)
    # ------------------------------------------------------------------

    def dead_letter_append(
        self,
        activity_id: str,
        reason: str,
        total_attempts: int,
        failed_recipients: list[str],
    ) -> None:
        """Write an exhausted outbox activity to this actor's dead-letter store."""
        queues.dead_letter_append(
            self, activity_id, reason, total_attempts, failed_recipients
        )

    def dead_letter_list(self) -> list[OutboxDeadLetterEntry]:
        """Return this actor's dead-letter entries (OX-13-004)."""
        return queues.dead_letter_list(self)
