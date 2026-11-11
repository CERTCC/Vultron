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

"""Construction-time seeding for :class:`VulnerabilityCase`.

The before-validators of the case model delegate here: a case this process
authors gets its id, genesis hash, ledger position and first status seeded;
a received or stored case that lacks one is refused (ADR-0103, CLP-08-002).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    ValidationInfo,
)

from vultron.core.models._helpers import (
    INBOUND_CONTEXT_KEY,
    STORED_CONTEXT_KEY,
    blank_as_none,
    new_object_id,
)
from vultron.core.models.case_ledger import compute_genesis_hash
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.models.wire_keys import wire_key
from vultron.errors import VultronValidationError


def _present_key(data: dict[str, Any], field_name: str) -> str:
    """Return the spelling of *field_name* that *data* carries.

    The AS2 spelling when present (an inbound case, ARCH-25-002, ADR-0099), else
    the field name, so a validator writes back under the key it read.
    """
    as2 = wire_key(field_name)
    return as2 if as2 in data else field_name


def _owner(data: dict[str, Any]) -> Any:
    """Return the case owner *data* carries under either spelling, or ``None``."""
    return data.get("attributed_to") or data.get(wire_key("attributed_to"))


def _names_blank_id(data: dict[str, Any]) -> bool:
    """Whether *data* carries an id key whose value is blank.

    A blank id is refused by ``id_``'s type (CS-08-001); a before-validator
    that sees one leaves *data* as it is, so that refusal names the id rather
    than a seed built from it.
    """
    return any(
        isinstance(data.get(key), str) and not data[key].strip()
        for key in ("id", "id_")
    )


def _start_ledger_position(
    data: dict[str, Any], info: ValidationInfo
) -> dict[str, Any]:
    """Start a case that names no ledger position at its empty ledger.

    Only a case this process builds starts there: index -1 with its genesis
    hash, the position of a ledger with no entries (CLP-08-004).  A stored row
    or a received case that omits the field is refused instead.  A stored one
    was written before cases carried their position, and no conversion is made,
    so the store must be reset (#4087).  A received one is a sender that left
    out what SYNC-16-005 requires, and a receiver infers nothing for it
    (ADR-0103).  An explicit value is left to field validation and
    :meth:`VulnerabilityCase._empty_ledger_names_genesis`.
    """
    key = _present_key(data, "ledger_position")
    if key in data or not _owner(data):
        return data
    context = info.context if isinstance(info.context, dict) else {}
    case_id = data.get("id") or data.get("id_") or "<unknown>"
    if STORED_CONTEXT_KEY in context:
        raise VultronValidationError(
            f"VulnerabilityCase '{case_id}' was stored without a"
            " ledger_position, the shape before #5091 made each case store"
            " the ledger position it is a projection of (SYNC-16-005); no"
            " conversion is made, so a store written before the change must"
            " be reset"
        )
    if INBOUND_CONTEXT_KEY in context:
        raise VultronValidationError(
            f"VulnerabilityCase '{case_id}' carries no ledgerPosition; a"
            " case's wire form names the ledger position it is a projection"
            " of (SYNC-16-005)"
        )
    data = dict(data)
    data[key] = LedgerPosition(
        log_index=EMPTY_LEDGER_LOG_INDEX,
        entry_hash=data[_present_key(data, "genesis_hash")],
    )
    return data


def _genesis_published(data: dict[str, Any]) -> datetime | None:
    """Return the ``published`` time a genesis hash is computed from.

    The time is never minted here: a case this process authors states its
    ``published`` (the act's instant, ADR-0176), and a received case carries
    the time its sender claimed.  An absent, ``None`` or blank value is a case
    that claimed no time, and the hash is refused rather than computed from a
    clock read, which would give each receiver its own genesis for the same
    case (ISSUE-3257, ADR-0103).
    """
    published_val = data.get("published")
    if published_val is None or published_val == "":
        return None
    if isinstance(published_val, datetime):
        return published_val
    try:
        parsed = datetime.fromisoformat(str(published_val))
    except (ValueError, TypeError):
        return None
    data["published"] = parsed
    return parsed


def compute_genesis_hash_if_missing(data: Any, info: ValidationInfo) -> Any:
    """Compute ``genesis_hash`` at case creation when not explicitly set.

    Uses ``id_``, ``published``, and ``attributed_to`` (the case owner's
    actor id, CP-09-001, CM-02-008) as inputs to
    :func:`~vultron.core.models.case_ledger.compute_genesis_hash`.  This is
    the single definition of a case's genesis hash (CLP-08-002): the owner
    is the anchor on every creation path, including a case a CaseActor
    creates from the owner's ``CaseProposal``, because the CaseActor acts
    as the owner's delegated proxy.  A creator therefore sets
    ``attributed_to`` and lets this validator compute the hash; it does
    not pass a hash of its own.

    ``genesis_hash`` MUST be non-empty after this validator runs — if the
    hash cannot be computed (e.g., ``published`` is absent), a
    :exc:`~vultron.errors.VultronValidationError` is raised (fail-closed
    per CLP-08-003/CLP-08-004).  No-ops when ``genesis_hash`` is already
    set — a received case keeps its sender's hash; one that carries none
    derives it here from its carried inputs (ADR-0103).  A case with no
    ``attributed_to`` is left to the required-field check, which refuses
    it (ARCH-10-001).

    Both spellings of each input are read: the class is its own wire class
    (ARCH-25-003, ADR-0099), so an inbound case arrives as ``attributedTo`` and
    ``genesisHash``.  An omitted or blank ``published`` is never a cue to
    mint one: an authored case states it, and a received case that omits it
    claimed no time (ADR-0103, ADR-0176).

    Spec: CLP-08-002, CLP-08-003.
    """
    if not isinstance(data, dict):
        return data
    attributed_to = _owner(data)
    if not attributed_to or _names_blank_id(data):
        return data  # the field checks refuse the case
    hash_key = _present_key(data, "genesis_hash")
    if not data.get(hash_key):
        data = dict(data)
        # Mint only an absent id: a blank one is refused by ``id_``'s
        # type, not silently replaced (CS-08-001).
        if data.get("id") is None and data.get("id_") is None:
            data["id"] = new_object_id()
        case_id = data.get("id") or data.get("id_")
        published_val = _genesis_published(data)
        if published_val is not None:
            data[hash_key] = compute_genesis_hash(
                case_id=case_id,
                created_at=published_val,
                owner_actor_id=attributed_to,
            )
    if not data.get(hash_key):
        case_id = data.get("id") or data.get("id_") or "<unknown>"
        raise VultronValidationError(
            f"VulnerabilityCase '{case_id}': genesis_hash could not "
            "be computed — 'published' timestamp is required "
            "(CLP-08-003)."
        )
    # The genesis hash is the empty ledger's position, so the position
    # starts here, once the hash is known (SYNC-16-005).
    return _start_ledger_position(data, info)


def init_case_statuses(data: Any, info: ValidationInfo) -> Any:
    """Seed ``case_statuses`` with a default entry when empty.

    Reads both spellings (ARCH-25-002, ADR-0099), and writes the seed under the
    one already present so it is not shadowed by an empty camelCase list.

    Seeding is for a case this process authors.  A received case with no
    status is refused instead (CM-29-004): the seed would carry the
    receiver's clock as the case's first status, a time no sender claimed
    (CLP-15-007).

    Raises:
        ValueError: On the inbound path, when the case carries no status.
    """
    if not isinstance(data, dict):
        return data
    statuses_key = _present_key(data, "case_statuses")
    attributed_to = _owner(data)
    if not attributed_to or _names_blank_id(data):
        return data  # the field checks refuse the case
    if not data.get(statuses_key):
        if (
            isinstance(info.context, dict)
            and INBOUND_CONTEXT_KEY in info.context
        ):
            case_id = data.get("id") or data.get("id_") or "<unknown>"
            raise ValueError(
                f"VulnerabilityCase {case_id!r} carries no caseStatuses; a"
                " received case must carry its status history, and the"
                " receiver does not seed one on its own clock (CM-29-004)"
            )
        # The first status is authored with the case, at the case's own
        # ``published`` (ADR-0176): the model reads no clock.  A case with no
        # time has no time to seed one at, so it is left to the field checks,
        # which report the missing ``published`` and ``updated`` together
        # (EH-07-001) rather than a nested status error.
        if blank_as_none(data.get("published")) is None:
            return data
        data = dict(data)
        # Mint only an absent id: a blank one is refused by ``id_``'s
        # type, not silently replaced (CS-08-001).
        if data.get("id") is None and data.get("id_") is None:
            data["id"] = new_object_id()
        case_id = data.get("id") or data.get("id_")
        data[statuses_key] = [
            CaseStatus(
                context=case_id,
                attributed_to=attributed_to,
                published=data.get("published"),
            )
        ]
    return data
