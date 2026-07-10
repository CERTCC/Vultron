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
from typing import TYPE_CHECKING, Any, cast

import yaml
from pydantic import ValidationError

from vultron.core.models.events import MessageSemantics
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.ports.datalayer import DataLayer
from vultron.demo.seed_config import SeedConfig

if TYPE_CHECKING:
    from vultron.core.models.actor_config import ActorConfig

logger = logging.getLogger(__name__)


def _resolve_actor_config() -> "ActorConfig | None":
    """Load the local actor's ``ActorConfig`` from ``SeedConfig``.

    Reads ``VULTRON_SEED_CONFIG`` (path) or the individual
    ``VULTRON_ACTOR_*`` env vars via :func:`~vultron.demo.seed_config.SeedConfig.load`.
    Returns ``None`` on any load error so callers fall through to the
    always-create default (CM-15-001).
    """
    try:
        return SeedConfig.load().local_actor
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        ValidationError,
        yaml.YAMLError,
    ):
        logger.debug(
            "_resolve_actor_config: SeedConfig unavailable — "
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


_SYNC_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.ANNOUNCE_CASE_LEDGER_ENTRY,
        MessageSemantics.ADD_NOTE_TO_CASE,
        MessageSemantics.CLOSE_CASE,
        MessageSemantics.INVITE_ACTOR_TO_CASE,
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
    }
)

_TRIGGER_ACTIVITY_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACCEPT_CASE_MANAGER_ROLE,
        MessageSemantics.OFFER_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_ACTOR_RECOMMENDATION,
        MessageSemantics.REJECT_ACTOR_RECOMMENDATION,
        MessageSemantics.VALIDATE_REPORT,
    }
)

# Semantics that require both a sync port and a trigger-activity port.
# ENGAGE_CASE, DEFER_CASE run BTs that contain CommitCaseLedgerEntryNode,
# which fans out Announce(CaseLedgerEntry) via sync_port (SYNC-02-002),
# AND also need trigger_activity for outbound wire-activity construction
# (e.g. Announce(VulnerabilityCase) broadcast).
# NOTE: SUBMIT_REPORT is intentionally absent here — it uses
# _submit_report_port_factory (below) which also injects actor_config.
_SYNC_AND_TRIGGER_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACK_REPORT,
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.DEFER_CASE,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.OFFER_CASE_MANAGER_ROLE,
    }
)

# SUBMIT_REPORT needs sync + trigger ports AND the local actor's ActorConfig
# so that SubmitReportReceivedUseCase can honour auto_create_case=False at
# runtime (CM-15-001, issue #1319).  Kept in a separate set so the disjoint
# guard in make_dispatcher() does not need special-casing.
_SUBMIT_REPORT_SEMANTICS = frozenset({MessageSemantics.SUBMIT_REPORT})
