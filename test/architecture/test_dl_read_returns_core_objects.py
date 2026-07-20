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
"""Architecture ratchet: dl.read() must not return wire vocab types into core.

This test enforces DL-05-004: no ``vultron.wire.as2`` vocabulary type may be
returned from ``dl.read()`` / ``dl.list_objects()`` into ``vultron/core/``.

For every type registered in ``CORE_VOCABULARY``, the test saves a minimal
instance to an in-memory ``SqliteDataLayer`` and reads it back.  The
returned object's ``__module__`` must not start with ``vultron.wire.as2``.

AS2 Activity types (those whose ``type_`` is registered only in the wire
``VOCABULARY``, not in ``CORE_VOCABULARY``) have no core counterpart and are
exempt from this rule.  That exemption is tracked in ``ACTIVITY_TYPE_EXEMPTIONS``
below (DL-05-004).  The exemption set may only shrink — a type that moves to a
core counterpart must be removed from the set, or the test fails.

Ratchet pattern
---------------
``KNOWN_WIRE_ESCAPES`` documents every pre-existing ``CORE_VOCABULARY`` type
that currently round-trips back as a wire object awaiting migration.  The
test asserts::

    actual_wire_escapes == KNOWN_WIRE_ESCAPES

This means:

- A **new** wire escape (not in ``KNOWN_WIRE_ESCAPES``) fails immediately.
- A **resolved** escape (in ``KNOWN_WIRE_ESCAPES`` but no longer occurring)
  also fails — prompting removal of that entry from ``KNOWN_WIRE_ESCAPES``
  so the ratchet stays tight.

Spec: ``specs/datalayer.yaml`` DL-05-004
ADR: ``docs/adr/0034-datalayer-returns-core-objects.md``
Related: issue #1503 (read-path implementation), issue #1506 (activity
read-back migration)
"""

from datetime import timedelta
from typing import cast

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.registry import CORE_VOCABULARY

_WIRE_MODULE_PREFIX = "vultron.wire.as2"

# ---------------------------------------------------------------------------
# AS2 Activity type exemptions (DL-05-004).
#
# These ``type_`` strings are stored in the DataLayer as wire Activities.
# They have no registered core counterpart in ``CORE_VOCABULARY``, so
# ``dl.read()`` legitimately returns a wire-layer object for them.  Core code
# that reads stored Activities is itself a boundary violation tracked in
# issue #1506 / ADR-0035; that migration is out of scope here.
#
# Enumerate every exempted type_ string explicitly.  Remove an entry when the
# corresponding Activity gains a core counterpart (its ``type_`` key will
# then appear in ``CORE_VOCABULARY`` and the exemption becomes stale).
# ---------------------------------------------------------------------------
ACTIVITY_TYPE_EXEMPTIONS: frozenset[str] = frozenset(
    {
        "Accept",
        "Activity",
        "Add",
        "Announce",
        "Arrive",
        "Block",
        "Create",
        "Delete",
        "Dislike",
        "Flag",
        "Follow",
        "Ignore",
        "Invite",
        "Join",
        "Leave",
        "Like",
        "Listen",
        "Move",
        "Question",
        "Read",
        "Reject",
        "Remove",
        "TentativeAccept",
        "TentativeReject",
        "Travel",
        "Undo",
        "Update",
        "View",
    }
)

# ---------------------------------------------------------------------------
# Known pre-existing wire escapes for CORE_VOCABULARY types.
#
# Each entry is a ``CORE_VOCABULARY`` key (i.e., the ``type_`` string used
# when the object was persisted) that currently round-trips back as a wire
# object rather than a core object.  These are actor types whose ``type_``
# value ("Person", "Service", etc.) is intercepted by the wire VOCABULARY
# before the core-vocabulary path can resolve them.
#
# Fix: ensure ``_from_row`` resolves these via ``CORE_VOCABULARY`` before
# falling back to the wire path.  No migration issue filed yet; file one
# when this ratchet is ready to be tightened.
#
# Remove an entry from this set when the round-trip regression is fixed.
# ---------------------------------------------------------------------------
KNOWN_WIRE_ESCAPES: frozenset[str] = frozenset(
    {
        "CaseActor",
        "VultronApplication",
        "VultronGroup",
        "VultronOrganization",
        "VultronPerson",
        "VultronService",
    }
)


