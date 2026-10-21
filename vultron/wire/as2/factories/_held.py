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

"""Embed an answered activity as the class a reply embeds (DL-06-004).

A reply factory embeds the activity it answers as that activity's pattern
class (an ``Accept`` of an embargo ``Invite`` embeds the embargo-proposal
class).  The answered activity is read back from the actor's own store.  An
activity the actor received is held as the body that arrived (ADR-0149); the
adapter's reply seam parses that body, so the activity reaches here as the
parsed wire activity, sealed with the body as its received evidence.
:func:`as_answered` validates it into the class the reply embeds and makes
the copy's AS2 form that body, verbatim, so the reply carries every field the
sender sent (``as_Activity.inlined_as_received``).  An activity the actor
sent, held under its own id, carries no received evidence and is passed to
the reply as it is.
"""

import json
from typing import TypeVar, cast

from pydantic import BaseModel

from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

_Answered = TypeVar("_Answered", bound=BaseModel)


def as_answered(cls: type[_Answered], activity: object) -> _Answered:
    """Return *activity* validated as *cls*, embedded as it was received.

    A received activity (one carrying received evidence) is validated as
    *cls* from its parsed fields, and the copy embeds the received body
    verbatim (:meth:`as_Activity.inlined_as_received`).  Anything else (an
    activity this actor sent) is returned unchanged, typed as *cls* for the
    reply constructor, whose own validation then accepts it or refuses it (a
    plain vocabulary activity, for instance).  So is core's read-only view of
    a received activity: a reply embeds what arrived, never a re-dump of the
    view (ADR-0149).

    Raises:
        pydantic.ValidationError: When *activity* does not validate as *cls*.
    """
    if (
        isinstance(activity, as_Activity)
        and activity.received_evidence_json is not None
    ):
        answered = (
            activity
            if isinstance(activity, cls)
            else validated_as(cls, activity)
        )
        return embedded_as_received(answered, activity)
    return cast(_Answered, activity)


def embedded_as_received(answered: _Answered, received: object) -> _Answered:
    """*answered*, embedded in a reply as the body *received* arrived as.

    *answered* is the reply's own validated copy of the activity it answers;
    *received* is that activity as the reply seam parsed it.  When *received*
    carries received evidence, the copy returned carries it too, and its AS2
    form is that body verbatim (:meth:`as_Activity.inlined_as_received`).
    Otherwise *answered* is returned as it is: an activity this actor sent
    has no received body.
    """
    evidence = (
        received.received_evidence_json
        if isinstance(received, as_Activity)
        else None
    )
    if evidence is None or not isinstance(answered, as_Activity):
        return answered
    answered.seal_received_evidence(evidence)
    return cast(_Answered, answered.inlined_as_received())


def validated_as(cls: type[_Answered], activity: BaseModel) -> _Answered:
    """*activity*'s declared fields, in their AS2 form, validated as *cls*.

    The one way a reply factory coerces the activity it answers into the
    class it embeds: the dump is of the parsed activity, whose keys the parse
    edge already decided, so the validation never meets a key no vocabulary
    names (MV-11-003).

    Raises:
        pydantic.ValidationError: When *activity* does not validate as *cls*.
    """
    return cls.model_validate(
        json.loads(
            activity.model_dump_json(by_alias=True, serialize_as_any=True)
        )
    )
