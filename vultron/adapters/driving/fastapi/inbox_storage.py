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
from typing import cast

from pydantic import ValidationError

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.protocols import PersistableModel
from vultron.core.ports.datalayer import DataLayer, StorableRecord
from vultron.core.services.carried_embargo import store_carried_embargo
from vultron.errors import (
    VultronAlreadyExistsError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

# Same logger the helpers used under routers/actors/_inbox.py, so moving them
# does not move their records to a different handler.
logger = logging.getLogger("uvicorn.error")


def _store_nested_inbox_object(dl: DataLayer, activity: as_Activity) -> None:
    """Store the inline nested ``object_`` of an inbox activity.

    Stores the class the parser produced for the inline object, unchanged.
    ``parse_activity`` already resolves every inline dict to its most specific
    wire class and refuses the activity when that class's validation fails
    (MV-04-003), so the parsed object graph is the authority for what arrived
    in each slot (MV-11-005).  The raw request body is received evidence
    (VM-08-002), not a second source to parse from: re-validating an inline
    object from it would see again the unknown keys the parse edge set aside
    (MV-11-003), fail on a core class's ``extra="forbid"``, and store a less
    specific type in its place.  That is what the retired
    ``_reparse_as_specific_type`` did (#3922).

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

    typed_nested = cast(PersistableModel, nested)

    if isinstance(nested, VulnerabilityCase):
        # EMB-18-003: hold the embargo the case names before the case row is
        # written, and never pre-store a case naming one this store cannot
        # read — the dispatched handler then refuses it with nothing saved.
        try:
            store_carried_embargo(nested, dl)
        except (VultronNotFoundError, VultronValidationError) as exc:
            logger.warning(
                "Not pre-storing inline VulnerabilityCase %s from ingress: it"
                " names an active embargo this store cannot read"
                " (EMB-18-003): %s",
                getattr(nested, "id_", "<no id>"),
                exc,
            )
            return

    try:
        # Normalise case_participants to string IDs in the *serialised record*
        # before persisting so the stored VulnerabilityCase row carries only ID
        # refs (#2233 write-path).  The Python object is never mutated —
        # downstream BT nodes must see the original inline objects so they can
        # project them to core and create standalone DataLayer records.
        record: StorableRecord | PersistableModel = object_to_record(
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
        logger.exception(
            "Not pre-storing inline %s %s from ingress: it cannot be projected"
            " to the canonical core shape.",
            nested.type_,
            getattr(nested, "id_", "<no id>"),
        )
    except VultronAlreadyExistsError:
        logger.debug(
            "Inline object %s already exists in shared DL; skipping re-store.",
            getattr(nested, "id_", "<no id>"),
        )


def _store_inbox_activity(dl: DataLayer, activity: as_Activity) -> bool:
    """Store *activity*; return whether this call wrote it.

    ``False`` means a record under the same id was already held, so a later
    by-id read returns *that* record rather than this delivery.
    """
    try:
        dl.create(object_to_record(activity))
    except VultronAlreadyExistsError:
        logger.debug(
            "Activity %s already exists in shared DL; skipping re-store.",
            activity.id_,
        )
        return False
    return True
