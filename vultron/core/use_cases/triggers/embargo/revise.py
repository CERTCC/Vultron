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

"""Embargo revision proposal trigger use case."""

import logging

from vultron.core.behaviors.embargo.trigger_tree import (
    propose_embargo_revision_trigger_bt,
)
from vultron.core.use_cases.triggers.embargo._terms import (
    SvcOfferEmbargoTermsBase,
)

logger = logging.getLogger(__name__)


class SvcProposeEmbargoRevisionUseCase(SvcOfferEmbargoTermsBase):
    _tree_factory = staticmethod(propose_embargo_revision_trigger_bt)

    def _log_lifecycle_result(self) -> None:
        lr = self._lifecycle_result
        logger.info(
            "Actor '%s' proposed embargo revision '%s' on case '%s'"
            " (EM %s → %s)",
            self._actor_id,
            self._embargo.id_,
            self._case.id_,
            lr.em_before,
            lr.em_after,
        )
