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
from typing import TypeVar, Callable, TypeAlias, Optional

from pydantic import BaseModel, Field

from vultron.as_vocab import VOCABULARY
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.base import as_Object

AsActivityType = TypeVar("AsActivityType", bound=as_Activity)
AsObjectType = TypeVar("AsObjectType", bound=as_Object)

# a dict of object type to handler function
ObjectHandlerMap: TypeAlias = dict[
    Optional[type[as_Object]], Callable[[str, as_Activity], None]
]

# a dict of activity type to ObjectHandlerMap
# which basically makes it a two-dimensional dict where
# the first key is the activity type and the second key is the object type
HandlerRegistry: TypeAlias = dict[type[as_Activity], ObjectHandlerMap]


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

        key = activity_type.__name__.lstrip("as_")

        # ensure that activity_type is in the VOCABULARY
        if key not in VOCABULARY.activities:
            raise ValueError(
                f"Unknown activity type: {activity_type.__name__}"
            )

        if object_type is not None:
            key = object_type.__name__.lstrip("as_")
            # ensure that object_type is in the VOCABULARY
            if key not in VOCABULARY.objects:
                raise ValueError(
                    f"Unknown object type: {object_type.__name__}"
                )

        if activity_type not in self.handlers:
            self.handlers[activity_type] = {}

        # throw an error if there is already a handler for this activity_type and object_type
        if object_type in self.handlers[activity_type]:
            raise ValueError(
                f"Handler already registered for activity type {activity_type.__name__} and object type {object_type.__name__ if object_type else 'None'}"
            )

        self.handlers[activity_type][object_type] = handler

    def get_handler(
        self, activity: as_Activity
    ) -> Callable[[str, AsActivityType], None] | None:
        """
        Get the handler for a given activity type and object type.
        Args:
            activity: The activity object to get the handler for.

        Returns:
            The handler function if found, otherwise None.

        """
        activity_type = type(activity)
        obj_handlers = self.handlers.get(activity_type)

        if obj_handlers is None:
            # short-circuit if no handlers for this activity type
            default = self.handlers.get(as_Activity, None)
            return default

        object_type = getattr(activity, "as_object", None)

        if object_type is None:
            # intransitive activity, look for None object type handler
            # return it if found, otherwise None
            handler = obj_handlers.get(None, None)

            if handler is not None:
                return handler

            # return the default handler for unknown activities
            default = self.handlers.get(as_Activity, None)
            return default

        # if you get here, activity_type is transitive
        # and object_type is the type of the as_object
        object_type = type(object_type)

        if object_type is not None:
            # look for the specific object type handler
            # return it if found
            # otherwise try the generic handler for this activity type
            handler = obj_handlers.get(object_type, None)
            if handler is not None:
                return handler
            # handler is None, try generic
            # if no generic, will return None
            return obj_handlers.get(None, None)


# instantiate the global registry
ACTIVITY_HANDLER_REGISTRY = ActivityHandlerRegistry()
