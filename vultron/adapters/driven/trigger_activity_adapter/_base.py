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

"""Shared constants and base class for TriggerActivityAdapter submodules."""

from typing import Any, TypeVar

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.errors import VultronNotFoundError
from vultron.wire.as2.vocab.base.base import as_Base

#: Serialisation options for every outbound activity dict this adapter returns.
#:
#: ``serialize_as_any=True`` is load bearing, not cosmetic. Without it Pydantic
#: serialises each field by its *declared* type, so an inline nested object held
#: in a field typed as a reference union is flattened — for
#: ``as_CaseProposal.object_`` (declared ``ActivityStreamRequiredRef[
#: as_VulnerabilityReport]``) the report came out as ``null``, putting a proposal
#: on the wire with no report at all in breach of CP-01-004. The receiver then had
#: nothing to store, and everything derived from the report — the reporter
#: participant, its ledger entry, the SIGNATORY seed — skipped "best-effort", so
#: the reporter silently never received a case replica.
#:
#: The same flag is required on the delivery path and in the test router, both of
#: which say so; this is the third place that needs it.
_DUMP_KWARGS: dict[str, Any] = {
    "by_alias": True,
    "exclude_none": True,
    "serialize_as_any": True,
}

_BM = TypeVar("_BM", bound=as_Base)


def _to_wire(core_obj: Any, wire_cls: type[_BM]) -> _BM:
    """Convert a core domain object to its wire vocabulary counterpart.

    Uses ``wire_cls.from_core(core_obj)`` so that wire classes that override
    ``from_core`` (e.g. ``as_VulnerabilityCase`` which wraps ``case_activity``
    string IDs as stub ``as_Activity`` objects) apply their custom logic.

    Raises:
        VultronNotFoundError: when *core_obj* is ``None`` (dl.read returned
            no match for the requested ID).
    """
    if core_obj is None:
        raise VultronNotFoundError(
            wire_cls.__name__,
            "object not found in DataLayer",
        )
    if isinstance(core_obj, wire_cls):
        return core_obj
    return wire_cls.from_core(core_obj)  # type: ignore[attr-defined,return-value,no-any-return]


class _TriggerAdapterBase:
    """Base class providing DataLayer access to trigger adapter mixins.

    Args:
        dl: The DataLayer for reading persisted objects and creating
            activities.
    """

    def __init__(self, dl: CaseOutboxPersistence) -> None:
        self._dl = dl
