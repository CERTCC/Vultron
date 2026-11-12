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

"""Domain representations of AS2 activity types used in the core layer."""

# pyright: reportGeneralTypeIssues=false

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    Strict,
    ValidationInfo,
    field_serializer,
    field_validator,
)

from vultron.core.models._helpers import as_utc, format_timestamp
from vultron.core.models.base import CoreObject, NonEmptyString
from vultron.core.models.base.core_object import (
    CoreObjectOrIri,
    CoreObjectOrIriValues,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.embargo_termination import TerminationCause
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.sender_sequence import SenderSequence
from vultron.core.models.type_lookup import core_class_for_type

#: The ``closed`` time and flag branches, strict so that no string or number
#: is coerced to a time or a flag.
_StrictTime = Annotated[datetime, Strict()]
_StrictFlag = Annotated[bool, Strict()]
#: An RFC 3339 date-time, the form a dumped ``closed`` time takes.
_RFC3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"
)


class VultronActivity(CoreObject):
    """Domain representation of an AS2 activity for DataLayer storage.

    ``VultronActivity`` is the domain model for an inbound or outbound AS2
    activity object. It is distinct from ``VultronEvent`` (defined in
    ``vultron.core.models.events``), which is the semantic dispatch event
    that carries decomposed ID/type fields extracted from the wire format.
    A ``VultronEvent`` may carry a ``VultronActivity`` as its ``activity``
    field, but the two types serve different purposes: ``VultronActivity``
    persists activity records in the DataLayer, while ``VultronEvent`` drives
    handler dispatch in the core.

    ``type_`` is required and must be set to the actual activity type
    (e.g. ``"Offer"``, ``"Accept"``, ``"Invite"``, ``"Leave"``, ``"Read"``).

    Field names match the wire-layer ``as_Activity`` internal names so that
    a stored ``VultronActivity`` can be round-tripped through
    ``record_to_object`` and deserialized as the appropriate AS2 activity
    subclass.  ``object_`` uses alias ``"object"`` to match the AS2 wire
    field name; callers may pass either ``object_=`` or ``object=`` thanks
    to ``populate_by_name=True`` on ``CoreRecord``.
    """

    type_: NonEmptyString = Field(  # pyright: ignore[reportGeneralTypeIssues]
        validation_alias="type", serialization_alias="type"
    )
    #: Core activity classes share their ``type`` values (``"Create"``), so a
    #: dumped activity's ``type`` names none of them, and the type lookup
    #: leaves them all out (:func:`core_class_for_type`).
    type_names_no_class: ClassVar[bool] = True
    actor: NonEmptyString  # non-optional because every activity must have an actor
    # The AS2 Activity slots hold one embedded object or one non-blank IRI,
    # as their wire declarations on ``as_Activity`` do: a core object, an
    # object core does not model (a Link, a case stub) as the wire layer
    # built it, or the id a stored row collapsed it to.  A blank IRI is
    # refused when the activity is built (CS-08-001, #6305).
    object_: CoreObjectOrIri | None = Field(
        default=None,
        validation_alias="object",
        serialization_alias="object",
    )
    target: CoreObjectOrIri | None = None
    origin: NonEmptyString | None = None
    # AS2 Activity fields no Vultron activity uses yet.  They stay declared
    # (ARCH-25-008, ADR-0099): ``CoreObject`` forbids extras, and a stored wire
    # activity dumps them, even when null.
    instrument: CoreObjectOrIri | None = None
    result: CoreObjectOrIri | None = None
    # A Reporter's proposed embargo terms on Offer(VulnerabilityReport)
    # (EP-04-004); the wire dump carries it as ``proposedEmbargo``.  The
    # parse edge expands it to the core event, and only the event states
    # terms, so an IRI or another object is refused here.
    proposed_embargo: EmbargoEvent | None = None
    # A termination Remove(EmbargoEvent)'s why (EMB-13-005); the wire dump
    # carries it as ``terminationCause``, and the ledger entry that records
    # the Remove carries it with it.
    termination_cause: TerminationCause | None = None
    # The sender's ledger tail every case activity states (SYNC-18-001); a
    # Read(CaseLedgerEntry) states it as the entry it names (SYNC-17-001).
    # The wire dump carries it as ``ledgerPosition``.
    ledger_position: LedgerPosition | None = None
    # The sender's number for a case activity to the CASE_MANAGER
    # (SYNC-21-001), and the number a refusal notice says the CASE_MANAGER
    # expects next (SYNC-21-015).  The wire dump carries them as
    # ``senderSequence`` and ``expectedSenderSequence``.
    sender_sequence: SenderSequence | None = None
    expected_sender_sequence: SenderSequence | None = None
    # ``Question`` fields (AS2 §4.1).  Vultron sends no ``Question``, but a
    # received one is stored as this model, so every key its wire class dumps
    # must be a field here (ARCH-25-008).
    # ``anyOf``/``oneOf`` are non-functional (one option or many), as on
    # ``as_Question``.  ``closed`` is an object, a link, a time or a boolean
    # (AS2 §4.1).  The time and flag branches are strict, so a string such
    # as ``"1"`` or ``"yes"`` is never coerced to one; only an RFC 3339 time
    # string, the form a stored row holds a time in, is read as a time
    # (``_read_closed_time``).
    any_of: CoreObjectOrIriValues = None
    one_of: CoreObjectOrIriValues = None
    closed: _StrictTime | _StrictFlag | CoreObjectOrIri | None = None
    # Addressing carries actor references; a blank one names nobody
    # (CS-08-001).  Only ``to`` is modelled: Vultron addresses every direct
    # message with it (OX-08-001), and ``cc``/``bto``/``bcc`` have no handler
    # semantics (HP-10-001, ADR-0109).  ``cc`` stays declared on ``CoreObject``
    # only as AS2 vocabulary a stored wire activity may dump (ARCH-25-008);
    # the extractor never maps it and no core code reads it.
    to: list[NonEmptyString] | None = None
    # CM-16-003: the wire dump this model is validated from is camelCase, so
    # the alias is required — without it the field silently validates to None
    # and the suggested roles vanish from the delivered activity.
    suggested_roles: list[NonEmptyString] | None = Field(
        default=None,
        validation_alias="suggestedRoles",
        serialization_alias="suggestedRoles",
    )
    # Single-word, so the camelCase wire name is identical and no alias is
    # needed; stated explicitly because the neighbouring field shows what the
    # omission costs when the names do differ.
    roles: list[NonEmptyString] | None = None

    @field_validator(
        "object_",
        "target",
        "instrument",
        "result",
        "any_of",
        "one_of",
        "closed",
        mode="before",
    )
    @classmethod
    def _read_embedded_dumps(
        cls, value: object, info: ValidationInfo
    ) -> object:
        """Read an embedded object's dump back as the class that wrote it.

        A dumped activity holds its embedded objects as mappings, and the
        slot's ``CoreObject`` branch forbids every field a subclass adds, so
        the activity would refuse its own dump (ARCH-23-005).  Each mapping
        is built as the class its ``type`` names first.

        An object core does not model (a Link, a case reference) is held as
        the wire layer built it, and its dump names no core class, so an
        activity holding one does not read its own dump back in core: only
        the stored-row reader, which can name wire classes, rebuilds it.
        """
        if isinstance(value, list):
            return [_read_embedded_dump(item, info) for item in value]
        return _read_embedded_dump(value, info)

    @field_validator("closed", mode="before")
    @classmethod
    def _read_closed_time(cls, value: object) -> object:
        """Read an RFC 3339 time string as the time it states.

        A stored row and a JSON dump hold ``closed`` as a string; the strict
        time branch takes only a ``datetime``, so the string is parsed here.
        Only a string with a ``T`` between date and time is a time, which no
        IRI and no flag spelling is.
        """
        if isinstance(value, str) and _RFC3339.fullmatch(value):
            return datetime.fromisoformat(value)
        return value

    @field_validator("closed")
    @classmethod
    def _read_naive_closed_as_utc(
        cls, value: datetime | bool | CoreObjectOrIri | None
    ) -> datetime | bool | CoreObjectOrIri | None:
        """Read a naive ``closed`` time as UTC, as every core time is (CS-13-001)."""
        return as_utc(value) if isinstance(value, datetime) else value

    @field_serializer("closed", mode="wrap", when_used="json")
    def _serialize_closed(
        self,
        value: datetime | bool | CoreObjectOrIri | None,
        handler: SerializerFunctionWrapHandler,
    ) -> object:
        """Write a ``closed`` time in the fixed form every timestamp uses.

        ``CoreObject`` formats its own time fields (CS-13-007); ``closed`` is
        one too when it holds a time, and any other value dumps as declared.
        """
        if isinstance(value, datetime):
            return format_timestamp(value)
        return handler(value)


