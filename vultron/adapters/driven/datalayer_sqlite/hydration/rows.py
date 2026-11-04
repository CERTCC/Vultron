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

"""The row <-> domain-object entry points: :func:`to_row` and :func:`from_row`."""

import logging
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from vultron.adapters.driven.datalayer_sqlite.hydration.coercion import (
    coerce_to_semantic_class,
    rehydrate_fields,
)
from vultron.adapters.driven.datalayer_sqlite.hydration.row_types import (
    WIRE_ROW_FAILURES,
    core_class_for_row_type,
    project_wire_row_to_core,
    wire_object_from_row,
)
from vultron.adapters.driven.db_record import (
    STORED_ROW_CONTEXT,
    Record,
)
from vultron.core.models.protocols import PersistableModel
from vultron.errors import VultronValidationError

from ..schema import VultronObjectRecord

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.
    from ..datalayer import SqliteDataLayer


logger = logging.getLogger(__name__)


def to_row(obj: PersistableModel) -> VultronObjectRecord:
    """Convert a domain object to a storage row.

    No ``actor_id`` column is written: the store *is* the actor's, so
    stamping ownership on each row would be redundant (ADR-0073).
    """
    rec = Record.from_obj(obj)
    return VultronObjectRecord(
        id_=rec.id_,
        type_=rec.type_,
        data=rec.data_,
    )


def from_row(
    dl: "SqliteDataLayer", row: VultronObjectRecord
) -> PersistableModel | None:
    """Convert a storage row back to a fully-typed domain object.

    Reconstruction is a three-step pipeline:

    1. Core-vocabulary lookup — if the stored ``type_`` has a registered
       core counterpart in ``CORE_VOCABULARY`` (by class name or by ``type``
       value, :func:`core_class_for_row_type`), reconstruct via
       ``core_cls.model_validate(data)`` (DL-05-001, DL-05-002, DL-05-006).
       This ensures domain entities round-trip as core objects rather than
       wire vocabulary types.  For persisted AS2 Activity types
       (no core counterpart), falls back to the wire vocabulary path below.
    2. ``record_to_object`` — wire-vocabulary base-type reconstruction
       (fallback for AS2 Activities and any type not in ``CORE_VOCABULARY``).
    3. :func:`rehydrate_fields` — expand dehydrated ``object_`` / ``target`` /
       ``origin`` / ``result`` / ``instrument`` ID strings back to typed
       Pydantic objects by reading them from the DataLayer.
    4. :func:`coerce_to_semantic_class` — pattern-match the rehydrated object
       against ``SEMANTIC_REGISTRY`` and, when a more specific
       Python class is known (e.g. ``RmSubmitReportActivity`` for
       ``as_Offer``), coerce via ``model_validate`` so that callers always
       receive the most precise type without manual coercion.
    """
    try:
        core_cls = core_class_for_row_type(row.type_)
    except KeyError:
        # No core counterpart (AS2 Activity types, CoreRecord bookkeeping
        # rows) → wire vocabulary path.
        try:
            obj = wire_object_from_row(row)
        except WIRE_ROW_FAILURES as exc:
            # dl.read() reports the row absent; say why, or an operator sees
            # only "not found" — e.g. a record stored under a field name a
            # later rename retired, whose refusal names the store reset (#4128).
            logger.warning(
                "Row %r (type %r) failed validation (%s); reading it as absent.",
                row.id_,
                row.type_,
                exc,
            )
            return None
    else:
        try:
            obj = cast(
                PersistableModel,
                core_cls.model_validate(row.data, context=STORED_ROW_CONTEXT),
            )
        except (ValidationError, VultronValidationError) as exc:
            # The row's stored shape does not validate against the core class.
            # Under extra="forbid" (ARCH-12-003, #2940) this is the sole
            # shape-mismatch signal, raised by Pydantic here rather than by the
            # retired per-class shape guard, so it must attempt the wire→core
            # projection: handing back a wire object makes every core-typed
            # caller fail (``resolve_case`` raises "Expected VulnerabilityCase,
            # got as_VulnerabilityCase").  ``project_wire_row_to_core`` falls
            # back to the un-projected wire object when the type has no working
            # ``to_core()`` — the residual KNOWN_WIRE_ESCAPES actor types
            # (DL-05-002, DL-05-004).
            #
            # Be precise about what actually trips this branch: an *unknown* key,
            # i.e. a camelCase-only name such as ``participantStatuses``.  A flat
            # ``rm_state``/``rmState`` does **not** — it is an AliasChoice on the
            # dimension field, so it is interpreted rather than dropped, and such
            # a row validates straight through as core without ever reaching the
            # projection (#2288/#2289 remove those aliases).
            logger.debug(
                "from_row: core_cls.model_validate failed for type %r"
                " (row %r): %s; attempting wire→core projection",
                row.type_,
                row.id_,
                exc,
            )
            try:
                wire_obj = wire_object_from_row(row)
            except WIRE_ROW_FAILURES:
                # Under ARCH-25-003 (ADR-0099) a paired type's wire class *is* its
                # core class, so there is no looser fallback left to try.
                # dl.read() will report the row absent; say why, loudly, or
                # the caller sees a misleading "not found" (issue #2232).
                logger.warning(
                    "Row %r (type %r) failed core validation (%s) and has no"
                    " wire fallback that validates; reading it as absent"
                    " (issue #2232).",
                    row.id_,
                    row.type_,
                    exc,
                )
                return None
            obj = project_wire_row_to_core(row, wire_obj, exc)
    if obj is None:
        return None
    obj = rehydrate_fields(dl, obj)
    return coerce_to_semantic_class(obj)
