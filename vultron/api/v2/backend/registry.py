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

from functools import wraps
from typing import TypeVar, Callable, cast

from vultron.as_vocab.base.objects.activities.base import as_Activity

AsActivityType = TypeVar("AsActivityType", bound=as_Activity)
ACTIVITY_HANDLERS: dict[
    type[as_Activity], Callable[[str, as_Activity], None]
] = {}


def activity_handler(
    activity_type: type[AsActivityType],
) -> Callable[
    [Callable[[str, AsActivityType], None]], Callable[[str, as_Activity], None]
]:
    def decorator(
        func: Callable[[str, AsActivityType], None],
    ) -> Callable[[str, as_Activity], None]:
        @wraps(func)
        def wrapper(actor_id: str, obj: AsActivityType):
            if not isinstance(obj, activity_type):
                raise TypeError(
                    f"Handler for {activity_type.__name__} received wrong type: {obj.__class__.__name__}"
                )
            return func(actor_id, cast(AsActivityType, obj))

        ACTIVITY_HANDLERS[activity_type] = wrapper
        return wrapper

    return decorator