def _read_embedded_dump(value: object, info: ValidationInfo) -> object:
    """Build *value* as the core class its ``type`` names, when it is a dump.

    A mapping with an ``actor`` is an embedded activity, which reads back as
    a :class:`VultronActivity`: core activity classes share their ``type``
    values (``"Create"``), so the value cannot name one.  Any other mapping
    is built as the one core class that presents its ``type``.  A mapping
    no core class presents is left for the slot to judge, which refuses it:
    an object core does not model reaches core already built (ADR-0032).
    """
    if not isinstance(value, Mapping):
        return value
    if "actor" in value:
        return VultronActivity.model_validate(value, context=info.context)
    type_value = value.get("type", value.get("type_"))
    if not isinstance(type_value, str):
        return value
    try:
        target = core_class_for_type(type_value)
    except KeyError:
        return value
    return target.model_validate(value, context=info.context)


class VultronOffer(VultronActivity):
    """Domain representation of an Offer activity.

    Mirrors the essential fields of ``as_Offer``.
    ``type_`` is ``"Offer"`` to match the wire value.
    """

    type_: Literal["Offer"] = Field(
        default="Offer",
        validation_alias="type",
        serialization_alias="type",
    )


class VultronAccept(VultronActivity):
    """Domain representation of an Accept activity.

    Mirrors the essential fields of ``as_Accept``.
    ``type_`` is ``"Accept"`` to match the wire value.

    ``result`` carries the URI of the ``VulnerabilityCase`` this Accept
    refers to.  For a duplicate-proposal response (CP-05-006 AC-2), it is
    the URI of the *existing* case so the vendor can correlate the
    acceptance to the already-created case.  For a first-time acceptance
    it is the URI of the newly-created case.
    """

    type_: Literal["Accept"] = Field(
        default="Accept",
        validation_alias="type",
        serialization_alias="type",
    )
    result: NonEmptyString | None = Field(
        default=None,
        description=(
            "URI of the VulnerabilityCase this Accept produced or refers to "
            "(CP-05-006 AC-2)."
        ),
    )


