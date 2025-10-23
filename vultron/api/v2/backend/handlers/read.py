#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Read Activity Handlers
"""
import logging
from functools import partial

from vultron.api.v2.backend.handlers.activity import ActivityHandler
from vultron.as_vocab.base.objects.activities.transitive import (
    as_Read,
)
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")

read_handler = partial(ActivityHandler, activity_type=as_Read)


@read_handler(object_type=VulnerabilityReport)
def rm_read_report(actor_id: str, activity: as_Read) -> None:
    """
    Process a Read(VulnerabilityReport) activity.

    Args:
        actor_id: The ID of the actor performing the Read activity.
        activity: The Read object containing the VulnerabilityReport being read.
    Returns:
        None
    """
    read_obj = activity.as_object

    logger.info(
        f"Actor {actor_id} has read {read_obj.as_type}: {read_obj.name}"
    )

    # TODO if the actor is a vendor on a case, ParticipantStatus -> V


def main():
    from vultron.api.v2.backend.handlers.registry import (
        ACTIVITY_HANDLER_REGISTRY,
    )

    for k, v in ACTIVITY_HANDLER_REGISTRY.handlers.items():
        for ok, ov in v.items():
            if ok is None:
                print(f"{k.__name__}: None -> {ov.__name__}")
            else:
                print(f"{k.__name__}: {ok.__name__} -> {ov.__name__}")


if __name__ == "__main__":
    main()
