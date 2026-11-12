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

"""Read inbound and stored data into core models: absent times, key spellings."""

import types
from collections.abc import Iterable
from typing import (
    Annotated,
    Any,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ValidationInfo
from pydantic.alias_generators import to_camel
from pydantic.fields import FieldInfo

from vultron.core.models._helpers.clock import (
    _datetime_type,
)
from vultron.primitives import normalise_actor_id


class DuplicateKeySpellingError(ValueError):
    """Two spellings of one field arrived carrying different values.

    A :class:`ValueError` subclass on purpose: these are raised from
    ``mode="before"`` validators on union-exposed core types, and pydantic only
    converts ``ValueError``/``AssertionError`` into a ``ValidationError``.
    ``VultronValidationError`` is not a ``ValueError`` subclass, so raising it
    here would escape union resolution instead of failing the candidate branch
    (the hazard recorded in #2940 and AGENTS.md).
    """


def collapse_duplicate_spellings(
    data: dict[str, Any],
    pairs: Iterable[tuple[str, str]],
    *,
    owner: str,
) -> dict[str, Any]:
    """Drop redundant key spellings, raising when the two disagree.

    *pairs* is ``(keep, drop)`` key tuples.  When both keys are present and
    carry equal values the ``drop`` spelling is redundant and is removed; when
    they *disagree* one of two real values would be discarded silently, so this
    raises instead.  Silently picking a winner is the defect class
    ``extra="forbid"`` exists to eliminate (ARCH-12-003): it is how a
    participant's RM ladder was reset without a trace (#2232).

    Returns *data* unchanged (not copied) when there is nothing to collapse.
    """
    conflicts: list[str] = []
    drops: set[str] = set()
    for keep, drop in pairs:
        if keep not in data or drop not in data:
            continue
        if data[keep] == data[drop]:
            drops.add(drop)
            continue
        conflicts.append(
            f"{drop}={data[drop]!r} conflicts with {keep}={data[keep]!r}"
        )
    if conflicts:
        raise DuplicateKeySpellingError(
            f"{owner} received two spellings of the same field with different "
            f"values: {'; '.join(sorted(conflicts))}. Convert at the wire->core "
            "boundary instead of passing both spellings."
        )
    if not drops:
        return data
    return {k: v for k, v in data.items() if k not in drops}


def strip_annotated(annotation: Any) -> Any:
    """Return the bare type under an ``Annotated[...]``, else *annotation*.

    The IRI branch of every reference union is ``NonEmptyString``, an
    ``Annotated[str, AfterValidator(...)]`` (CS-08-001, CS-08-002).  Inside a
    union Pydantic keeps that wrapper, so code that asks "does this slot admit a
    string?" by testing ``branch is str`` stops seeing the branch the moment
    the alias is tightened — and a reference slot is then misread as an
    object-only slot.  Every annotation introspection that classifies a union
    branch goes through this helper so the wrapper is transparent to it.
    """
    if get_origin(annotation) is Annotated:
        return get_args(annotation)[0]
    return annotation


def reads_absent_as_none(field: FieldInfo) -> bool:
    """Whether a received omission of *field* reads as ``None``.

    True for a required time that admits ``None``: an author time
    (``published``, ``updated``, an embargo's ``start_time``), which an
    authored object states and a received one may omit (ADR-0103, ADR-0176).
    """
    return (
        field.is_required()
        and _is_datetime_field(field)
        and _admits_none(field)
    )


def _admits_none(field: FieldInfo) -> bool:
    """Return whether *field*'s annotation admits ``None``."""
    annotation = field.annotation
    if (
        isinstance(annotation, types.UnionType)
        or get_origin(annotation) is Union
    ):
        return type(None) in get_args(annotation)
    return False


def _is_datetime_field(field: FieldInfo) -> bool:
    """Return whether *field* can hold a ``datetime``.

    Compares against the frozen ``_datetime_type`` rather than the module-level
    ``datetime`` name, which tests monkeypatch to control the clock: a patched
    name would make every timestamp field read as a non-datetime and silently
    disable :func:`absent_times_as_none`.
    """
    annotation = field.annotation
    if annotation is _datetime_type:
        return True
    if (
        isinstance(annotation, types.UnionType)
        or get_origin(annotation) is Union
    ):
        return _datetime_type in get_args(annotation)
    return False


#: Validation-context key that marks a ``model_validate`` call as reading
#: *inbound* data.  ``parse_activity`` sets it, and so do the other edges that
#: read a peer's body (a fetched object, a demo client reading a served one);
#: an object this process authors must never be validated with it.  Defined in
#: core because both ``as_Base`` and ``CoreObject`` gate on it, and under
#: ARCH-25-003 (ADR-0099) a core class is what an inbound payload validates into.
INBOUND_CONTEXT_KEY = "inbound_wire"

#: Validation-context key that marks a ``model_validate`` call as reading a
#: *stored* row back.  The datalayer's row readers set it; nothing else should.
#: A validator that defaults an omitted field at construction refuses the
#: omission under this key instead, so a row written before the field existed
#: is refused with a reset note rather than silently given a value it never
#: held (no migration, #4087).
STORED_CONTEXT_KEY = "stored_row"


def normalise_inbound_actor_id(value: object, info: ValidationInfo) -> object:
    """Strip a trailing slash from an actor id read from a peer's body.

    The ``mode="before"`` half of a ``NormalisedActorId`` field on a class an
    inbound payload validates into (ARCH-25-003, ADR-0099).  A received
    activity's parse is where an actor id it carries is extracted, so it is
    normalised there (OID-01-006).  Any other construction is left alone, so
    the field's type refuses an id this process authored or stored with the
    other spelling (ARCH-10-001): a stored row is never rewritten on read.
    """
    context = info.context
    if (
        isinstance(value, str)
        and isinstance(context, dict)
        and context.get(INBOUND_CONTEXT_KEY)
    ):
        return normalise_actor_id(value)
    return value


def blank_times_as_none(
    cls: type[BaseModel], data: dict[str, Any]
) -> dict[str, Any]:
    """Read a blank-string timestamp in *data* as ``None`` (CS-08-001).

    The core counterpart of ``as_Object.validate_datetime``'s blank handling:
    a blank carries no time, so it is absence rather than a malformed value.
    Checks every spelling a datetime field can arrive under.
    """
    for name, field in cls.model_fields.items():
        if not _is_datetime_field(field):
            continue
        for key in (name, field.alias, field.validation_alias):
            if not isinstance(key, str):
                continue
            value = data.get(key)
            if isinstance(value, str) and not value.strip():
                data[key] = None
    return data


def absent_times_as_none(
    cls: type[BaseModel], data: dict[str, Any]
) -> dict[str, Any]:
    """Read every absent required timestamp that admits ``None`` as ``None``.

    The author's times (``published``, ``updated``, an embargo's
    ``start_time``) are required with no default (ADR-0176): an object this
    process authors states the act's instant.  A received object may omit
    them, because AS2 lets a sender omit them, and the omission is the sender
    claiming no time, so it reads as ``None``, never as the receiver's clock
    (ISSUE-3257, CLP-15-007).

    Absence has two spellings on the two inbound edges and both arrive here as
    an absent key: a sender omits the field on the wire, and a stored snapshot
    drops it because the snapshot dump excludes ``None``.  A required time
    that does not admit ``None`` (a case status's ``published``, a ledger
    entry's ``received_at``) stays absent, so validation refuses it, as it
    does when a validator needs the time (a case's genesis hash, CLP-08-002),
    rather than deciding on a minted value later (ADR-0032, ADR-0103).
    """
    for name, field in cls.model_fields.items():
        if not reads_absent_as_none(field):
            continue
        keys = {name} | {
            key
            for key in (field.alias, field.validation_alias)
            if isinstance(key, str)
        }
        if keys.isdisjoint(data):
            data[name] = None
    return data


def project_wire_snapshot_to_core(cls: type[BaseModel], data: Any) -> Any:
    """Rename a wire-rendered snapshot's camelCase keys to *cls*'s field names.

    A ledger ``payloadSnapshot`` embeds objects in AS2 wire shape (camelCase,
    e.g. ``attributedTo``).  Reconstructing a core object from one is a
    *deliberate* wire→core crossing, distinct from the accidental
    wire-shaped-input that ``extra="forbid"`` exists to reject (ARCH-12-003):
    the crossing must project the spellings first.  Core fields that carry an
    explicit ``validation_alias`` (``id``, ``type``, ``@context``,
    ``inReplyTo``) already accept their wire form; this maps the remaining
    ``to_camel`` spellings (``attributedTo`` → ``attributed_to``) back to the
    field name so the core type validates without loosening its guard.

    Projection also reads an absent required timestamp as ``None``
    (:func:`absent_times_as_none`).  A snapshot is dumped with
    ``exclude_none=True``, so an object whose time was carried as absent has no
    key at all here, and reading it as anything else would invent a time —
    once, a clock default stamped *this replica's* clock in its place — the
    same fabrication the wire parser refuses one boundary earlier, and the
    reason two replicas disagreed about which status was current (ISSUE-3257, CLP-15-007).

    Helper for the handful of core sync/effect nodes that rebuild core
    objects from inline snapshots.  The ``WireParsePort`` ADR-0082 designed to
    own this centrally (#2938) was rejected by ADR-0099, so this stays the
    seam; it is not a reintroduction of the retired persistence-boundary
    normalisation (#2940).
    """
    if not isinstance(data, dict):
        return data
    remap: dict[str, str] = {}
    for name, field in cls.model_fields.items():
        if isinstance(field.validation_alias, str):
            continue  # an explicit alias already accepts the wire spelling
        camel = to_camel(name)
        if camel != name:
            remap[camel] = name
    if not remap:
        return absent_times_as_none(cls, dict(data))
    # A snapshot carrying *both* spellings would collapse onto one key and lose
    # a value by iteration order, so reject a disagreement before remapping.
    collapsed = collapse_duplicate_spellings(
        data,
        ((name, camel) for camel, name in remap.items()),
        owner=f"{cls.__name__} wire snapshot",
    )
    # Read absences only once the wire spellings have been projected onto field
    # names: a core field's camelCase form is a spelling this helper supplies,
    # not an alias the field itself declares, so reading first would take a
    # present ``receivedAt`` for an absent ``received_at``.
    projected: dict[str, Any] = {
        remap.get(key, key): value for key, value in collapsed.items()
    }
    return absent_times_as_none(cls, projected)


class MissingReceivedIdError(ValueError):
    """A received ActivityStreams Object carries no ``id`` (OID-01-013).

    A :class:`ValueError` subclass so pydantic turns it into a
    ``ValidationError`` and a union tries its next branch, as
    :class:`DuplicateKeySpellingError` explains.
    """


#: The keys an object's id may arrive under: the AS2 term, and the field name
#: a stored or by-name dump uses.
_ID_KEYS = ("id", "id_")


def refuse_absent_id(cls: type[BaseModel], data: dict[str, Any]) -> None:
    """Raise :class:`MissingReceivedIdError` when *data* names no ``id``.

    ActivityPub gives every object it distributes a global id, and a receiver
    that minted one would present its own invention as the sender's object
    (OID-01-013).  For the inbound path only: an object this process builds
    takes the minting default.  A blank id is refused by ``NonEmptyString``
    itself; absent and ``None`` are refused here.
    """
    if all(data.get(key) is None for key in _ID_KEYS):
        raise MissingReceivedIdError(
            f"a received {cls.__name__} carries no 'id'; every object a"
            " sender distributes carries its own id, and the receiver mints"
            " none for it (OID-01-013, OID-01-014)"
        )
