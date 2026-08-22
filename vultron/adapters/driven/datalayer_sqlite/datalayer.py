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
from typing import Any, Callable, cast, get_args

from pydantic import BaseModel, ValidationError
from sqlmodel import SQLModel

from vultron.adapters.outbox_dead_letter import OutboxDeadLetterEntry
from vultron.adapters.driven.db_record import (
    Record,
    _AS_LIST_REF_FIELDS,
    _AS_OBJECT_REF_FIELDS,
    record_to_object,
)
from vultron.core.models import find_in_core_vocabulary
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import StorableRecord
from vultron.errors import VultronValidationError
from vultron.semantic_registry import (
    find_matching_semantics,
    semantics_to_activity_class as _semantics_to_activity_class,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

from .schema import VultronObjectRecord
from .engine import dispose_actor_engines, get_actor_engine
from . import crud, queries, queues

logger = logging.getLogger(__name__)


def _field_admits_object(obj: Any, field_name: str) -> bool:
    """True when *field_name* on *obj* can legitimately hold a nested object.

    ``_AS_OBJECT_REF_FIELDS`` names fields that are *usually* references, but the
    same name can be declared as a plain URI on a particular model (for instance
    ``as_CaseProposal.target``, required by CP-01-005 to be the case-actor's URI).
    Expanding such a field yields a model that violates its own annotation —
    ``model_copy`` does not validate, so the breach surfaces later and elsewhere.

    Unknown fields are treated as expandable, preserving the previous behaviour
    for models that do not declare the field at all.
    """
    # ``PersistableModel`` is a Protocol, so ``model_fields`` is reached
    # defensively rather than assumed.
    model_fields = getattr(type(obj), "model_fields", None)
    field = model_fields.get(field_name) if model_fields else None
    if field is None:
        return True
    annotation = field.annotation
    if annotation is None:
        return True
    candidates = list(get_args(annotation)) or [annotation]
    for candidate in candidates:
        # Unwrap one more level for containers such as ``Ref[as_Foo]``.
        parts = list(get_args(candidate)) or [candidate]
        for part in parts:
            if isinstance(part, type) and issubclass(part, BaseModel):
                return True
    return False


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
                gets its own store derived from it (ADR-0070), so this names a
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
        hold: under ADR-0070 a store is never anonymous, so "which actor" is
        part of a DataLayer's identity rather than an implementation detail.
        :class:`~vultron.core.behaviors.bridge.BTBridge` uses it to keep the
        blackboard's ``datalayer`` and ``actor_id`` in agreement.
        """
        return self._actor_id

    def close(self) -> None:
        """Dispose this actor's engine, releasing its SQLite connections.

        Engines are cached per ``(db_url, actor_id)`` so that two instances for
        the same actor share one store; disposal therefore goes through the
        cache rather than the local reference.
        """
        dispose_actor_engines(self._db_url, self._actor_id)

    def clone_for_actor(self, actor_id: str) -> "SqliteDataLayer":
        """Return a DataLayer for *actor_id*, backed by that actor's own store.

        Under ADR-0070 this opens a **different** store rather than applying a
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
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_row(self, obj: PersistableModel) -> VultronObjectRecord:
        """Convert a domain object to a storage row.

        No ``actor_id`` column is written: the store *is* the actor's, so
        stamping ownership on each row would be redundant (ADR-0070).
        """
        rec = Record.from_obj(obj)
        return VultronObjectRecord(
            id_=rec.id_,
            type_=rec.type_,
            data=rec.data_,
        )

    def _from_row(self, row: VultronObjectRecord) -> PersistableModel | None:
        """Convert a storage row back to a fully-typed domain object.

        Reconstruction is a three-step pipeline:

        1. Core-vocabulary lookup — if the stored ``type_`` has a registered
           core counterpart in ``CORE_VOCABULARY``, reconstruct via
           ``find_in_core_vocabulary(type_).model_validate(data)`` (DL-05-001,
           DL-05-002).  This ensures domain entities round-trip as core objects
           rather than wire vocabulary types.  For persisted AS2 Activity types
           (no core counterpart), falls back to the wire vocabulary path below.
        2. ``record_to_object`` — wire-vocabulary base-type reconstruction
           (fallback for AS2 Activities and any type not in ``CORE_VOCABULARY``).
        3. ``_rehydrate_fields`` — expand dehydrated ``object_`` / ``target`` /
           ``origin`` / ``result`` / ``instrument`` ID strings back to typed
           Pydantic objects by reading them from the DataLayer.
        4. ``_coerce_to_semantic_class`` — pattern-match the rehydrated object
           against ``SEMANTICS_ACTIVITY_PATTERNS`` and, when a more specific
           Python class is known (e.g. ``RmSubmitReportActivity`` for
           ``as_Offer``), coerce via ``model_validate`` so that callers always
           receive the most precise type without manual coercion.
        """
        wire_obj: PersistableModel | None
        try:
            core_cls = find_in_core_vocabulary(row.type_)
        except KeyError:
            # No core counterpart (AS2 Activity types) → wire vocabulary path.
            wire_obj = self._wire_object_from_row(row)
            if wire_obj is None:
                return None
            obj = wire_obj
        else:
            try:
                obj = cast(PersistableModel, core_cls.model_validate(row.data))
            except ValidationError as exc:
                # Stored data came from a wire object whose schema differs from
                # the core class (e.g. as_EmbargoEvent lacks context).  Return
                # the wire object un-projected: that is the long-standing
                # behaviour the KNOWN_WIRE_ESCAPES ratchet in
                # test/architecture/test_dl_read_returns_core_objects.py
                # measures, and projecting here would dehydrate inline nested
                # objects that callers of these rows still expect inline.
                logger.debug(
                    "_from_row: core_cls.model_validate failed for type %r"
                    " (row %r): %s; using wire fallback",
                    row.type_,
                    row.id_,
                    exc,
                )
                wire_obj = self._wire_object_from_row(row)
                if wire_obj is None:
                    return None
                obj = wire_obj
            except VultronValidationError as exc:
                # A core type's own shape guard rejected the row — e.g.
                # CaseParticipant's wire-spelled-key guard (#2232).  It is not a
                # ValueError subclass, so without naming it here it would escape
                # this ladder entirely instead of falling back like every other
                # shape mismatch (DL-05-002).
                #
                # Unlike the ValidationError case above, the row *is* a
                # wire-spelled copy of a core type, so project it: handing back
                # a wire object makes every core-typed caller fail (resolve_case
                # raises "Expected VulnerabilityCase, got as_VulnerabilityCase").
                logger.debug(
                    "_from_row: VultronValidationError for type %r (row %r):"
                    " %s; projecting wire row to core",
                    row.type_,
                    row.id_,
                    exc,
                )
                wire_obj = self._wire_object_from_row(row)
                if wire_obj is None:
                    return None
                obj = self._project_wire_row_to_core(row, wire_obj, exc)
        if obj is None:
            return None
        obj = self._rehydrate_fields(obj)
        return self._coerce_to_semantic_class(obj)

    def _wire_object_from_row(
        self, row: VultronObjectRecord
    ) -> PersistableModel | None:
        """Reconstruct *row* through the wire vocabulary, or ``None``."""
        rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
        try:
            return cast(PersistableModel, record_to_object(rec))
        except (ValueError, ValidationError, VultronValidationError):
            return None

    def _project_wire_row_to_core(
        self,
        row: VultronObjectRecord,
        wire_obj: PersistableModel,
        core_exc: Exception,
    ) -> PersistableModel:
        """Project a wire-vocabulary fallback back to its core counterpart.

        ``_from_row`` reaches this only when the row's ``type_`` *has* a core
        counterpart but the stored data does not validate against it, so the
        wire class was used instead.  Handing that wire object to core callers
        is what DL-05-001/DL-05-002 forbid: a wire ``as_VulnerabilityCase``
        reaching ``resolve_case`` raises "Expected VulnerabilityCase, got
        as_VulnerabilityCase" rather than reading the case (issue #2232).

        ``to_core()`` is the same projection the write path applies in
        ``_normalize_to_core`` — the persistence-boundary half of ADR-0062,
        applied on the way out as well as on the way in.  Wire types are looser
        than core types, so a row that fails core validation directly can still
        project cleanly: ``to_core()`` maps flat wire spellings onto the nested
        core shape instead of dropping them.

        When the projection also fails, *wire_obj* is returned unchanged — that
        is the pre-#2232 behaviour for these rows, and degrading it to ``None``
        would turn a wrongly-typed read into a missing-object read.  Both
        outcomes are logged: a silent fallback here is what made this class of
        shape bug so hard to trace.
        """
        to_core = getattr(wire_obj, "to_core", None)
        if to_core is None:
            logger.warning(
                "Row %r (type %r) failed core validation (%s) and its wire"
                " fallback %s has no to_core() projection; returning the wire"
                " object (DL-05-002, issue #2232).",
                row.id_,
                row.type_,
                core_exc,
                type(wire_obj).__name__,
            )
            return wire_obj
        try:
            projected = cast(PersistableModel, to_core())
        except (
            ValidationError,
            VultronValidationError,
            ValueError,
            TypeError,
        ) as exc:
            logger.warning(
                "Row %r (type %r) failed core validation (%s) and projecting"
                " its wire fallback %s to core also failed (%s); returning the"
                " wire object (issue #2232).",
                row.id_,
                row.type_,
                core_exc,
                type(wire_obj).__name__,
                exc,
            )
            return wire_obj
        logger.debug(
            "Row %r (type %r) failed core validation (%s); recovered the core"
            " shape by projecting the wire fallback %s via to_core()"
            " (issue #2232).",
            row.id_,
            row.type_,
            core_exc,
            type(wire_obj).__name__,
        )
        return projected

    def _rehydrate_fields(self, obj: PersistableModel) -> PersistableModel:
        """Expand dehydrated object-reference fields back to typed objects.

        Fields listed in ``_AS_OBJECT_REF_FIELDS`` (``object_``, ``target``,
        ``origin``, ``result``, ``instrument``) are dehydrated to ID strings
        by the storage layer.  This method resolves each string ID via
        ``self.read()`` and replaces it with the full domain object.  If a
        referenced object is not found the string is kept and a DEBUG message
        is logged.

        When a field holds an inline ``PersistableModel`` (kept inline by
        ``_KEEP_INLINE_NESTED_TYPES`` rather than dehydrated to a bare ID),
        this method recurses into it so that the nested object's own reference
        fields are expanded too.  Without this recursion an inline Offer's
        ``target`` would remain a bare string URI and break semantic dispatch
        that relies on the resolved type (e.g. Organisation ≠ CaseParticipant
        for ``OfferCaseManagerRolePattern`` vs ``OfferCaseOwnershipTransfer``).

        Expansion respects the field's **declared type**.  ``_AS_OBJECT_REF_FIELDS``
        is a flat list applied to every object, but some models declare one of
        those names as a plain URI rather than a reference — ``as_CaseProposal
        .target`` is required by CP-01-005 to be the case-actor's URI, not an
        inline actor.  Expanding it produced a model whose ``target`` was a dict,
        which ``model_copy`` accepts silently (it does not validate) and which then
        failed the next ``model_validate`` far away, in outbound delivery: the
        proposal could not be re-hydrated, the recipient saw a dehydrated object,
        matched no semantics, and never sent its ``Accept``. Nothing raised at the
        point of damage.
        """
        updates: dict[str, object] = {}
        for field_name in _AS_OBJECT_REF_FIELDS:
            value = getattr(obj, field_name, None)
            if value is None:
                continue
            if isinstance(value, str):
                if not value:
                    continue
                if not _field_admits_object(obj, field_name):
                    logger.debug(
                        "Field %r on %r is declared as a plain URI; leaving its"
                        " reference unexpanded.",
                        field_name,
                        type(obj).__name__,
                    )
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
            elif isinstance(value, BaseModel):
                rehydrated = self._rehydrate_fields(
                    cast(PersistableModel, value)
                )
                if rehydrated is not value:
                    updates[field_name] = rehydrated
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
        except (ValidationError, VultronValidationError, TypeError) as exc:
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
        except (ValidationError, VultronValidationError, ValueError):
            pass

        raw_type = stored_record.get("type")
        if isinstance(raw_type, str):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(stored_record)
                )
            except (KeyError, ValidationError, VultronValidationError):
                pass

        raw_type = stored_record.get("type_")
        raw_data = stored_record.get("data_")
        if isinstance(raw_type, str) and isinstance(raw_data, dict):
            try:
                vocab_cls = find_in_vocabulary(raw_type)
                return cast(
                    PersistableModel, vocab_cls.model_validate(raw_data)
                )
            except (KeyError, ValidationError, VultronValidationError):
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
            request_found=request_found,
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
