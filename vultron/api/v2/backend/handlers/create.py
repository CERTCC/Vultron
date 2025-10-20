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
from functools import wraps
from typing import TypeVar, Callable

from vultron.api.v2.backend.registry import activity_handler
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.objects.object_types import as_Note
from vultron.as_vocab.objects.case_participant import CaseParticipant
from vultron.as_vocab.objects.case_status import CaseStatus, ParticipantStatus
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger("uvicorn.error")


# The global registry of CREATE handlers
CREATE_HANDLERS: dict[type[as_Object], Callable[[str, as_Object], None]] = {}


# Type variable for the model type
T = TypeVar("T", bound=as_Object)


def create_handler(model_cls: type[T]):
    """
    Decorator to register a handler for a given model class in CREATE_HANDLERS.

    Example:
        @create_handler(ParticipantStatus)
        def create_participant_status(actor_id: str, obj: ParticipantStatus):
            ...
    """

    def decorator(
        func: Callable[[str, T], None],
    ) -> Callable[[str, T], None]:

        CREATE_HANDLERS[model_cls] = func

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        logger.debug(
            f"Registered create handler for {model_cls.__name__}: {func.__name__}"
        )
        return wrapper

    return decorator


@create_handler(as_Note)
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


@create_handler(VulnerabilityReport)
def create_vulnerability_report(actor_id: str, obj: as_Create) -> None:
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


@create_handler(VulnerabilityCase)
def create_vulnerability_case(actor_id: str, obj: as_Create) -> None:
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


@create_handler(CaseParticipant)
def create_case_participant(actor_id: str, obj: CaseParticipant) -> None:
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


@create_handler(CaseStatus)
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


@create_handler(ParticipantStatus)
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


def create_unknown(actor_id: str, obj: as_Create) -> None:
    created_obj = obj.as_object
    logger.warning(
        f"Actor {actor_id} received Create activity for unknown object type {created_obj.as_type}: {created_obj.name}"
    )


@activity_handler(as_Create)
def handle_create(actor_id: str, obj: as_Create):
    logger.info(f"Actor {actor_id} received Create activity: {obj.name}")

    # what are we creating?
    created_obj = obj.as_object

    handler = CREATE_HANDLERS.get(created_obj.__class__, create_unknown)

    handler(actor_id, obj)


if __name__ == "__main__":
    for cls, handler in CREATE_HANDLERS.items():
        print(f"Registered handler for {cls.__name__}: {handler.__name__}")
