#!/usr/bin/env python
"""Port factory functions for Vultron inbox dispatch wiring.

Defines the per-semantic port factories and the three disjoint semantics
sets used by
:func:`~vultron.adapters.driving.fastapi.inbox_handler.make_dispatcher`
to inject adapter ports into use cases at dispatch time.
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can
#    Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol
#  Prototype is licensed under a MIT (SEI)-style license, please see
#  LICENSE.md distributed with this Software or contact
#  permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States
#  Government (see Acknowledgments file). This program may include
#  and/or can make use of certain third party source code, object code,
#  documentation and other files ("Third Party Software"). See
#  LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered
#  in the U.S. Patent and Trademark Office by Carnegie Mellon University

import logging
from typing import Any, cast

from vultron.config.actor import ActorConfig
from vultron.config.app import load_actor_config
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer

logger = logging.getLogger(__name__)


def _resolve_actor_config() -> ActorConfig | None:
    """Load the local actor's ``ActorConfig`` via :func:`load_actor_config`.

    Reads actor policy from ``VULTRON_SEED_CONFIG`` YAML or
    ``VULTRON_ACTOR__*`` env vars (CFG-07-005).  Returns ``None`` on any
    load error so callers fall through to the always-create default
    (CM-15-001).
    """
    try:
        return load_actor_config()
    except Exception:
        logger.debug(
            "_resolve_actor_config: load_actor_config failed — "
            "defaulting to auto_create_case=True",
            exc_info=True,
        )
        return None


def _sync_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``SyncActivityAdapter`` for the given DataLayer.

    ``dl`` at runtime is an ``ActorScopedDataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (ARCH-13-002).
    """
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )

    return {"sync_port": SyncActivityAdapter(cast(CaseOutboxPersistence, dl))}


def _trigger_activity_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``TriggerActivityAdapter`` from the current DataLayer.

    ``dl`` at runtime is an ``ActorScopedDataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (ARCH-13-002).
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    return {
        "trigger_activity": TriggerActivityAdapter(
            cast(CaseOutboxPersistence, dl)
        )
    }


def _sync_and_trigger_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create both a ``SyncActivityAdapter`` and a ``TriggerActivityAdapter``.

    Used for semantics that require both ports — specifically
    ``ADD_PARTICIPANT_STATUS_TO_PARTICIPANT``, which must sync the log
    entry to participants *and* trigger the downstream
    participant-status activity.
    """
    return {**_sync_port_factory(dl), **_trigger_activity_port_factory(dl)}


def _submit_report_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create sync+trigger ports and resolve the local ``ActorConfig``.

    Used for ``SUBMIT_REPORT`` so that ``SubmitReportReceivedUseCase``
    receives a populated ``actor_config`` and can honour
    ``auto_create_case=False`` at runtime (CM-15-001, issue #1319).
    Falls back to ``actor_config=None`` when ``SeedConfig`` is unavailable,
    preserving the always-create default.
    """
    kwargs: dict[str, Any] = _sync_and_trigger_port_factory(dl)
    actor_config = _resolve_actor_config()
    if actor_config is not None:
        kwargs["actor_config"] = actor_config
    return kwargs


def _case_proposal_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Resolve the local ``ActorConfig`` for ``CREATE_CASE_PROPOSAL``.

    ``CreateCaseProposalReceivedUseCase`` needs ``default_case_roles`` so the
    CaseActor grants the proposing actor its real CVD roles alongside
    ``CVDRole.CASE_OWNER`` (CFG-07-002, CFG-07-004).  Without it the node would
    have to guess, and labelling a coordinator as ``CVDRole.VENDOR`` makes
    downstream VFD fix-lifecycle checks demand a fix it never produces.

    Falls back to omitting ``actor_config`` when config load fails, leaving the
    receiver with ``CVDRole.CASE_OWNER`` only.
    """
    del dl  # no driven ports required; only local configuration
    actor_config = _resolve_actor_config()
    if actor_config is None:
        return {}
    return {"actor_config": actor_config}


_SYNC_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
        # ANNOUNCE_VULNERABILITY_CASE seeds the local VulnerabilityCase, which
        # anchors the per-case genesis hash and lets AnnounceVulnerabilityCase-
        # ReceivedUseCase drain any pre-genesis Announce(CaseLedgerEntry) it
        # parked in the gap buffer.  The drain re-runs the announce receive path,
        # which sends a Reject on any residual mismatch, so it needs sync_port
        # (SYNC-15-005, #2186, #2180).
        MessageSemantics.ANNOUNCE_VULNERABILITY_CASE,
        MessageSemantics.ADD_NOTE_TO_CASE,
        MessageSemantics.CLOSE_CASE,
        MessageSemantics.INVITE_ACTOR_TO_CASE,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    }
)

_TRIGGER_ACTIVITY_PORT_SEMANTICS = frozenset(
    {
        # ADD_CASE_STATUS_TO_CASE needs trigger_activity so that
        # ThreatTerminationBranchNode (EmbargoTeardownAuthorizationGate) can dispatch TerminateEmbargo
        # activities when P/X/A is set (RSH-03-001, ADR-0046).
        MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        MessageSemantics.OFFER_ACTOR_TO_CASE,
        MessageSemantics.OFFER_CASE_PARTICIPANT,
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
        MessageSemantics.VALIDATE_REPORT,
    }
)

# Semantics that require both a sync port and a trigger-activity port.
# ENGAGE_CASE, DEFER_CASE run BTs that contain CommitCaseLedgerEntryNode,
# which fans out Announce(CaseLedgerEntry) via sync_port (SYNC-02-002),
# AND also need trigger_activity for outbound wire-activity construction
# (e.g. Announce(VulnerabilityCase) broadcast).
# INVITE_TO_EMBARGO_ON_CASE and ACCEPT_INVITE_TO_EMBARGO_ON_CASE need
# trigger_activity to emit ER when P/X/A is set (EMB-01-002, EMB-02-002).
# NOTE: SUBMIT_REPORT is intentionally absent here — it uses
# _submit_report_port_factory (below) which also injects actor_config.
_SYNC_AND_TRIGGER_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACK_REPORT,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.DEFER_CASE,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE,
        # REJECT_CASE_LEDGER_ENTRY needs trigger_activity so that
        # AnnounceCaseOnGenesisRejectNode can send Announce(VulnerabilityCase)
        # to a peer that has no case yet before replaying entries (SYNC-15-002).
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
    }
)

# SUBMIT_REPORT needs sync + trigger ports AND the local actor's ActorConfig
# so that SubmitReportReceivedUseCase can honour auto_create_case=False at
# runtime (CM-15-001, issue #1319).  Kept in a separate set so the disjoint
# guard in make_dispatcher() does not need special-casing.
_SUBMIT_REPORT_SEMANTICS = frozenset({MessageSemantics.SUBMIT_REPORT})

# CREATE_CASE_PROPOSAL needs only the local actor's ActorConfig (no driven
# ports) so the CaseActor can assign the proposing actor its configured CVD
# roles (CFG-07-002, CFG-07-004).  Separate set for the same reason as above.
_CASE_PROPOSAL_SEMANTICS = frozenset({MessageSemantics.CREATE_CASE_PROPOSAL})
