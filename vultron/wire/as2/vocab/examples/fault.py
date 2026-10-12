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
"""Example ``Create(ProcessingFault)``: a message received but not understood."""

from vultron.core.models.fault_classes import (
    VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
)
from vultron.wire.as2.factories.fault import create_processing_fault_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.examples._base import _CASE_ACTOR, vendor
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault


def create_processing_fault() -> as_Create:
    """The Case Manager refuses a status assertion naming an impossible state.

    The fault points at the failed activity by ``inReplyTo`` and names its
    failure class by URI, with no implementation diagnostics (ASK-07-003,
    ASK-07-004, ASK-07-006).
    """
    _vendor = vendor()
    fault = as_ProcessingFault(
        failure_class=VULTRON_FAILURE_STATUS_ASSERTION_REFUSED_IMPOSSIBLE_STATE,
        in_reply_to=(
            "https://vultron.example/cases/1/participants/vendor/status/9"
        ),
    )
    return create_processing_fault_activity(
        actor=_CASE_ACTOR.id_,
        fault=fault,
        to=[_vendor.id_],
    )
