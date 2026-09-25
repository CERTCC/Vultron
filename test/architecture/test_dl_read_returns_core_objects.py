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

from typing import cast

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from pydantic.alias_generators import to_camel

from test.support.core_vocab import minimal_kwargs
from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.core.ports.datalayer import StorableRecord
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

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
# Each entry is a ``CORE_VOCABULARY`` key (a class name) whose saved instance
# currently round-trips back as a wire object rather than a core object.
# Remove an entry from this set when the round-trip regression is fixed.
#
# Empty since #3647: ``VultronNote`` stores as ``"Note"``, which never matched
# its class-name key, until ``from_row`` gained a type-value fallback
# (``hydration.core_class_for_row_type``).
# ---------------------------------------------------------------------------
KNOWN_WIRE_ESCAPES: frozenset[str] = frozenset()


def _collect_wire_escapes() -> frozenset[str]:
    """Return CORE_VOCABULARY keys whose ``dl.read()`` result is a wire type."""
    reset_datalayer()
    dl = SqliteDataLayer(
        actor_id="https://test.example/api/v2/actors/test-actor"
    )
    wire_escapes: set[str] = set()

    for vocab_key, base_cls in CORE_VOCABULARY.items():
        if not issubclass(base_cls, CoreObject):
            continue
        cls: type[CoreObject] = base_cls  # type: ignore[assignment]
        kwargs = minimal_kwargs(cls)
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


#: CORE_VOCABULARY keys whose *wire-shaped row* still reads back as a wire
#: object.  Distinct from KNOWN_WIRE_ESCAPES above, which only exercises rows
#: written from a *core-constructed* object.  Since #2940 removed the write-side
#: normalisation, ingress can persist a wire-shaped row verbatim, so that path
#: needs its own ratchet — a core-object round trip structurally cannot observe
#: it.
#:
#: Empty on purpose: measured at #3531, every shadowed core type reads a
#: wire-spelled row back as core.  Note this is *stricter* than
#: KNOWN_WIRE_ESCAPES — the actor types listed there escape only when the row
#: was written from a core object, not on this path.  Keep it empty.
KNOWN_WIRE_SHAPED_ROW_ESCAPES: frozenset[str] = frozenset()

#: Lower bound on how many types the wire-shaped-row ratchet must exercise, so a
#: fixture change cannot quietly reduce it to nothing (the failure mode #3531
#: found in the AC-6 guard).
_MIN_WIRE_SHAPED_ROWS_EXERCISED = 5


def _collect_wire_shaped_row_escapes() -> tuple[frozenset[str], int]:
    """Return (escapes, number of types actually exercised)."""
    reset_datalayer()
    dl = SqliteDataLayer(
        actor_id="https://test.example/api/v2/actors/test-actor"
    )
    escapes: set[str] = set()
    exercised = 0

    for vocab_key, base_cls in CORE_VOCABULARY.items():
        if not issubclass(base_cls, CoreObject):
            continue
        if vocab_key not in WIRE_TYPE_MAP:
            # Not a wire type, so ingress never stores a wire-shaped row of it.
            # Keyed on the ``type`` value rather than an ``as_{name}`` class:
            # under ADR-0099 detail 3 those classes are aliases, not entries.
            continue
        cls: type[CoreObject] = base_cls  # type: ignore[assignment]
        row_id = f"urn:test:{vocab_key.lower()}:wire-row-ratchet"
        kwargs = minimal_kwargs(cls)
        kwargs["id_"] = row_id
        try:
            core_obj: CoreObject = cls(**kwargs)
        except Exception:
            continue
        # Build a *wire-shaped* copy of valid core data: camelCase spellings plus
        # the wire-facing identity keys.  Deriving it from a constructed core
        # object keeps the payload semantically valid, so any failure to read it
        # back as core is a genuine shape escape rather than missing data.
        core_data = core_obj.model_dump(mode="json")
        wire_data = {
            to_camel(k): v
            for k, v in core_data.items()
            if k not in ("id_", "type_")
        }
        wire_data["id"] = row_id
        wire_data["type"] = vocab_key
        storable = StorableRecord(id_=row_id, type_=vocab_key, data_=wire_data)
        try:
            dl.create(storable)
        except Exception:
            continue
        result = dl.read(row_id)
        if result is None:
            continue
        exercised += 1
        if type(result).__module__.startswith(_WIRE_MODULE_PREFIX):
            escapes.add(vocab_key)

    reset_datalayer()
    return frozenset(escapes), exercised


def test_dl_read_projects_wire_shaped_rows_to_core() -> None:
    """A wire-shaped *row* must also read back as a core object (DL-05-002).

    #2940 removed the write-side wire→core normalisation, so a wire-shaped
    payload reaching ingress is now stored verbatim and the projection happens on
    read.  ``KNOWN_WIRE_ESCAPES`` cannot see that path — it writes rows from
    core-constructed objects — so without this ratchet a stored wire row could
    hand a wire object to core callers on *every* read, indefinitely and
    unobserved, rather than failing once at the boundary.
    """
    actual, exercised = _collect_wire_shaped_row_escapes()
    new_escapes = actual - KNOWN_WIRE_SHAPED_ROW_ESCAPES
    resolved = KNOWN_WIRE_SHAPED_ROW_ESCAPES - actual

    assert exercised >= _MIN_WIRE_SHAPED_ROWS_EXERCISED, (
        f"only {exercised} wire-shaped rows were exercised (expected at least "
        f"{_MIN_WIRE_SHAPED_ROWS_EXERCISED}) — the fixture stopped building "
        "valid rows and this ratchet is checking almost nothing"
    )

    assert not new_escapes, (
        "NEW wire-shaped-row escapes — dl.read() returned a vultron.wire.as2 "
        f"type for a verbatim wire row: {sorted(new_escapes)}. The read-side "
        "projection (hydration.project_wire_row_to_core) must resolve these."
    )
    assert not resolved, (
        "These wire-shaped-row escapes are fixed — remove them from "
        f"KNOWN_WIRE_SHAPED_ROW_ESCAPES: {sorted(resolved)}"
    )


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
