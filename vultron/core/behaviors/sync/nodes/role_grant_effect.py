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

"""Role-grant application for ``accept_case_participant_role`` (ADR-0039).

An ``Offer(CaseParticipantRole)`` is a proposal, not the grant (#3764); the
grant is the CASE_MANAGER-committed ``accept_case_participant_role`` ledger
entry.  :func:`grant_role_to_target` is the one place that entry becomes case
state — it adds the offered ``CVDRole`` to the target participant's
``case_roles`` on a given replica.  The CASE_MANAGER applies it to its own
replica when it commits the accept
(:class:`~vultron.core.behaviors.case.nodes.delegation.AutoAcceptCaseParticipantRoleNode`);
every other participant applies it by replaying the entry through
:class:`ApplyCaseParticipantRoleGrantFromLedgerNode` in
``create_announce_log_entry_tree`` (CM-02-016, RSH-08-004, ADR-0124).
"""

from __future__ import annotations

import logging
from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.sync.nodes._helpers import (
    _extract_id_from_field,
    _LedgerEffectNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    _SingleEventTypeNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.ports.case_persistence import CasePersistence
from vultron.enums.roles import CVDRole, validate_roles

logger = logging.getLogger(__name__)

_ACCEPT_CASE_PARTICIPANT_ROLE_EVENT = "accept_case_participant_role"


def role_and_target_from_accept_snapshot(
    snapshot: dict,
) -> tuple[CVDRole, str] | None:
    """Read the granted role and target actor id from an ``Accept`` snapshot.

    The ``accept_case_participant_role`` ``payload_snapshot`` is the ``Accept``
    blob; its nested offer carries the grant::

        snapshot["object"]["object"]["role"]   # the CVDRole being granted
        snapshot["object"]["target"]            # the target Actor

    Returns ``(role, target_actor_id)`` or ``None`` when either is absent or
    the role is unparseable.
    """
    offer = snapshot.get("object")
    if not isinstance(offer, dict):
        return None
    target_actor_id = _extract_id_from_field(offer.get("target"))
    role_obj = offer.get("object")
    raw_role = role_obj.get("role") if isinstance(role_obj, dict) else None
    if not target_actor_id or not raw_role:
        return None
    try:
        roles = validate_roles([raw_role])
    except (TypeError, ValueError, KeyError):
        return None
    if not roles:
        return None
    return roles[0], target_actor_id


def grant_role_to_target(
    datalayer: CasePersistence,
    case: VulnerabilityCase,
    target_actor_id: str,
    role: CVDRole,
) -> bool:
    """Grant *role* to *target_actor_id*'s participant on this replica.

    Idempotent (via :meth:`CaseParticipant.add_role`): a role already held is a
    no-op.  Returns ``True`` when the target holds the role afterwards, ``False``
    when the target is not a participant on this replica (a non-fatal skip — the
    grant arrives with the roster the target joins through, or not at all).  No
    ``attributed_to`` is touched, so a single ``save`` is correct (CM-21-004).
    """
    participant_id = case.actor_participant_index.get(target_actor_id)
    participant = datalayer.read(participant_id) if participant_id else None
    if not isinstance(participant, CaseParticipant):
        return False
    if not participant.has_role(role):
        participant.add_role(role)
        datalayer.save(participant)
    return True


class IsAcceptCaseParticipantRoleEventNode(_SingleEventTypeNode):
    """Precondition: SUCCESS when this log entry grants a delegated role.

    Matches the ``accept_case_participant_role`` ``event_type`` in the
    ``RoleGrant`` effect slot of ``AnnounceLogEntryReceivedBT`` (BTND-08-001).
    """

    matched_event_type: ClassVar[str] = _ACCEPT_CASE_PARTICIPANT_ROLE_EVENT


class ApplyCaseParticipantRoleGrantFromLedgerNode(_LedgerEffectNode):
    """Apply an ``accept_case_participant_role`` ledger entry to the replica.

    On a non-CASE_MANAGER replica receiving ``Announce(CaseLedgerEntry)``, adds
    the granted role to the target participant's ``case_roles`` (CM-02-016).  A
    participant MUST NOT mutate ``case_roles`` from an ``Accept`` message
    directly; only the CASE_MANAGER commits the entry and every node learns the
    grant from the ledger (RSH-08-004, ADR-0124).

    Lenient on missing data: an absent case replica, an unreadable role/target,
    or a target that is not yet a participant here is a non-fatal SUCCESS, so it
    does not block the ``Announce`` flow (as
    :class:`ApplyInviteAcceptFromLedgerNode`).
    """

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = self._get_entry()
        case_id = entry.case_id
        parsed = role_and_target_from_accept_snapshot(entry.payload_snapshot)
        if not case_id or parsed is None:
            self.logger.debug(
                "%s: entry missing case_id or a readable role/target"
                " — skipping role-grant apply (non-fatal)",
                self.name,
            )
            return Status.SUCCESS
        role, target_actor_id = parsed

        case = self._resolve_case_replica(case_id)
        if case is None:
            return Status.SUCCESS  # Regime 2 (ADR-0087): partial replica, skip

        if grant_role_to_target(self.datalayer, case, target_actor_id, role):
            self.logger.info(
                "%s: granted %s to '%s' on case '%s' from the ledger"
                " (CM-02-016, ADR-0039)",
                self.name,
                role.value,
                target_actor_id,
                case_id,
            )
        else:
            self.logger.debug(
                "%s: target '%s' is not a participant on this replica of"
                " case '%s' — skipping role grant (non-fatal)",
                self.name,
                target_actor_id,
                case_id,
            )
        return Status.SUCCESS
