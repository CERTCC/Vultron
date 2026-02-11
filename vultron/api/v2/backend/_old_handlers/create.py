"""
Handlers for Create Activities
"""

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

import logging
from functools import partial

from vultron.api.v2.backend.handlers.activity import (
    ActivityHandler,
)
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")

create_handler = partial(ActivityHandler, activity_type=as_Create)


@create_handler(object_type=as_Note)
def create_note(actor_id: str, obj: as_Create) -> None:
    """
    Process a Create(Note) activity.

    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the Note being created.
    Returns:
        None
    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


@create_handler(object_type=VulnerabilityReport)
def rm_create_report(actor_id: str, obj: as_Create) -> None:
    """
    Process a Create(VulnerabilityReport) activity.

    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the VulnerabilityReport being created.

    Returns:
        None

    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


@create_handler(object_type=VulnerabilityCase)
def create_case(actor_id: str, obj: as_Create) -> None:
    """
    Process a Create(VulnerabilityCase) activity.
    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the VulnerabilityCase being created.

    Returns:

    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


@create_handler(object_type=CaseParticipant)
def create_participant(actor_id: str, obj: CaseParticipant) -> None:
    """
    Process a Create(CaseParticipant) activity.

    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the CaseParticipant being created.

    Returns:

    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


@create_handler(object_type=CaseStatus)
def create_case_status(actor_id: str, obj: CaseStatus) -> None:
    """
    Process a Create(CaseStatus) activity.

    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the CaseStatus being created.

    Returns:

    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


@create_handler(object_type=ParticipantStatus)
def create_participant_status(actor_id: str, obj: ParticipantStatus) -> None:
    """
    Process a Create(ParticipantStatus) activity.

    Args:
        actor_id: The ID of the actor performing the Create activity.
        obj: The Create object containing the ParticipantStatus being created.

    Returns:
    """
    created_obj = obj.as_object

    logger.info(
        f"Actor {actor_id} is creating a {created_obj.as_type}: {created_obj.name}"
    )


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
