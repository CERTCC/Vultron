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

"""Row-type resolution: which class a stored row's ``type_`` names.

Maps a row's stored type value onto the most precise core class the
registries name, and reads a wire-only row into its wire class before
projecting it onto core.
"""

import logging
from typing import cast

from pydantic import ValidationError

from vultron.adapters.driven.db_record import (
    Record,
    record_to_object,
)
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.type_lookup import core_class_for_type
from vultron.errors import VultronValidationError

from ..schema import StoredRow

logger = logging.getLogger(__name__)


#: The stored-row name of the core lookup: a row stores the object's ``type``
#: value, which the core reads back with the same lookup an embedded object
#: does (DL-05-006, #6305).
core_class_for_row_type = core_class_for_type


WIRE_ROW_FAILURES: tuple[type[Exception], ...] = (
    ValueError,
    ValidationError,
    VultronValidationError,
)
"""What :func:`wire_object_from_row` raises for a row that does not validate."""


def wire_object_from_row(row: StoredRow) -> PersistableModel:
    """Reconstruct *row* through the wire vocabulary.

    Raises one of :data:`WIRE_ROW_FAILURES` when the stored data does not
    validate; the caller decides how to report the row absent.
    """
    rec = Record(id_=row.id_, type_=row.type_, data_=row.data)
    return cast(PersistableModel, record_to_object(rec))


def project_wire_row_to_core(
    row: StoredRow,
    wire_obj: PersistableModel,
    core_exc: Exception,
) -> PersistableModel:
    """Project a wire-vocabulary fallback back to its core counterpart.

    :func:`from_row` reaches this only when the row's ``type_`` *has* a core
    counterpart but the stored data does not validate against it, so the
    wire class was used instead.  Handing that wire object to core callers
    is what DL-05-001/DL-05-002 forbid: a wire ``as_VulnerabilityCase``
    reaching ``resolve_case`` raises "Expected VulnerabilityCase, got
    as_VulnerabilityCase" rather than reading the case (issue #2232).

    ``to_core()`` is the read-side wire→core projection: since #2940 removed
    the write-side normalisation gate (``extra="forbid"`` now rejects a
    wire-shaped payload handed to a core type rather than silently storing it),
    a row nonetheless persisted in a wire shape is projected here on the way
    out.  Wire types are looser than core types, so a row that fails core
    validation directly can still project cleanly: ``to_core()`` maps flat wire
    spellings onto the nested core shape instead of dropping them.

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
