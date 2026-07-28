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

"""Dead-letter storage BT leaf node.

Provides a leaf action node that constructs and persists a
``DeadLetterRecord`` for an activity whose ``object_`` URI could not be
resolved after rehydration.

Per ``specs/semantic-extraction.yaml`` SE-04-002, SE-04-003.
"""

from py_trees.common import Status

from vultron.core.behaviors.helpers import DataLayerAction
from vultron.core.models.dead_letter import DeadLetterRecord
from vultron.core.models.events.unknown import UnresolvableObjectReceivedEvent


class StoreDeadLetterRecordNode(DataLayerAction):
    """Build and persist a ``DeadLetterRecord`` for an unresolvable activity.

    Extracts the unresolvable URI, actor ID, activity ID and type from the
    event, constructs a ``DeadLetterRecord``, and stores it via
    ``self.datalayer.save()``.

    Returns ``SUCCESS`` on persist, ``FAILURE`` if the DataLayer is
    unavailable.
    """

    def __init__(
        self,
        request: UnresolvableObjectReceivedEvent,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._request = request

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        request = self._request
        unresolvable_uri = request.object_id or ""
        activity_summary = (
            request.activity.model_dump(by_alias=True, exclude_none=True)
            if request.activity is not None
            else None
        )
        record = DeadLetterRecord(
            unresolvable_uri=unresolvable_uri,
            actor_id=request.actor_id,
            activity_id=request.activity_id,
            activity_type=request.activity_type,
            activity_summary=activity_summary,
        )
        self.datalayer.save(record)
        self.logger.info(
            "%s: stored dead-letter record for unresolvable URI '%s'"
            " (activity '%s', actor '%s')",
            self.name,
            unresolvable_uri,
            request.activity_id,
            request.actor_id,
        )
        return Status.SUCCESS
