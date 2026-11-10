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

"""The status history of a :class:`VulnerabilityCase` (CM-29).

Appending a status and reading the current one.  EM on a status is only a
stamped copy of the embargo register's (ADR-0122).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from vultron.core.models._helpers import (
    new_object_id,
    stamp_after,
)
from vultron.core.models.case_status import CaseStatus
from vultron.errors import VultronValidationError

if TYPE_CHECKING:
    from vultron.core.models.base import NonEmptyString
    from vultron.core.models.case.vulnerability_case import VulnerabilityCase


class CaseStatusHistoryMixin:
    """Status-history methods of :class:`VulnerabilityCase`."""

    if TYPE_CHECKING:
        # The model's fields, and the register's EM stamp, this mixin uses.
        id_: NonEmptyString
        case_statuses: list[NonEmptyString | CaseStatus]

        def _stamp_em(self) -> None: ...

    def add_case_status(self, status: CaseStatus) -> None:
        """Append a CaseStatus to this case's history.

        Validates the appended item's shape and raises
        :exc:`~vultron.errors.VultronValidationError` when a non-core
        (wire-shaped) input is passed, closing the ``append`` door for
        ``case_statuses`` (CM-27-003, ADR-0064).

        Args:
            status: A core :class:`CaseStatus` object.

        Raises:
            VultronValidationError: when *status* is not a
                :class:`CaseStatus` instance.
        """
        if not isinstance(status, CaseStatus):
            raise VultronValidationError(
                f"add_case_status expects a CaseStatus; "
                f"got {type(status).__name__}"
            )
        self.case_statuses.append(status)
        # EM is the register's, never the appended status's (ADR-0122).
        self._stamp_em()

    def append_case_status(self, at: datetime, **updates: Any) -> None:
        """Append a new CaseStatus derived from the current one with fields overridden.

        Inherits all fields from ``current_status`` then assigns each of
        *updates* by its ``CaseStatus`` field name, so passing
        ``pxa=CS_pxa.Pxa`` (or a ``PxaDimension``) keeps every other
        dimension.  Each assignment is validated (ARCH-21-001).  The new
        entry gets a fresh ``id_`` and a ``name`` derived from its own states
        unless one is passed.  Its ``published`` is the act's instant *at*,
        bumped by ``stamp_after`` so it is strictly later than the current
        status's (CM-29-005): two statuses appended in one act share *at*,
        and the bump sorts them in append order (ADR-0167).  The method reads
        no clock (ADR-0176).  The new status carries no ``updated``: a status
        is never changed after it is appended, so ``published`` is its one
        time (CM-29-006).  EM is not a status field to set: it is derived
        from the embargo register (ADR-0122), so ``em`` is refused.

        Args:
            at: The act's instant; timezone-aware.
            **updates: ``CaseStatus`` field names and their new values.

        Raises:
            VultronValidationError: when ``em`` is passed, or when a keyword
                names no ``CaseStatus`` field (the retired flat spellings
                ``pxa_state`` / ``em_state`` included, SDO-03-003).
            ValueError: when *at* is naive (CS-13-001).
        """
        if "em" in updates:
            raise VultronValidationError(
                "append_case_status: EM is derived from the embargo register"
                " (ADR-0122); change the register instead of the status."
            )
        unknown = sorted(set(updates) - set(CaseStatus.model_fields))
        if unknown:
            raise VultronValidationError(
                f"append_case_status: {', '.join(unknown)} names no"
                " CaseStatus field"
            )
        current = self.current_status
        stamp = stamp_after(at, current.published)

        # The new entry is its own status: a fresh ``id_``, and a ``name``
        # left unset so ``CaseStatus._set_name`` re-derives the label from
        # the new states on the first assignment below (an explicit ``name``
        # in *updates* still wins).  ``model_copy`` does not validate its
        # update, so the overrides are assigned one by one under
        # ``validate_assignment`` instead, and the case context and bumped
        # timestamp are assigned last so that they always win.  The copied
        # ``updated`` is cleared, not carried: it is the old status's.
        status = current.model_copy(
            update={"id_": new_object_id(), "name": None}
        )
        for name, value in {
            **updates,
            "context": self.id_,
            "published": stamp,
            "updated": None,
        }.items():
            setattr(status, name, value)
        self.add_case_status(status)

    @property
    def current_status(self) -> CaseStatus:
        """Return the last materialized :class:`CaseStatus` appended.

        Append order, never a timestamp, decides the current status
        (CM-29-001), as it does a participant's (SM-05-002): every status is
        the CASE_MANAGER's, each built as a valid next step from the one
        before it, and a replica appends them in ledger order.  A clock that
        steps back, or a CASE_MANAGER on another clock, therefore cannot
        make an older status current.

        Raises:
            ValueError: When no materialized :class:`CaseStatus` exists.
        """
        current = self._last_materialized_status()
        if current is None:
            raise ValueError(
                "VulnerabilityCase has no materialized CaseStatus"
            )
        return current

    def _last_materialized_status(self) -> CaseStatus | None:
        """The last :class:`CaseStatus` object in ``case_statuses``, if any.

        A bare id is a reference, not a status, so it is skipped.
        """
        return next(
            (
                s
                for s in reversed(self.case_statuses)
                if isinstance(s, CaseStatus)
            ),
            None,
        )

    @property
    def case_status(self) -> CaseStatus:
        """Return the current :class:`CaseStatus` (alias for ``current_status``)."""
        return self.current_status


def has_case_statuses(case: VulnerabilityCase) -> bool:
    """Return True when *case* has at least one CaseStatus entry.

    Use this as the single shared predicate wherever code must distinguish
    "no status history yet" from "at least one status recorded" — in both
    BT condition nodes and plain use-case guards (LST-05 / AC-5).
    """
    return bool(case.case_statuses)
