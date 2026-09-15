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
from datetime import datetime, timedelta, timezone
from typing import Any

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
