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

"""The ledger position of the case copy a replica last replaced its case with.

A replica that replaces its case file with a copy whose ledger tail is ahead
of its own chain holds a case that already reflects the entries up to that
tail (SYNC-16-006, ADR-0142).  This record keeps that tail, so each of those
entries it later stores, replayed or drained, is stored as a no-op rather than
applied again over the copy (SYNC-16-007).

It is the replica's own bookkeeping, never a value of the case file: the case
is replicated, this record is not (CLP-07-014).
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Literal

from pydantic import Field, model_validator

from vultron.core.models.base import CoreRecord, NonEmptyString, with_record_id
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)


class CaseCopyPosition(CoreRecord):
    """The tail of the case copy that last replaced this replica's case file.

    The ``id_`` is derived from ``case_id``, so a replica holds one per case
    and a later replacement overwrites it.
    """

    type_: Literal["CaseCopyPosition"] = Field(  # type: ignore[assignment]
        default="CaseCopyPosition",
        validation_alias="type",
        serialization_alias="type",
    )
    case_id: NonEmptyString = Field(
        ..., description="URI of the case the copy replaced"
    )
    log_index: int = Field(
        ...,
        ge=EMPTY_LEDGER_LOG_INDEX,
        description="log_index of the last entry the copy reflects",
    )
    entry_hash: NonEmptyString = Field(
        ..., description="entry_hash of the last entry the copy reflects"
    )

    @property
    def position(self) -> LedgerPosition:
        """The copy's tail as a :class:`LedgerPosition`."""
        return LedgerPosition(
            log_index=self.log_index, entry_hash=self.entry_hash
        )

    @classmethod
    def build_id(cls, case_id: str) -> str:
        """Return the stable DataLayer ID for *case_id*."""
        slug = urllib.parse.quote(case_id, safe="")
        return f"case-copy-position/{slug}"

    @model_validator(mode="before")
    @classmethod
    def _set_id(cls, data: Any) -> Any:
        """Compute ``id_`` deterministically from ``case_id``."""
        if isinstance(data, dict):
            case_id = data.get("case_id")
            if case_id is not None:
                data = with_record_id(data, cls.build_id(case_id))
        return data


__all__ = ["CaseCopyPosition"]
