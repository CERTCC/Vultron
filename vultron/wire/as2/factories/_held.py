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

"""Read a held activity as the class a reply embeds.

A reply factory embeds the activity it answers as that activity's pattern
class (an ``Accept`` of an embargo ``Invite`` embeds the embargo-proposal
class).  The answered activity is read back from the actor's own store.  An
activity the actor received is held as intake archived it, in its core form
(``ReceivedActivityRecord``, ADR-0111), which no reply class admits;
:func:`as_answered` validates that form into the class the reply embeds.  A
wire activity is passed through unchanged, so a plain vocabulary activity is
still refused by the reply's own validation.
"""

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from vultron.core.models.base import CoreObject

_Answered = TypeVar("_Answered", bound=BaseModel)


def as_answered(cls: type[_Answered], activity: Any) -> Any:
    """Return a core-form *activity* validated as *cls*; anything else as is.

    Raises:
        pydantic.ValidationError: When a core-form *activity* does not
            validate as *cls*.
    """
    if isinstance(activity, cls) or not isinstance(activity, CoreObject):
        return activity
    return cls.model_validate(
        json.loads(
            activity.model_dump_json(by_alias=True, serialize_as_any=True)
        )
    )
