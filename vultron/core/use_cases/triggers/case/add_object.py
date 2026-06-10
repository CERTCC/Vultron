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

import logging
from typing import TYPE_CHECKING, Any

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.add_object_trigger_tree import (
    add_object_trigger_bt,
)
from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.core.use_cases.triggers._helpers import (
    resolve_actor,
    resolve_case,
)
from vultron.core.use_cases.triggers.requests import (
    AddObjectToCaseTriggerRequest,
)
from vultron.errors import VultronNotFoundError, VultronValidationError

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


class SvcAddObjectToCaseUseCase:
    """Add any existing AS2 object to a case (general-purpose).

    Reads the object by ``object_id`` from the datalayer, creates a generic
    ``Add(object, target=case)`` activity, and queues it in the actor's
    outbox. The object must already exist; this use case does not create it.

    Type-specific wrappers (e.g., ``SvcAddReportToCaseUseCase``) delegate
    here after performing their own validation (TRIG-10-002).

    Implements: TRIG-10-001.

    BT-15-001 audit: outbound Add(object,target=case) emission and outbox
    queueing are delegated to a trigger-side BT.
    """

    def __init__(
        self,
        dl: CaseOutboxPersistence,
        request: AddObjectToCaseTriggerRequest,
        trigger_activity: "TriggerActivityPort | None" = None,
    ) -> None:
        self._dl = dl
        self._request = request
        self._trigger_activity = trigger_activity

    def execute(self) -> dict[str, Any]:
        actor_id = self._request.actor_id
        case_id = self._request.case_id
        object_id = self._request.object_id
        dl = self._dl

        actor = resolve_actor(actor_id, dl)
        actor_id = actor.id_

        resolve_case(case_id, dl)

        raw = dl.read(object_id)
        if raw is None:
            raise VultronNotFoundError("AS2Object", object_id)

        if self._trigger_activity is None:
            raise RuntimeError(
                "SvcAddObjectToCaseUseCase requires a TriggerActivityPort"
            )

        return _execute_add_object_trigger_bt(
            dl=dl,
            actor_id=actor_id,
            case_id=case_id,
            object_id=object_id,
            trigger_activity=self._trigger_activity,
        )


def _execute_add_object_trigger_bt(
    *,
    dl: CaseOutboxPersistence,
    actor_id: str,
    case_id: str,
    object_id: str,
    trigger_activity: "TriggerActivityPort",
) -> dict[str, Any]:
    """Emit Add(object,target=case) and queue it via BTBridge."""
    result_data: dict[str, Any] = {}

    def _build_activity() -> tuple[str, dict[str, Any]]:
        return trigger_activity.add_object_to_case(
            actor=actor_id,
            object_id=object_id,
            case_id=case_id,
        )

    bridge = BTBridge(datalayer=dl, trigger_activity=trigger_activity)
    tree = add_object_trigger_bt(
        result_out=result_data,
        activity_builder=_build_activity,
    )
    result = bridge.execute_with_setup(
        tree, actor_id=actor_id, case_id=case_id
    )
    if result.status != Status.SUCCESS:
        raise VultronValidationError(
            f"AddObjectToCase failed: {BTBridge.get_failure_reason(tree)}"
        )

    logger.info(
        "Actor '%s' added object '%s' to case '%s'",
        actor_id,
        object_id,
        case_id,
    )
    return {"activity": result_data.get("activity")}