def _minimal_kwargs(cls: type[CoreObject]) -> dict:
    """Return the minimum kwargs to construct *cls* without validation errors."""
    kwargs: dict = {}
    for field_name, field_info in cls.model_fields.items():
        if not field_info.is_required():
            continue
        ann = str(field_info.annotation)
        if "timedelta" in ann:
            kwargs[field_name] = timedelta(days=90)
        else:
            kwargs[field_name] = f"urn:test:{field_name}:1"
    return kwargs


def _collect_wire_escapes() -> frozenset[str]:
    """Return CORE_VOCABULARY keys whose ``dl.read()`` result is a wire type."""
    reset_datalayer()
    dl = SqliteDataLayer()
    wire_escapes: set[str] = set()

    for vocab_key, base_cls in CORE_VOCABULARY.items():
        if not issubclass(base_cls, CoreObject):
            continue
        cls: type[CoreObject] = base_cls  # type: ignore[assignment]
        kwargs = _minimal_kwargs(cls)
        kwargs["id_"] = f"urn:test:{vocab_key.lower()}:ratchet"
        try:
            obj: CoreObject = cls(**kwargs)
        except Exception:
            # If we cannot construct a minimal instance we skip — the type
            # is not a concern for this ratchet (no core code saves it without
            # required fields either).
            continue

        dl.save(cast(PersistableModel, obj))
        result = dl.read(obj.id_)

        if result is None:
            continue
        if type(result).__module__.startswith(_WIRE_MODULE_PREFIX):
            wire_escapes.add(vocab_key)

    reset_datalayer()
    return frozenset(wire_escapes)


def test_dl_read_returns_core_objects_not_wire_types() -> None:
    """dl.read() must return core objects for all CORE_VOCABULARY types.

    Saves a minimal instance of each type in CORE_VOCABULARY to an
    in-memory DataLayer, reads it back, and asserts the returned object's
    module does not start with ``vultron.wire.as2``.

    Enforces DL-05-004.  See module docstring for the ratchet strategy.
    """
    actual = _collect_wire_escapes()
    new_escapes = actual - KNOWN_WIRE_ESCAPES
    resolved = KNOWN_WIRE_ESCAPES - actual

    diff_lines: list[str] = []
    if new_escapes:
        diff_lines.append(
            "NEW wire escapes — dl.read() returned a vultron.wire.as2 type "
            "for a CORE_VOCABULARY entry (DL-05-004 regression):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_escapes))
    if resolved:
        diff_lines.append(
            "RESOLVED wire escapes — remove these entries from "
            "KNOWN_WIRE_ESCAPES (ratchet must stay tight):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_WIRE_ESCAPES, "\n\n" + "\n".join(diff_lines)


def test_activity_type_exemptions_are_not_in_core_vocabulary() -> None:
    """AS2 Activity exemptions must not appear in CORE_VOCABULARY.

    If any type listed in ACTIVITY_TYPE_EXEMPTIONS gains a core counterpart
    (i.e., its ``type_`` key appears in CORE_VOCABULARY), it is no longer an
    Activity-only type and should be removed from the exemption set.

    This keeps the exemption set shrink-only per DL-05-004.
    """
    stale_exemptions = ACTIVITY_TYPE_EXEMPTIONS & frozenset(
        CORE_VOCABULARY.keys()
    )
    assert not stale_exemptions, (
        f"Stale ACTIVITY_TYPE_EXEMPTIONS — these types now have a core "
        f"counterpart and should be removed from the exemption set: "
        f"{sorted(stale_exemptions)}"
    )
