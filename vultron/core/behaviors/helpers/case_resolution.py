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

"""Case-resolution disposition policy for BT nodes (ADR-0087)."""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.helpers.messages import DATALAYER_UNAVAILABLE
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.models.case import VulnerabilityCase

# ---------------------------------------------------------------------------
# Case-resolution disposition policy (ADR-0087)
# ---------------------------------------------------------------------------
#
# One canonical decision about "what to do when a case evaporates underneath a
# BT node", not a per-site accident.  A node coordinating an *existing* case
# has exactly one of three dispositions when ``read_case`` returns nothing, and
# each has a single shared entry point so the disposition is chosen by role,
# not re-litigated at every call site (#3101):
#
#   Regime 1 — Authoritative coordination (default).  Guards, acceptance
#     checks, ledger commits, append/emit nodes: the case MUST exist.  Its
#     absence mid-coordination is an anomaly, so ``require_case`` reports one
#     canonical FAILURE at ``error`` level.
#   Regime 2 — Replica-apply of a remote ledger entry.  ``resolve_case_replica``
#     treats a missing *local* case as normal (partial replica, SYNC-02-002 /
#     ADR-0073) and lets the caller SUCCESS-skip.
#   Regime 3 — Case-under-construction (proposal / offer-received flows).
#     Absence precedes a create and is handled inline by those nodes; they use
#     neither helper.


def require_case(
    node: py_trees.behaviour.Behaviour,
    case_id: "str | None",
) -> "tuple[VulnerabilityCase, Status | None]":
    """Resolve a case that MUST exist for authoritative coordination (Regime 1).

    The canonical case-resolution helper for BT nodes that coordinate an
    *existing* case: idempotency/invariant guards, acceptance checks,
    ledger commits, append nodes, emit nodes.  A case that cannot be resolved
    mid-coordination is an anomaly — a concurrent deletion or a caller bug —
    never a routine branch (ADR-0087).  It therefore reports one canonical
    outcome, ``Status.FAILURE`` at ``error`` log level with a canonical
    ``feedback_message``, replacing the per-site drift (silent / ``debug`` /
    ``warning``) that #3101 catalogued.

    Returns ``(case, None)`` when the case resolves, or
    ``(None, Status.FAILURE)`` when ``case_id`` is missing/empty or the record
    is absent or not a :class:`VulnerabilityCase`.  On the failure tuple the
    caller MUST return the supplied status::

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure
        # `case` is a VulnerabilityCase from here on

    The first tuple element is annotated ``VulnerabilityCase`` (not
    ``Optional``) so callers need no ``assert``/narrowing after the guard: the
    contract is that ``case`` is only read when ``failure is None``.  On the
    failure tuple it is really ``None``, hence the ``type: ignore`` on the
    failure returns below — the sole place that unsoundness is contained.

    The isinstance guard treats a non-``VulnerabilityCase`` record (e.g. a
    vocabulary-registry mismatch) as not-found, subsuming the defensive check
    formerly hand-rolled in ``_CsStatusGuardBase._resolve_case``.  The
    DataLayer-missing branch mirrors :meth:`_require_datalayer`.

    Two disposition regimes deliberately do NOT use this helper (ADR-0087):
    replica-apply of remote ledger entries (:func:`resolve_case_replica`,
    SYNC-02-002 / ADR-0073) and case-under-construction flows where absence
    legitimately precedes a create.
    """
    log = node_logger(node)
    datalayer = getattr(node, "datalayer", None)
    if datalayer is None:
        node.feedback_message = DATALAYER_UNAVAILABLE
        log.error("%s: %s", node.name, node.feedback_message)
        return None, Status.FAILURE  # type: ignore[return-value]
    if not case_id:
        node.feedback_message = "no case_id available to resolve case"
        log.error("%s: %s", node.name, node.feedback_message)
        return None, Status.FAILURE  # type: ignore[return-value]
    case = datalayer.read_case(case_id)
    if not isinstance(case, VulnerabilityCase):
        node.feedback_message = f"case '{case_id}' not found in DataLayer"
        log.error("%s: %s", node.name, node.feedback_message)
        return None, Status.FAILURE  # type: ignore[return-value]
    return case, None


def resolve_case_replica(
    node: py_trees.behaviour.Behaviour,
    case_id: "str | None",
) -> "VulnerabilityCase | None":
    """Resolve a case for replica-apply of a remote ledger entry (Regime 2).

    Apply-from-ledger nodes run against a *partial* local replica whose case
    row may legitimately be absent (SYNC-02-002, ADR-0073 per-actor storage):
    the local store simply does not mirror that case yet.  Absence here is NOT
    an error — the caller returns ``Status.SUCCESS`` and skips the apply so the
    surrounding Announce processing is never blocked.  This logs at ``debug``
    and sets no failure ``feedback_message``.

    Returns the case, or ``None`` when it is absent/unresolvable (caller skips).
    Distinct from :func:`require_case` solely in disposition (ADR-0087): the
    same lookup, the opposite verdict on absence.
    """
    datalayer = getattr(node, "datalayer", None)
    if datalayer is None:
        return None
    if not case_id:
        return None
    case = datalayer.read_case(case_id)
    if not isinstance(case, VulnerabilityCase):
        log = node_logger(node)
        log.debug(
            "%s: case '%s' not present in local replica;"
            " skipping apply (SYNC-02-002)",
            node.name,
            case_id,
        )
        return None
    return case
