#!/usr/bin/env python
"""Port factory functions for Vultron inbox dispatch wiring.

Defines the per-semantic port factories and the disjoint semantics
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
from collections.abc import Callable
from typing import Any, cast

from vultron.adapters.driven.sync_activity_adapter import (
    SyncActivityAdapter,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.config.actor import ActorConfig
from vultron.config.app import load_actor_config
from vultron.core.behaviors.call_out.bundles.case_proposal import (
    CASE_PROPOSAL_DETERMINISTIC,
)
from vultron.core.behaviors.call_out.bundles.status_authorization import (
    STATUS_AUTHORIZATION_PERMISSIVE,
)
from vultron.core.models.events import MessageSemantics
from vultron.core.ports.case_outbox import CaseOutboxPersistence
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


PortFactory = Callable[[DataLayer], dict[str, Any]]


def _wire_render_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create the ``WireRenderPort`` every received use case is given.

    Every received tree ends in a guarded ledger commit, and the commit's
    payload snapshot is the AS2 rendering of the received activity, so every
    use case needs the port: core cannot produce that shape itself
    (ARCH-20-001, CLP-07-009).  The adapter is stateless, so *dl* is unused.
    """
    return {"wire_render_port": As2WireRenderAdapter()}


def _sync_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``SyncActivityAdapter`` for the given DataLayer.

    ``dl`` at runtime is an ``DataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (DL-07-002).
    """
    return {"sync_port": SyncActivityAdapter(cast(CaseOutboxPersistence, dl))}


def with_received_baseline_ports(factory: PortFactory) -> PortFactory:
    """Return *factory* extended with the ports every received use case gets.

    Every received tree that names a case runs a guarded ledger commit
    (CLP-10-006).  The commit snapshots the activity as an AS2 rendering, which
    needs the ``WireRenderPort`` (ARCH-20-001, CLP-07-009), and the
    CASE_MANAGER announces the entry to every active participant, which needs
    the ``SyncActivityPort`` (SYNC-02-003).  Both are given to every use case
    rather than to a hand-kept list of those whose trees commit: a list that
    falls behind is how the snapshot path ran portless before #3930, and how
    ``OFFER_ACTOR_TO_CASE``, ``VALIDATE_REPORT`` and
    ``REJECT_INVITE_ACTOR_TO_CASE`` committed without fan-out until #4113.

    This is the **only** source of both ports: no per-semantic factory below
    names either one.  Some semantics use the sync port for more than their
    commit, and still take it from here:

    - ``ANNOUNCE_VULNERABILITY_CASE`` seeds the local case, which anchors the
      per-case genesis hash, and then drains any pre-genesis
      ``Announce(CaseLedgerEntry)`` parked in the gap buffer.  The drain re-runs
      the announce receive path, which sends a ``Reject`` on any residual
      mismatch (SYNC-15-005, #2186, #2180).
    - ``CREATE_CASE_PROPOSAL``'s accept path commits the genesis entries
      natively and fans them out (``CommitNativeLedgerEntriesNode``, ADR-0041
      AC-4); the port is that fan-out's only channel (ARCH-04-004), and its
      outbox order relative to ``Create(VulnerabilityCase)`` is CP-09-009's.
    - ``CLOSE_CASE`` fans out ``case_fully_closed`` (CM-23-002) and renders the
      CASE_MANAGER's own ``RM.CLOSED`` status into the snapshot CM-23-005
      requires (``CommitCaseActorRMClosedEntryNode``, ISSUE-2505).
    """

    def _factory(dl: DataLayer) -> dict[str, Any]:
        return {
            **factory(dl),
            **_sync_port_factory(dl),
            **_wire_render_port_factory(dl),
        }

    return _factory


def _trigger_activity_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Create a ``TriggerActivityAdapter`` from the current DataLayer.

    ``dl`` at runtime is an ``DataLayer`` (satisfies
    ``CaseOutboxPersistence``) — the cast is safe (DL-07-002).
    """
    return {
        "trigger_activity": TriggerActivityAdapter(
            cast(CaseOutboxPersistence, dl)
        )
    }


def _trigger_activity_with_actor_config_port_factory(
    dl: DataLayer,
) -> dict[str, Any]:
    """Create the trigger port and resolve the local ``ActorConfig``.

    Registered for two semantic sets that need the receiver's own
    configuration:

    - ``SUBMIT_REPORT``, so that ``SubmitReportReceivedUseCase`` can honour
      ``auto_create_case=False`` at runtime (CM-15-001, issue #1319).
    - ``INVITE_TO_EMBARGO_ON_CASE`` and ``ACCEPT_INVITE_TO_EMBARGO_ON_CASE``,
      whose CASE_MANAGER stamps every Invite it relays, and the EMB-17-003
      re-invite, with an RSVP deadline measured against its configured
      ``min_rsvp_window`` and ``default_rsvp_window`` (CM-28-012, EP-07-002).

    Falls back to ``actor_config=None`` when ``SeedConfig`` is unavailable:
    report submission keeps the always-create default and the embargo use
    cases stay on ``ActorConfig()``'s defaults.  The sync and wire-render
    ports come from :func:`with_received_baseline_ports`.
    """
    return _with_actor_config(_trigger_activity_port_factory(dl))


def _with_actor_config(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Add the local ``ActorConfig`` to *kwargs* when one resolves."""
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

    The trigger-activity port is needed only on the decline path, where
    ``_EmitRejectCaseProposalNode`` builds ``Reject(as_CaseProposal)`` through
    the shared emit seam (CP-05-002, CP-05-004).  The accept path never reads it.
    The accept path's sync port comes from
    :func:`with_received_baseline_ports`, as a constructor argument, so the
    fan-out stays part of the use case's declared contract.

    ``call_out`` is the admission-policy injection point (CP-05-002).  This
    adapter wires the core DETERMINISTIC bundle, which admits every well-formed
    proposal — the behaviour the service had before the seam existed
    (BT-23-001, BT-23-011).  A deployment with an admission policy substitutes
    its own bundle here, the same way this module wires
    ``STATUS_AUTHORIZATION_PERMISSIVE`` for the received-side status gates.
    """
    return _with_actor_config(
        {
            "call_out": CASE_PROPOSAL_DETERMINISTIC,
            **_trigger_activity_port_factory(dl),
        }
    )


# Semantics whose use cases need the trigger-activity port.  None of these
# sets names the sync or wire-render port: every received use case gets both
# from with_received_baseline_ports, so a semantic that needs only those two is
# in no set at all.
_TRIGGER_ACTIVITY_PORT_SEMANTICS = frozenset(
    {
        MessageSemantics.ACK_REPORT,
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        # ADD_CASE_PARTICIPANT_TO_CASE sends the reinstated participant its
        # direct Add(CaseParticipant) notice and, when it is not bound by
        # the active embargo, that embargo's Invite (CM-31-011, CM-31-013).
        MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE,
        # CLOSE_CASE emits the as:Reject that declines an owner close during a
        # live embargo (CM-23-011).
        MessageSemantics.CLOSE_CASE,
        # CLOSE_REPORT and INVALIDATE_REPORT post the RSH-06-004
        # clarification note on a non-adjacent RM jump (RSH-06-006).
        MessageSemantics.CLOSE_REPORT,
        MessageSemantics.INVALIDATE_REPORT,
        # ENGAGE_CASE and DEFER_CASE build outbound wire activities such as the
        # Announce(VulnerabilityCase) broadcast.
        MessageSemantics.DEFER_CASE,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.OFFER_CASE_PARTICIPANT,
        MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE,
        # REJECT_CASE_LEDGER_ENTRY needs trigger_activity so that
        # AnnounceCaseOnGenesisRejectNode can send Announce(VulnerabilityCase)
        # to a peer that has no case yet before replaying entries (SYNC-15-002).
        MessageSemantics.REJECT_CASE_LEDGER_ENTRY,
        MessageSemantics.REJECT_OFFER_CASE_PARTICIPANT,
        # REMOVE_CASE_PARTICIPANT_FROM_CASE sends the removed participant its
        # direct Remove(CaseParticipant) notice (CM-31-006).
        MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE,
        # UPDATE_CASE broadcasts Announce(VulnerabilityCase) to the
        # participants (CM-06-001); the adapter builds and seals it
        # (VM-08-003).
        MessageSemantics.UPDATE_CASE,
        MessageSemantics.VALIDATE_REPORT,
    }
)

# SUBMIT_REPORT needs the trigger port AND the local actor's ActorConfig so
# that SubmitReportReceivedUseCase can honour auto_create_case=False at
# runtime (CM-15-001, issue #1319).  Kept in a separate set so the disjoint
# guard in make_dispatcher() does not need special-casing.
_SUBMIT_REPORT_SEMANTICS = frozenset({MessageSemantics.SUBMIT_REPORT})

# CREATE_CASE_PROPOSAL needs the local actor's ActorConfig so the CaseActor can
# assign the proposing actor its configured CVD roles (CFG-07-002, CFG-07-004),
# and — since the admission gate landed — the trigger-activity port plus a
# CaseProposalCallOutBundle for the decline path (CP-05-002, CP-05-004).  See
# _case_proposal_port_factory.  Separate set for the same reason as above.
_CASE_PROPOSAL_SEMANTICS = frozenset({MessageSemantics.CREATE_CASE_PROPOSAL})

# INVITE_TO_EMBARGO_ON_CASE and ACCEPT_INVITE_TO_EMBARGO_ON_CASE emit ER when
# P/X/A is set (EMB-01-002, EMB-02-002), so they need the trigger port; the
# CASE_MANAGER's relay and EMB-17-003 re-invite also stamp the RSVP deadline
# from the local ActorConfig (CM-28-012).  See
# _trigger_activity_with_actor_config_port_factory.
_EMBARGO_INVITE_SEMANTICS = frozenset(
    {
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.INVITE_TO_EMBARGO_ON_CASE,
        # OFFER_ACTOR_TO_CASE: the CASE_MANAGER's stub Invite, first or
        # re-invite, is stamped with the same RSVP window (CM-11-014).
        MessageSemantics.OFFER_ACTOR_TO_CASE,
        # ADD_/REMOVE_EMBARGO_EVENT: an embargo change re-issues the
        # CASE_MANAGER's outstanding stub Invites (CM-11-016), each stamped
        # with the same RSVP window (CM-11-014).
        MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE,
        MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE,
        # REJECT_INVITE_TO_EMBARGO_ON_CASE: the owner's Reject after disclosure
        # ends the embargo and so re-issues the stubs the same way.
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    }
)

# Status-authorization call-out seam (ADR-0076, RSH-07-003):
# ADD_CASE_STATUS_TO_CASE and ADD_PARTICIPANT_STATUS_TO_PARTICIPANT both
# carry a StatusAuthorizationCallOutBundle injection point.  The adapter
# wires STATUS_AUTHORIZATION_PERMISSIVE (explicit trusted/demo configuration)
# so the EmbargoTeardownAuthorizationGate and StatusAdoptionGate succeed
# without a live Case Owner approval round-trip.  Production deployments that
# implement the full Offer/Accept/Reject round-trip would inject a different
# bundle here.
_STATUS_AUTH_TRIGGER_SEMANTICS = frozenset(
    {
        # ADD_CASE_STATUS_TO_CASE also needs trigger_activity so that
        # ThreatTerminationBranchNode can dispatch TerminateEmbargo when
        # P/X/A is set (RSH-03-001, ADR-0046).
        MessageSemantics.ADD_CASE_STATUS_TO_CASE,
        # ADD_PARTICIPANT_STATUS_TO_PARTICIPANT triggers the downstream
        # participant-status activity.
        MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT,
    }
)


def _status_auth_trigger_port_factory(dl: DataLayer) -> dict[str, Any]:
    """Inject trigger_activity + STATUS_AUTHORIZATION_PERMISSIVE.

    Used for ``ADD_CASE_STATUS_TO_CASE`` and
    ``ADD_PARTICIPANT_STATUS_TO_PARTICIPANT``.  Wires the permissive
    authorization bundle (RSH-07-003, ADR-0076) so the
    EmbargoTeardownAuthorizationGate and StatusAdoptionGate succeed in this
    adapter's trusted/demo deployment context.
    """
    return {
        **_trigger_activity_port_factory(dl),
        "call_out": STATUS_AUTHORIZATION_PERMISSIVE,
    }
