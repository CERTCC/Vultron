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


"""The base of every trigger verb whose result is an activity.

:class:`SvcActivityTriggerBase` binds the result to :class:`ActivityResult`
and builds it from the captured activity and the emitting actor.
"""

import logging

from vultron.core.models.pending_assertion import (
    suppressed_repeat_reason,
)
from vultron.core.models.use_case_result import ActivityResult
from vultron.core.use_cases.triggers._base.bt import SvcBTTriggerBase

logger = logging.getLogger(__name__)


class SvcActivityTriggerBase(SvcBTTriggerBase[ActivityResult]):
    """BT-backed trigger whose body is the emitted activity and its emitter.

    Binds :class:`SvcBTTriggerBase` to :class:`ActivityResult` and builds it
    from the activity the tree captured (``None`` when it captured nothing)
    and the actor ``_prepare()`` resolved.  Verbs whose body differs bind the
    generic base to their own subtype instead.
    """

    def _build_result(self) -> ActivityResult:
        return ActivityResult(**self._activity_fields())

    def _suppressed_repeat(
        self, case_id: str, semantic_type: str, subject_id: str
    ) -> ActivityResult | None:
        """The no-activity result for a repeat still pending, else ``None``.

        The check half of the pending-assertion pair whose record half is
        :meth:`_record_asserted_activity`: a request about *subject_id* while
        an assertion about it under *semantic_type* is pending is answered
        without re-emitting it (SYNC-11-002).  Judged against
        :attr:`_at`, this act's instant, so the check reads no clock of its
        own (#5591).
        """
        reason = suppressed_repeat_reason(
            self._actor_id, case_id, semantic_type, subject_id, at=self._at
        )
        if reason is None:
            return None
        logger.info("%s: %s", type(self).__name__, reason)
        return ActivityResult(activity=None, emitting_actor_id=self._actor_id)
