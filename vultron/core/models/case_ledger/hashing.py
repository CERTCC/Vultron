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


"""The per-case genesis hash and the canonical hash of ledger content.

Canonical serialization is deterministic JSON (``sort_keys=True``, compact
separators, UTF-8).  It is **not** RFC 8785 JCS: it escapes non-ASCII text
and writes numbers in Python's form, so it differs from the JCS form that
SYNC-01-008 requires.  The gap is #3659.
"""

import hashlib
import json
from datetime import datetime
from typing import Any

from vultron.core.models._helpers import (
    format_timestamp,
)

# ---------------------------------------------------------------------------
# Per-case genesis hash (CLP-08-001, CLP-08-002)
# ---------------------------------------------------------------------------


def compute_genesis_hash(
    case_id: str, created_at: datetime, owner_actor_id: str
) -> str:
    """Return the per-case genesis hash for a case ledger.

    Derived as ``SHA-256(case_id + "|" + format_timestamp(created_at) + "|" +
    owner_actor_id)``, where ``case_id`` is the canonical case URI,
    ``created_at`` is the case creation UTC timestamp, and
    ``owner_actor_id`` is the case owner's actor id
    (``VulnerabilityCase.attributed_to``).

    The anchor is the **owner**, not the CaseActor that may create the case
    on the owner's behalf: the CaseActor is the owner's delegated proxy, so a
    case created by its owner and one created by a CaseActor from the owner's
    ``CaseProposal`` are anchored to the same identity (CLP-08-002).

    This is the one formula.  ``VulnerabilityCase`` calls it from its
    construction validator whenever no ``genesis_hash`` is supplied, so every
    creation path that sets ``attributed_to`` gets the same value.  A replica
    keeps the hash it receives; a received case that carries none derives it
    here from its carried ``id``, ``published`` and ``attributedTo``
    (ADR-0103), which the owner anchor makes agree with the sender.

    This anchors each case ledger to its origin identity and timestamp,
    replacing the former global zero-hash sentinel (CLP-08-001,
    CLP-08-002).

    Args:
        case_id: Canonical URI of the :class:`VulnerabilityCase`.
        created_at: TZ-aware UTC datetime at case creation.
        owner_actor_id: Actor id of the case owner (``attributed_to``).

    Returns:
        64-character lowercase hex SHA-256 digest string.

    Spec: CLP-08-001, CLP-08-002.
    """
    raw = f"{case_id}|{format_timestamp(created_at)}|{owner_actor_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Canonical serialization helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(data: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for *data*.

    Uses ``sort_keys=True`` and compact separators to produce a deterministic
    form for cryptographic hashing.  This form is not RFC 8785 JCS, which
    SYNC-01-008 requires (#3659).
    A ``datetime`` is written in the fixed form of :func:`format_timestamp`
    (CS-13-007); any other non-JSON-native value is refused.  Snapshots
    reach here as JSON-mode dumps, so neither normally occurs.

    Args:
        data: A dict whose values are JSON-serialisable.

    Returns:
        Compact UTF-8-encoded JSON bytes with sorted keys.
    """
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=_canonical_default,
    ).encode("utf-8")


def _canonical_default(value: Any) -> str:
    """Write a ``datetime`` in the fixed form; refuse anything else."""
    if isinstance(value, datetime):
        return format_timestamp(value)
    raise TypeError(
        f"Object of type {type(value).__name__} has no canonical JSON form"
    )


def _sha256_hex(data: dict[str, Any]) -> str:
    """Return the lowercase hex SHA-256 digest of the canonical JSON of *data*.

    Args:
        data: A dict to canonicalise and hash.

    Returns:
        64-character lowercase hex SHA-256 digest string.
    """
    return hashlib.sha256(_canonical_bytes(data)).hexdigest()
