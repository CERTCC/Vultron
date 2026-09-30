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

"""The sealed body of an outbound activity: what is delivered, byte for byte.

VM-08-003 requires that the exact blob a factory produced be used both as the
``CaseLedgerEntry.payloadSnapshot`` core records and as the payload the outbox
delivers, with no port or adapter enriching, mutating, or re-deriving it in
between.  The activity *record* the DataLayer holds cannot serve as that blob:
persistence dehydrates reference fields to ids and read-back rehydrates them
from whatever the store holds now, so a re-read is a reconstruction, not the
artifact (ADR-0074 § Outbound, ADR-0107 § Context).

So every adapter that persists an outbound activity also seals its body here —
the ``model_dump_json`` the factory's object produces under
:data:`OUTBOUND_DUMP_KWARGS`, stored verbatim as a string — and the outbox
handler delivers that string without reading the activity record at all.

Like :class:`~vultron.adapters.outbox_dead_letter.OutboxDeadLetterEntry`, the
record lives in the adapter layer but extends ``CoreRecord`` so that
``dl.read`` reconstructs it typed (ARCH-12-010).  Core never touches it: core
holds the same text as the ``activity_blob`` the trigger port returned.
"""

import json
import logging
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from vultron.core.models.base import CoreRecord, NonEmptyString
from vultron.core.models.protocols import PersistableModel
from vultron.errors import VultronValidationError

logger = logging.getLogger(__name__)


class SealStore(Protocol):
    """The two store operations sealing needs.

    Both the broad ``DataLayer`` port and the narrow ``CasePersistence`` port
    satisfy this structurally, so a caller holding either can seal.
    """

    def read(
        self, object_id: str, raise_on_missing: bool = False
    ) -> PersistableModel | None: ...

    def save(self, obj: PersistableModel) -> None: ...


#: Serialisation options for every outbound activity body.
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
OUTBOUND_DUMP_KWARGS: dict[str, Any] = {
    "by_alias": True,
    "exclude_none": True,
    "serialize_as_any": True,
}

_SEALED_BODY_SUFFIX = "#sealed-body"


class SealedOutboundBody(CoreRecord):
    """The exact JSON text of an outbound activity, sealed at emission.

    Attributes:
        type_: Fixed literal ``"SealedOutboundBody"`` for DataLayer type lookup.
        activity_id: The id of the activity whose body this is.
        body: The JSON text the factory's object dumped under
            :data:`OUTBOUND_DUMP_KWARGS`.  This is what the outbox delivers and
            what core records as ``payloadSnapshot``.
    """

    type_: Literal["SealedOutboundBody"] = Field(  # type: ignore[assignment]
        default="SealedOutboundBody",
        validation_alias="type",
        serialization_alias="type",
    )
    activity_id: NonEmptyString
    body: NonEmptyString


def sealed_body_id(activity_id: str) -> str:
    """Return the record id under which *activity_id*'s sealed body is stored."""
    return f"{activity_id}{_SEALED_BODY_SUFFIX}"


def dump_outbound_body(activity: BaseModel) -> str:
    """Return the sealed JSON text for *activity*."""
    return activity.model_dump_json(**OUTBOUND_DUMP_KWARGS)


def outbound_activity_id(activity: BaseModel) -> str:
    """Return the id an outbound *activity* is sealed under.

    Raises:
        VultronValidationError: when the activity carries no non-empty
            ``id_`` — there is nothing to seal it under, and nothing the
            outbox could queue.
    """
    activity_id = getattr(activity, "id_", None)
    if not isinstance(activity_id, str) or not activity_id:
        raise VultronValidationError(
            "seal_outbound_body: activity has no id_ and cannot be sealed"
        )
    return activity_id


def seal_outbound_body(dl: SealStore, activity: BaseModel) -> str:
    """Seal *activity*'s body in *dl* and return the text that is sealed.

    Sealing is write-once per activity id: a body already sealed for this id is
    returned unchanged, so a re-emission under an id the store already holds
    (which ``dl.create`` also refuses) hands core the text that was, or will
    be, delivered — not a second rendering of it.
    """
    activity_id = outbound_activity_id(activity)
    existing = read_sealed_body(dl, activity_id)
    if existing is not None:
        return existing.body
    body = dump_outbound_body(activity)
    dl.save(
        SealedOutboundBody(
            id_=sealed_body_id(activity_id),
            activity_id=activity_id,
            body=body,
        )
    )
    logger.debug("Sealed outbound body for activity '%s'", activity_id)
    return body


def read_sealed_body(
    dl: SealStore, activity_id: str
) -> SealedOutboundBody | None:
    """Return the sealed body of *activity_id*, or ``None`` when none is held."""
    stored = dl.read(sealed_body_id(activity_id))
    if isinstance(stored, SealedOutboundBody):
        return stored
    return None


def parse_sealed_body(sealed: SealedOutboundBody) -> dict[str, Any]:
    """Decode a sealed body into the AS2 document it holds.

    Raises:
        VultronValidationError: when the sealed text is not JSON, or not a
            JSON object — a seal that cannot happen through
            :func:`seal_outbound_body`, so it is reported as the defect it is
            rather than delivered.
    """
    try:
        parsed = json.loads(sealed.body)
    except ValueError as exc:
        raise VultronValidationError(
            f"sealed body of activity '{sealed.activity_id}' is not JSON:"
            f" {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise VultronValidationError(
            f"sealed body of activity '{sealed.activity_id}' is not a JSON"
            " object"
        )
    return parsed


def read_sealed_body_dict(
    dl: SealStore, activity_id: str
) -> dict[str, Any] | None:
    """The decoded sealed body of *activity_id*, or ``None`` when none is held."""
    sealed = read_sealed_body(dl, activity_id)
    return parse_sealed_body(sealed) if sealed is not None else None
