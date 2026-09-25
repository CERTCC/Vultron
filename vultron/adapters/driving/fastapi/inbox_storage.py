#!/usr/bin/env python
"""Ingress storage for inbox activities and their inline objects.

Persists an inbound activity, and the domain object it carries inline, into
the receiving actor's DataLayer before the inbox pipeline dispatches it.
``FastAPIIngressAdapter`` in ``inbox_orchestration`` is the caller.

These helpers live outside ``routers/`` on purpose: the router package imports
``inbox_orchestration`` (for ``run_inbox_pipeline``), so orchestration
importing back into the router package made a cycle that broke any import of
``inbox_orchestration`` that ran first (#3705).
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging
from typing import Any, cast

from pydantic import ValidationError

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.errors import VultronAlreadyExistsError, VultronValidationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.base import as_Object
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

# Same logger the helpers used under routers/actors/_inbox.py, so moving them
# does not move their records to a different handler.
logger = logging.getLogger("uvicorn.error")


def _reparse_as_specific_type(
    nested: as_Object,
    raw_obj: dict[str, Any],
) -> PersistableModel:
    """Re-parse *raw_obj* with the correct specific vocabulary class.

    When the wire parser validates an inline object as the base ``as_Object``
    type, domain-specific fields are silently dropped.  This helper looks up
    the specific vocabulary class for ``nested.type_`` and re-parses
    *raw_obj* (the raw dict from the wire body) with it so all fields are
    preserved.

    Returns the re-parsed specific instance, or the original *nested* cast
    to ``PersistableModel`` when re-parsing fails or is unnecessary.
    """
    base: PersistableModel = cast(PersistableModel, nested)
    obj_type: str | None = nested.type_
    if obj_type is None:
        return base
    # Wire-only lookup (VM-06-008): this re-parses a sender's payload, so a
    # core-only ``type`` name must fall back to the base object rather than
    # persist a core class the sender named by coincidence (ISSUE-3565).
    try:
        specific_cls = find_in_vocabulary(obj_type)
    except KeyError:
        return base
    if isinstance(nested, specific_cls):
        return base
    try:
        result = cast(PersistableModel, specific_cls.model_validate(raw_obj))
        logger.debug(
            "Re-parsed inline '%s' as specific class %s.",
            obj_type,
            specific_cls.__name__,
        )
        return result
    except ValidationError:
        logger.debug(
            "Could not re-parse inline '%s' as %s; using base as_Object.",
            obj_type,
            specific_cls.__name__,
        )
        return base


def _store_nested_inbox_object(
    dl: DataLayer,
    activity: as_Activity,
    body: dict[str, Any] | None = None,
) -> None:
    """Store the inline nested ``object_`` of an inbox activity.

    When the wire parser parses an Announce or other transitive activity, the
    inline ``object_`` is validated as the base ``as_Object`` type, which
    silently drops domain-specific fields (``case_id``, ``event_type``, etc.).
    This function uses the raw request body to re-parse the nested object with
    the correct specific vocabulary class so that all fields are preserved.
    Without this, a subsequent DataLayer round-trip would fail Pydantic
    validation on the specific class (missing required fields), causing
    rehydration to return ``None`` and pattern matching to fall back to a
    less specific pattern (e.g. ``announce_vulnerability_case`` instead of
    ``announce_case_ledger_entry``).

    Ledger entries are exempt: per SYNC-13-002 a ``CaseLedgerEntry`` MUST NOT
    be written to the DataLayer by ingress/adapter code — only a participant's
    core ``PersistReceivedLogEntry`` step (or the CaseActor's authoritative
    append) may do so, because entry presence is the SYNC-12 evidence that the
    entry's domain effects were applied.  ``FastAPIIngressAdapter.rehydrate``
    carries the typed inline entry forward in-memory (SYNC-13-003), so no
    pre-store is needed for routing.

    Args:
        dl: The receiving actor's own DataLayer (ADR-0073).
        activity: The parsed AS2 activity whose ``object_`` to store.
        body: Optional raw JSON request body dict.  When present, used to
            re-parse the nested object with the correct specific class.
    """
    nested = getattr(activity, "object_", None)
    if nested is None or isinstance(nested, str):
        return
    if not (
        hasattr(nested, "id_")
        and hasattr(nested, "type_")
        and nested.type_ is not None
        and not nested.type_.startswith("as_")
    ):
        return
    # SYNC-13-002: never persist a CaseLedgerEntry from ingress. The ledger is
    # core-owned; PersistReceivedLogEntry is the sole writer of replica entries.
    if nested.type_ == "CaseLedgerEntry":
        logger.debug(
            "Not pre-storing inline CaseLedgerEntry %s from ingress"
            " (SYNC-13-002); core PersistReceivedLogEntry owns the write.",
            getattr(nested, "id_", "<no id>"),
        )
        return

    raw_obj = body.get("object") if body is not None else None
    typed_nested: PersistableModel = (
        _reparse_as_specific_type(nested, raw_obj)
        if isinstance(raw_obj, dict)
        else cast(PersistableModel, nested)
    )

    try:
        # Normalise case_participants to string IDs in the *serialised record*
        # before persisting so the stored VulnerabilityCase row carries only ID
        # refs (#2233 write-path).  The Python object is never mutated —
        # downstream BT nodes must see the original inline objects so they can
        # project them to core and create standalone DataLayer records.
        record: "StorableRecord | PersistableModel" = object_to_record(
            typed_nested
        )
        if (
            hasattr(typed_nested, "case_participants")
            and isinstance(record, dict)
            and isinstance(record.get("case_participants"), list)
        ):
            record["case_participants"] = [
                (
                    entry["id_"]
                    if isinstance(entry, dict) and "id_" in entry
                    else entry
                )
                for entry in record["case_participants"]
                if isinstance(entry, (str, dict))
            ]
        dl.create(record)
    except (VultronValidationError, ValidationError):
        # A shape/projection failure, NOT an "already exists" collision — the
        # object cannot be persisted in the canonical core shape at all
        # (issue #2232).  Under ``extra="forbid"`` (#2940) that can surface as a
        # bare Pydantic ``ValidationError`` as well as a core guard's error.
        # Swallowing this silently alongside the duplicate case left the row
        # absent and downstream nodes reporting a misleading "participant not
        # found", so it is logged loudly instead.
        logger.error(
            "Not pre-storing inline %s %s from ingress: it cannot be projected"
            " to the canonical core shape.",
            nested.type_,
            getattr(nested, "id_", "<no id>"),
            exc_info=True,
        )
    except VultronAlreadyExistsError:
        logger.debug(
            "Inline object %s already exists in shared DL; skipping re-store.",
            getattr(nested, "id_", "<no id>"),
        )


def _store_inbox_activity(dl: DataLayer, activity: as_Activity) -> None:
    try:
        dl.create(object_to_record(activity))
    except VultronAlreadyExistsError:
        logger.debug(
            "Activity %s already exists in shared DL; skipping re-store.",
            activity.id_,
        )
