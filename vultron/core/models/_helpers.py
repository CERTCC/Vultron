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

"""Shared helper utilities for core domain model types."""

import uuid
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel
from pydantic.alias_generators import to_camel

# Frozen reference to the real datetime type used for isinstance guards.
# `now_utc` looks up `datetime` by name at call time so that tests can
# monkeypatch `_helpers.datetime` to control the clock; those patches must not
# break isinstance() calls in parse_published, so we capture the real class here
# before any patch can replace the module-level name.
_datetime_type = datetime


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def days_from_now_utc(days: int = 45) -> datetime:
    """Return a UTC datetime *days* in the future, at second precision."""
    return now_utc() + timedelta(days=days)


#: Recency floor for statuses that carry no timestamps: they sort to the
#: bottom. ``id_`` MUST NOT be used as a recency tiebreaker (CM-29-001) — its
#: scheme (``urn:uuid`` vs ``https``) is an implementation artefact, not a
#: time proxy.
_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Return *value* as a timezone-aware UTC datetime, or ``None``.

    Wire-deserialized timestamps may be naive (``datetime.fromisoformat`` on an
    offset-less ISO string yields a naive datetime). Assume naive datetimes are
    UTC — consistent with :func:`now_utc` — so recency comparisons never mix
    naive and aware values, which would raise ``TypeError``.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def parse_published(value: Any) -> datetime | None:
    """Return *value* as a timezone-aware UTC datetime, or ``None``.

    Accepts a ``datetime`` or an ISO 8601 string; anything else — including a
    string that is not valid ISO 8601 — yields ``None`` so callers can tell
    "absent" from "unparseable" by checking the raw value themselves.  Naive
    inputs are assumed UTC, consistent with :func:`as_utc`.

    Unlike :func:`as_utc`, which only *attaches* UTC to a naive value, an
    aware input in another offset is converted, so the return value is always
    in UTC.  Comparisons work either way — Python compares aware datetimes
    across offsets correctly — but the value is rendered into
    spec-citing violation messages, and a mixed-offset message reads as though
    the guard compared unlike quantities.

    Shared by the case-ledger commit-boundary guard and the per-actor
    predecessor lookup that feeds it, so both read a claimed
    ``payloadSnapshot.published`` the same way (CS-22-001).
    """
    if isinstance(value, _datetime_type):
        parsed: datetime | None = value
    elif isinstance(value, str):
        try:
            parsed = _datetime_type.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    aware = as_utc(parsed)
    assert (
        aware is not None
    )  # parsed is a datetime here; as_utc only returns None for None input
    return aware.astimezone(timezone.utc)


def claimed_published_iso(activity_obj: Any) -> str:
    """Return *activity_obj*'s claimed ``published`` as an ISO 8601 string.

    For use by the hand-built ``payloadSnapshot`` dicts that the CaseActor
    commits on behalf of a participant.  Such a snapshot is attributed to that
    participant, so its ``published`` must be the participant's own claimed
    event time — taken from the activity that triggered it — and not the
    CaseActor's clock.  Mixing two clocks inside one actor's claimed stream is
    what the CLP-15-003 check reads as a timestamp regression, and it also
    leaves CLP-14-007/008 comparing the receiver's clock against itself on that
    path (ISSUE-3149).

    Falls back to the local clock when *activity_obj* is ``None`` or carries no
    parseable timestamp.  Anything that arrived off the wire has one —
    ``parse_activity`` refuses an inbound activity without it — so the fallback
    covers synthesised and legacy callers only.
    """
    claimed = parse_published(getattr(activity_obj, "published", None))
    return (claimed or now_utc()).isoformat()


def status_recency_key(
    updated: datetime | None, published: datetime | None
) -> datetime:
    """Return the recency sort key for a status: ``updated`` else ``published``.

    Both are normalised to timezone-aware UTC. When both are absent the key is
    ``datetime.min`` (UTC) so timestampless statuses sort to the bottom rather
    than by ``id_`` scheme (CM-29-001). Shared by the core and wire
    ``VulnerabilityCase.current_status`` implementations so the invariant lives
    in one place.
    """
    return as_utc(updated) or as_utc(published) or _MIN_UTC


class _Timestamped(Protocol):
    @property
    def updated(self) -> datetime | None: ...

    @property
    def published(self) -> datetime | None: ...


_StatusT = TypeVar("_StatusT", bound=_Timestamped)


def most_recent_status(statuses: Sequence[_StatusT]) -> _StatusT:
    """Return the most recent of *statuses*; a tie goes to the last appended.

    Recency is :func:`status_recency_key`.  Received statuses carry the
    sender's time or none at all (ISSUE-3257), so equal keys are ordinary, and
    append order is the only honest tiebreaker left: ``id_`` scheme is an
    implementation artefact (CM-29-001), and a bare ``max`` keeps the *first*
    maximal element, so a status appended with the same time as the one before
    it would never become current.

    Raises:
        ValueError: When *statuses* is empty.
    """
    _, latest = max(
        enumerate(statuses),
        key=lambda pair: (
            status_recency_key(pair[1].updated, pair[1].published),
            pair[0],
        ),
    )
    return latest


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
    pairs: "Iterable[tuple[str, str]]",
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

    Interim helper for the handful of core sync/effect nodes that rebuild core
    objects from inline snapshots.  It becomes redundant once the wire→core
    ``WireParsePort`` designed in ADR-0082 (#2938) lands and owns wire→core
    projection centrally; this is not a reintroduction of the retired
    persistence-boundary normalisation (#2940).
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
        return data
    # A snapshot carrying *both* spellings would collapse onto one key and lose
    # a value by iteration order, so reject a disagreement before remapping.
    data = collapse_duplicate_spellings(
        data,
        ((name, camel) for camel, name in remap.items()),
        owner=f"{cls.__name__} wire snapshot",
    )
    return {remap.get(key, key): value for key, value in data.items()}


def _new_urn() -> str:
    return f"urn:uuid:{uuid.uuid4()}"


def _as_id(obj: Any) -> str | None:
    """Return the ActivityStreams id of *obj* as a plain string.

    - If *obj* is ``None``, returns ``None``.
    - If *obj* has an ``id_`` attribute, returns ``obj.id_``.
    - Otherwise returns ``str(obj)``.

    This handles the mixed ``str | <wire-type>`` collections that arise when
    the DataLayer stores plain string IDs alongside rehydrated objects.
    """
    if obj is None:
        return None
    id_ = getattr(obj, "id_", None)
    if isinstance(id_, str):
        return id_
    return str(obj)
