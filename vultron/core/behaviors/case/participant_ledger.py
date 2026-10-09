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

"""Commit the CASE_MANAGER's own changes to a participant record to the ledger.

Every state change the CASE_MANAGER makes emits a message (ADR-0114,
ADR-0124): the CASE_MANAGER changes its own copy, then commits an entry that
carries the change, and the ledger replicates it.  A replica stores what the
entry carries, as received, and derives nothing.  Each function here commits
one entry for one change, from the very object the CASE_MANAGER holds, so the
ids and times in the entry are the ones in its store.

- :func:`commit_case_participant_created` -- ``create_case_participant``
- :func:`commit_case_participant_updated` -- ``update_case_participant``
- :func:`commit_participant_status_added` -- the existing
  ``add_participant_status_to_participant``

The caller runs inside a CASE_MANAGER-gated tree (BT-17-005); each function
raises ``RuntimeError`` when the commit does not succeed, so the node fails
rather than leaving a change no replica can learn of.
"""

import json
from typing import TYPE_CHECKING

from vultron.core.behaviors.case.ledger_snapshots import (
    build_add_participant_status_snapshot,
    build_create_case_participant_snapshot,
    build_update_case_participant_snapshot,
)
from vultron.core.behaviors.sync.commit_tree import commit_emitted_activity
from vultron.core.models._helpers import _new_urn
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_event_types import (
    CREATE_CASE_PARTICIPANT_EVENT_TYPE,
    UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.ports.case_outbox import CaseOutboxPersistence

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort


def commit_case_participant_created(
    *,
    datalayer: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    participant: CaseParticipant,
    wire_render_port: "WireRenderPort",
) -> None:
    """Commit ``Create(CaseParticipant)`` for the record just created."""
    snapshot = build_create_case_participant_snapshot(
        participant, actor_id, case_id, wire_render_port
    )
    commit_emitted_activity(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        activity_id=participant.id_,
        activity_blob=json.dumps(snapshot),
        event_type=CREATE_CASE_PARTICIPANT_EVENT_TYPE,
    )


def commit_case_participant_updated(
    *,
    datalayer: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    participant: CaseParticipant,
    wire_render_port: "WireRenderPort",
) -> None:
    """Commit ``Update(CaseParticipant)`` for one change to the record."""
    update_id = _new_urn()
    snapshot = build_update_case_participant_snapshot(
        participant, actor_id, case_id, update_id, wire_render_port
    )
    commit_emitted_activity(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        activity_id=update_id,
        activity_blob=json.dumps(snapshot),
        event_type=UPDATE_CASE_PARTICIPANT_EVENT_TYPE,
    )


def commit_participant_status_added(
    *,
    datalayer: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    participant: CaseParticipant,
    status: ParticipantStatus,
    wire_render_port: "WireRenderPort",
) -> None:
    """Commit ``Add(ParticipantStatus)`` for the status just appended."""
    snapshot = build_add_participant_status_snapshot(
        status, participant, actor_id, case_id, wire_render_port
    )
    commit_emitted_activity(
        datalayer=datalayer,
        actor_id=actor_id,
        case_id=case_id,
        activity_id=status.id_,
        activity_blob=json.dumps(snapshot),
        event_type="add_participant_status_to_participant",
    )
