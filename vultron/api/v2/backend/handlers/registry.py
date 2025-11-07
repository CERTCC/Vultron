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
from typing import TypeVar, Callable, TypeAlias, Optional

from pydantic import BaseModel, Field

from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.base import as_Object

logger = logging.getLogger(__name__)

AsActivityType = TypeVar("AsActivityType", bound=as_Activity)
AsObjectType = TypeVar("AsObjectType", bound=as_Object)

# a dict of object type to handler function
ObjectHandlerMap: TypeAlias = dict[
    Optional[str], Callable[[str, as_Activity], None]
]

# a dict of activity type to ObjectHandlerMap
# which basically makes it a two-dimensional dict where
# the first key is the activity type and the second key is the object type
HandlerRegistry: TypeAlias = dict[str, ObjectHandlerMap]


# we actually need a two-dimensional registry: (activity type, object type) -> handler
class ActivityHandlerRegistry(BaseModel):
    """
    Registry for activity handlers based on activity type and object type.
    Intransitive activities can use None as the object type.
    """

    handlers: HandlerRegistry = Field(default_factory=dict)

    def register_handler(
        self,
        activity_type: type[AsActivityType],
        object_type: type[AsObjectType] | None,
        handler: Callable[[str, AsActivityType], None],
    ) -> None:

        activity_key = activity_type.__name__.lstrip("as_")

        # ensure that activity_type is an Activity in the VOCABULARY
        if activity_key not in VOCABULARY.activities:
            raise ValueError(
                f"Unknown activity type: {activity_type.__name__}"
            )

        object_key = None

        if object_type is not None:
            object_key = object_type.__name__.lstrip("as_")
            # ensure that object_type is in the VOCABULARY (could be any object)

            if object_key not in VOCABULARY:
                raise ValueError(
                    f"Unknown object type: {object_type.__name__}"
                )

        if activity_key not in self.handlers:
            self.handlers[activity_key] = {}

        # throw an error if there is already a handler for this activity_type and object_type
        if object_type in self.handlers[activity_key]:
            raise ValueError(
                f"Handler already registered for activity type {activity_type.__name__} and object type {object_type.__name__ if object_type else 'None'}"
            )

        self.handlers[activity_key][object_key] = handler


# instantiate the global registry
ACTIVITY_HANDLER_REGISTRY = ActivityHandlerRegistry()


def get_activity_handler(
    activity: as_Activity,
) -> Callable[[str, AsActivityType], None]:
    """Get the handler for a given activity.
    Args:
        activity: The activity object to get the handler for.
    Returns:
        The handler function.
    Raises:
        ValueError: If no handler is found for the activity.
    """
    # get keys
    a_key = activity.as_type

    if a_key in ACTIVITY_HANDLER_REGISTRY.handlers:
        logger.debug(f"Found specific handlers for activity type {a_key}")
        hdlrs = ACTIVITY_HANDLER_REGISTRY.handlers[a_key]
    elif None in ACTIVITY_HANDLER_REGISTRY.handlers:
        logger.info(f"Using generic handler for {a_key}")
        hdlrs = ACTIVITY_HANDLER_REGISTRY.handlers[None]
    else:
        logger.error(
            f"No handlers (specific or generic) for activity type {a_key}"
        )
        raise ValueError(
            f"No handlers (including generic) registered for activity type {a_key}"
        )

    # short-circuit for intransitive activities
    if not hasattr(activity, "as_object"):
        try:
            handler = hdlrs[None]
        except KeyError:
            raise ValueError(
                f"No handlers (including generic) registered for activity type {a_key} and intransitive object"
            )
        return handler

    # transitive activity
    # as_object might be a string though
    if isinstance(activity.as_object, str):
        o_key = None
    else:
        o_key = activity.as_object.as_type

    try:
        handler = hdlrs[o_key]
    except KeyError:
        try:
            handler = hdlrs[None]
        except KeyError:
            raise ValueError(
                f"No handlers (including generic) registered for activity type {a_key} and object type {o_key}"
            )

    return handler