class VultronCreateCaseActivity(VultronActivity):
    """Domain representation of a Create(VulnerabilityCase) activity.

    Mirrors the essential fields of ``as_CreateCase``.
    ``type_`` is ``"Create"`` to match the wire value.

    Per CP-05-003 and ADR-0045:

    - ``context`` MUST be the URI of the new ``VulnerabilityCase`` (consistent
      with all other case-scoped activities; required for inbox deferral routing).
    - ``in_reply_to`` carries the URI of the ``Accept(CaseProposal)`` activity
      that authorised case creation (causal antecedent in the AS2-correct field).
    """

    type_: Literal["Create"] = Field(
        default="Create",
        validation_alias="type",
        serialization_alias="type",
    )
    context: NonEmptyString | None = Field(
        default=None,
        description=(
            "URI of the VulnerabilityCase this activity is scoped to "
            "(CP-05-003, ADR-0045). MUST be the case URI, not the Accept URI."
        ),
    )
    in_reply_to: NonEmptyString | None = Field(
        default=None,
        validation_alias="inReplyTo",
        serialization_alias="inReplyTo",
        description=(
            "URI of the Accept(CaseProposal) that authorised this Create "
            "(CP-05-003, ADR-0045). Causal antecedent in the AS2-correct field."
        ),
    )
