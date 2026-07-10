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

"""Main SqliteDataLayer class implementation."""

import logging
from typing import Any, Callable, cast

from pydantic import ValidationError
from sqlmodel import SQLModel

from vultron.adapters.driven.db_record import (
    Record,
    _AS_LIST_REF_FIELDS,
    _AS_OBJECT_REF_FIELDS,
    record_to_object,
)
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.semantic_registry import (
    find_matching_semantics,
    semantics_to_activity_class as _semantics_to_activity_class,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

from .schema import VultronObjectRecord
from .engine import make_engine
from . import crud, queries, queues

logger = logging.getLogger(__name__)


class SqliteDataLayer:
    """SQLite-backed implementation of the :class:`DataLayer` protocol."""

    def __init__(
        self,
        db_url: str = "sqlite:///:memory:",
        actor_id: str | None = None,
        enqueue_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = make_engine(db_url)
        self._actor_id = actor_id
        self._owns_engine: bool = True
        self._enqueue_callback: Callable[[str], None] | None = enqueue_callback
        SQLModel.metadata.create_all(self._engine)

    def close(self) -> None:
        """Dispose the underlying SQLAlchemy engine, releasing connections."""
        if self._owns_engine:
            self._engine.dispose()

    def clone_for_actor(self, actor_id: str) -> "SqliteDataLayer":
        """Return a new actor-scoped instance sharing this instance's engine.

        The concrete return type is ``SqliteDataLayer``, which satisfies the
        :class:`~vultron.core.ports.datalayer.ActorScopedDataLayer` Protocol
        structurally at both type-check and runtime (ARCH-13-003).

        The returned instance borrows the underlying engine (it does not own
        it) so its :meth:`close` / ``__del__`` will not dispose the engine.
        The original instance remains responsible for engine lifecycle.

        Args:
            actor_id: The actor URI to scope the new instance to.

        Returns:
            A :class:`SqliteDataLayer` scoped to *actor_id* (satisfies
            :class:`~vultron.core.ports.datalayer.ActorScopedDataLayer`)
            that reads and writes to the same database as this instance.
        """
        clone = SqliteDataLayer.__new__(SqliteDataLayer)
        clone._engine = self._engine
        clone._actor_id = actor_id
        clone._owns_engine = False
        clone._enqueue_callback = self._enqueue_callback
        return clone

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
        """Dispose engine on garbage collection to avoid ResourceWarning.

        Only disposes if this instance created (owns) the engine.  Borrowed
        engines (``_owns_engine = False``) must be disposed by their owner.
        """
        if not getattr(self, "_owns_engine", True):
            return
        try:
            self._engine.dispose()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scoped(self, stmt: Any) -> Any:
        """Apply actor-scoping WHERE clause when this DL has an actor_id."""
        if self._actor_id:
            return stmt.where(VultronObjectRecord.actor_id == self._actor_id)
        return stmt

    def _to_row(self, obj: PersistableModel) -> VultronObjectRecord:
        """Convert a domain object to a storage row."""
        rec = Record.from_obj(obj)
        return VultronObjectRecord(
            id_=rec.id_,
            type_=rec.type_,
            actor_id=self._actor_id,
            data=rec.data_,
        )

    def _from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
        """Convert a storage row back to a fully-typed domain object.

        Reconstruction is a three-step pipeline:

        1. ``record_to_object`` — vocabulary-based base-type reconstruction.
        2. ``_rehydrate_fields`` — expand dehydrated ``object_`` / ``target`` /
           ``origin`` / ``result`` / ``instrument`` ID strings back to typed
           Pydantic objects by reading them from the DataLayer.
        3. ``_coerce_to_semantic_class`` — pattern-match the rehydrated object
           against ``SEMANTICS_ACTIVITY_PATTERNS`` and, when a more specific
           Python class is known (e.g. ``RmSubmitReportActivity`` for
           ``as_Offer``), coerce via ``model_validate`` so that callers always
           receive the most precise type without manual coercion.
        """
        rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
        try:
            obj = cast(PersistableModel, record_to_object(rec))
        except (ValueError, ValidationError):
            return None
        if obj is None:
            return None
        obj = self._rehydrate_fields(obj)
        return self._coerce_to_semantic_class(obj)

    def _rehydrate_fields(self, obj: PersistableModel) -> PersistableModel:
        """Expand dehydrated object-reference fields back to typed objects.

        Fields listed in ``_AS_OBJECT_REF_FIELDS`` (``object_``, ``target``,
        ``origin``, ``result``, ``instrument``) are dehydrated to ID strings
        by the storage layer.  This method resolves each string ID via
        ``self.read()`` and replaces it with the full domain object.  If a
        referenced object is not found the string is kept and a DEBUG message
        is logged.
        """
        updates: dict[str, object] = {}
        for field_name in _AS_OBJECT_REF_FIELDS:
            value = getattr(obj, field_name, None)
            if not isinstance(value, str) or not value:
                continue
            nested = self.read(value)
            if nested is None:
                logger.debug(
                    "Could not rehydrate field %r with id %r on %r;"
                    " keeping string reference.",
                    field_name,
                    value,
                    type(obj).__name__,
                )
                continue
            updates[field_name] = nested
        if updates:
            obj = obj.model_copy(update=updates)
        return obj

    def hydrate(self, obj: PersistableModel) -> PersistableModel:
        """Deep-hydrate all reference fields in *obj*, including list fields.

        Extends :meth:`_rehydrate_fields` (which handles scalar object-ref
        fields such as ``object_``, ``target``, ``origin``) to also expand
        fields listed in ``_AS_LIST_REF_FIELDS`` (e.g. ``case_participants``),
        where each list item may be a bare ID string rather than a full domain
        object.

        Called by the outbox handler at delivery time so that bootstrap
        payloads (``Create``/``Announce`` activities whose ``object_`` is a
        ``VulnerabilityCase``) carry embedded participant objects that
        recipients can store in their own DataLayer.

        Args:
            obj: A fully-constructed domain object (Pydantic model) whose
                 list reference fields may still contain bare ID strings.

        Returns:
            A new model instance with all resolvable ID strings replaced by
            the corresponding domain objects.  Unresolvable IDs are left as
            strings and logged at DEBUG level.
        """
        obj = self._rehydrate_fields(obj)
        updates: dict[str, object] = {}
        for field_name in _AS_LIST_REF_FIELDS:
            items = getattr(obj, field_name, None)
            if not isinstance(items, list):
                continue
            expanded: list[Any] = []
            changed = False
            for item in items:
                if isinstance(item, str) and item:
                    resolved = self.read(item)
                    if resolved is not None:
                        expanded.append(resolved)
                        changed = True
                    else:
                        logger.warning(
                            "Could not hydrate list item %r in field %r"
                            " on %r; sending bare ID string to recipient"
                            " (participant may be missing from sender DataLayer).",
                            item,
                            field_name,
                            type(obj).__name__,
                        )
                        expanded.append(item)
                else:
                    expanded.append(item)
            if changed:
                updates[field_name] = expanded
        if updates:
            obj = obj.model_copy(update=updates)
        return obj

    def _coerce_to_semantic_class(
        self, obj: PersistableModel
    ) -> PersistableModel:
        """Coerce a base-vocabulary activity to its semantic subtype.

        After rehydration the object has correct field types but may still be
        typed as a base vocabulary class (e.g. ``as_Offer``).  This method
        uses :func:`find_matching_semantics` to identify the semantic intent
        and, when a more specific class is registered in the semantic registry,
        coerces via ``model_validate``.
        Coercion failures are logged as warnings and the original object is
        returned unchanged.
        """
        if not isinstance(obj, as_Activity):
            return obj

        from vultron.core.models.events import MessageSemantics

        semantics = find_matching_semantics(obj)
        if semantics == MessageSemantics.UNKNOWN:
            return obj

        activity_cls = _semantics_to_activity_class().get(semantics)
        if activity_cls is None or isinstance(obj, activity_cls):
            return obj

        try:
            return cast(
                PersistableModel,
                activity_cls.model_validate(
                    obj.model_dump(by_alias=True, serialize_as_any=True)
                ),
            )
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "Could not coerce %r to semantic class %r: %s",
                type(obj).__name__,
                activity_cls.__name__,
                exc,
            )
            return obj

    def _object_from_storage(
        self, stored_record: dict[str, Any]
    ) -> PersistableModel | None:
        """Reconstruct a domain object from a raw stored-record dict."""
        try:
            record = Record.model_validate(stored_record)
            return cast(PersistableModel, record_to_object(record))
        except (ValidationError, ValueError):
            pass

        raw_type = stored_record.get("type")
        if isinstance(raw_type, str):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(stored_record)
                )
            except KeyError:
                pass

        raw_type = stored_record.get("type_")
        raw_data = stored_record.get("data_")
        if isinstance(raw_type, str) and isinstance(raw_data, dict):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(raw_data)
                )
            except KeyError:
                pass

        return None

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
        """Return the open/closed state of a request/reply protocol pair.

        Two-pass scan of ``CaseLedgerEntry`` objects scoped to *case_id*:

        1. Locate the request entry whose ``event_type == request_event_type``
           **and** ``log_object_id == object_id``.
        2. Search for a reply entry whose ``event_type`` is in
           *reply_event_types*.

        Returns a :class:`~vultron.core.models.protocol_pair.ProtocolPair`
        with ``reply_object_id`` / ``reply_event_type`` populated when a reply
        is found (``is_closed()``), or ``None`` fields when not (``is_open()``).
        If no request entry is found, returns an open pair.

        .. note::
           ``CaseLedgerEntry`` has no structural field linking a reply to the
           specific request that triggered it (``in_reply_to`` chain-following
           is YAGNI per CLP-11-004).  This method is therefore most reliable
           when at most one open offer of a given ``request_event_type`` exists
           per case at a time, which is the expected protocol usage
           (ADR-0026/CM-16).
        """
        case_entries = [
            e
            for e in self.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case_id
        ]

        request_found = any(
            getattr(e, "event_type", None) == request_event_type
            and getattr(e, "log_object_id", None) == object_id
            for e in case_entries
        )

        reply_object_id: str | None = None
        reply_event_type_found: str | None = None

        if request_found:
            for entry in case_entries:
                entry_event_type = getattr(entry, "event_type", None)
                if entry_event_type in reply_event_types:
                    reply_object_id = getattr(entry, "log_object_id", None)
                    reply_event_type_found = entry_event_type
                    break

        return ProtocolPair(
            case_id=case_id,
            request_event_type=request_event_type,
            object_id=object_id,
            reply_event_types=reply_event_types,
            reply_object_id=reply_object_id,
            reply_event_type=reply_event_type_found,
        )

    def find_actor_by_short_id(self, short_id: str) -> PersistableModel | None:
        """Find an actor by the last path segment of its URI."""
        return queries.find_actor_by_short_id(self, short_id)

    def find_case_by_short_id(self, short_id: str) -> PersistableModel | None:
        """Find a case by its URL-safe surrogate key."""
        return queries.find_case_by_short_id(self, short_id)

    def find_case_by_report_id(
        self, report_id: str
    ) -> PersistableModel | None:
        """Find a ``VulnerabilityCase`` referencing the given report ID."""
        return queries.find_case_by_report_id(self, report_id)

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

    def outbox_list_for_actor(self, actor_id: str) -> list[str]:
        """Return all outbox activity IDs for *actor_id*, in insertion order."""
        return queues.outbox_list_for_actor(self, actor_id)

    def outbox_pop(self) -> str | None:
        """Remove and return the oldest activity ID from the outbox."""
        return queues.outbox_pop(self)

    def record_outbox_item(self, actor_id: str, activity_id: str) -> None:
        """Queue an outbox item for *actor_id* regardless of this DL's scope."""
        queues.record_outbox_item(self, actor_id, activity_id)
