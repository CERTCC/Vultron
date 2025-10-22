"""Generic activity handler for Vultron API v2."""

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
from typing import Callable

from vultron.api.v2.backend.handlers.registry import (
    AsActivityType,
    ACTIVITY_HANDLER_REGISTRY,
)
from vultron.as_vocab.base.objects.activities.base import as_Activity
from vultron.as_vocab.base.objects.base import as_Object

logger = logging.getLogger(__name__)


class ActivityHandler:
    def __init__(
        self,
        activity_type: type[AsActivityType],
        object_type: type[as_Object] | None = None,
    ):
        self.activity_type = activity_type
        self.object_type = object_type

    def __call__(
        self,
        func: Callable[[str, AsActivityType], None],
    ) -> Callable[[str, AsActivityType], None]:
        ACTIVITY_HANDLER_REGISTRY.register_handler(
            self.activity_type, self.object_type, func
        )

        @wraps(func)
        def wrapper(actor_id: str, obj: AsActivityType):

            # if the object_type is specified, verify it matches
            if self.object_type is not None:
                act_obj = getattr(
                    obj, "as_object"
                )  # ensure obj has as_object attribute

                if act_obj is None:
                    raise ValueError(
                        f"Activity object is None for activity type {self.activity_type.__name__}"
                    )

                if not isinstance(act_obj, self.object_type):
                    raise TypeError(
                        f"Activity object type mismatch: expected {self.object_type.__name__}, got {type(act_obj).__name__}"
                    )

            return func(actor_id, obj)

        return wrapper


# Register the default handler for unknown activities
@ActivityHandler(activity_type=as_Activity, object_type=None)
def handle_unknown(actor_id: str, obj: as_Activity):
    if hasattr(obj, "as_object"):
        # transitive activity
        act_obj = obj.as_object
        logger.warning(
            f"Actor {actor_id} received unknown Activity type {obj.as_type} with object type {act_obj.as_type}: {obj.name}"
        )
    else:
        # intransitive or unknown activity
        logger.warning(
            f"Actor {actor_id} received unknown Activity type {obj.as_type}: {obj.name}"
        )
