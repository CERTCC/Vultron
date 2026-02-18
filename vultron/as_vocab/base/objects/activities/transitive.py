#!/usr/bin/env python
"""This module provides transitive activity classes"""

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

from pydantic import Field, model_validator

from vultron.enums import as_TransitiveActivityType as TA_type
from vultron.as_vocab.base.objects.activities.base import (
    as_Activity as Activity,
)
from vultron.as_vocab.base.objects.base import as_ObjectRef
from vultron.as_vocab.base.registry import activitystreams_activity
from vultron.as_vocab.base.utils import name_of


@activitystreams_activity
class as_TransitiveActivity(Activity):
    """A transitive activity is an activity that has an object.
    ActivityPub doesn't define transitive activities separately from activities, but we do it here for convenience.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity>
    """

    as_object: as_ObjectRef = Field(None, alias="object")

    @model_validator(mode="after")
    def set_name(self):
        """Set a default name if none is provided"""
        if self.name is not None:
            return self

        parts = []
        if self.actor is not None:
            parts.append(name_of(self.actor))
        if self.as_type is not None:
            parts.append(self.as_type)
        if self.as_object is not None:
            parts.append(name_of(self.as_object))
        if self.origin is not None:
            parts.extend(("from", self.origin))
        if self.target is not None:
            parts.extend(("to", self.target))
        if self.instrument is not None:
            parts.extend(("using", self.instrument))

        if parts:
            self.name = " ".join([str(part) for part in parts])

        return self


@activitystreams_activity
class as_Like(as_TransitiveActivity):
    """The actor likes, recommends or endorses the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-like>
    """

    as_type: TA_type = Field(default=TA_type.LIKE, alias="type")


@activitystreams_activity
class as_Ignore(as_TransitiveActivity):
    """The actor is ignoring the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-ignore>
    """

    as_type: TA_type = Field(default=TA_type.IGNORE, alias="type")


@activitystreams_activity
class as_Block(as_Ignore):
    """The actor is blocking the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-block>
    """

    as_type: TA_type = Field(default=TA_type.BLOCK, alias="type")


@activitystreams_activity
class as_Offer(as_TransitiveActivity):
    """The actor is offering the object. If specified, the origin indicates the context from which the object originated.
    The target indicates the entity to which the object is being offered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-offer>
    """

    as_type: TA_type = Field(default=TA_type.OFFER, alias="type")


@activitystreams_activity
class as_Invite(as_Offer):
    """The actor is requesting that the target accept the object. The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-invite>
    """

    as_type: TA_type = Field(default=TA_type.INVITE, alias="type")


@activitystreams_activity
class as_Flag(as_TransitiveActivity):
    """The actor is flagging the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-flag>
    """

    as_type: TA_type = Field(default=TA_type.FLAG, alias="type")


@activitystreams_activity
class as_Remove(as_TransitiveActivity):
    """The actor removes the object from the target. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-remove>
    """

    as_type: TA_type = Field(default=TA_type.REMOVE, alias="type")


@activitystreams_activity
class as_Undo(as_TransitiveActivity):
    """The actor is undoing the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-undo>
    """

    as_type: TA_type = Field(default=TA_type.UNDO, alias="type")


@activitystreams_activity
class as_Create(as_TransitiveActivity):
    """The actor is creating the object. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-create>
    """

    as_type: TA_type = Field(default=TA_type.CREATE, alias="type")


@activitystreams_activity
class as_Delete(as_TransitiveActivity):
    """The actor is deleting the object. If specified, the origin indicates the context from which the object was deleted.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-delete>
    """

    as_type: TA_type = Field(default=TA_type.DELETE, alias="type")


@activitystreams_activity
class as_Move(as_TransitiveActivity):
    """The actor is moving the object from the origin to the target.
    If the origin or target are not specified, either can be determined by context.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-move>
    """

    as_type: TA_type = Field(default=TA_type.MOVE, alias="type")


@activitystreams_activity
class as_Add(as_TransitiveActivity):
    """The actor is adding the object to the target. If the target is not specified, it must be determined by context.
    The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-add>
    """

    as_type: TA_type = Field(default=TA_type.ADD, alias="type")


@activitystreams_activity
class as_Join(as_TransitiveActivity):
    """The actor has joined the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-join>
    """

    as_type: TA_type = Field(default=TA_type.JOIN, alias="type")


@activitystreams_activity
class as_Update(as_TransitiveActivity):
    """The actor has updated the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-update>
    """

    as_type: TA_type = Field(default=TA_type.UPDATE, alias="type")


@activitystreams_activity
class as_Listen(as_TransitiveActivity):
    """The actor has listened to the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-listen>
    """

    as_type: TA_type = Field(default=TA_type.LISTEN, alias="type")


@activitystreams_activity
class as_Leave(as_TransitiveActivity):
    """The actor has left the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-leave>
    """

    as_type: TA_type = Field(default=TA_type.LEAVE, alias="type")


@activitystreams_activity
class as_Announce(as_TransitiveActivity):
    """The actor is calling the target's attention to the object. The origin typically has no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-announce>
    """

    as_type: TA_type = Field(default=TA_type.ANNOUNCE, alias="type")


@activitystreams_activity
class as_Follow(as_TransitiveActivity):
    """The actor is "following" the object.
    Following is defined in the sense commonly used in Social systems in which the actor is interested in any activity
    performed by or on the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-follow>
    """

    as_type: TA_type = Field(default=TA_type.FOLLOW, alias="type")


@activitystreams_activity
class as_Accept(as_TransitiveActivity):
    """The actor accepts the object. The target property can be used in certain circumstances to indicate the context into
    which the object has been accepted.
    """

    as_type: TA_type = Field(default=TA_type.ACCEPT, alias="type")


@activitystreams_activity
class as_TentativeAccept(as_Accept):
    """The actor tentatively accepts the object.
    A specialization of Accept indicating that the acceptance is tentative.
    """

    as_type: TA_type = Field(default=TA_type.TENTATIVE_ACCEPT, alias="type")


@activitystreams_activity
class as_View(as_TransitiveActivity):
    """The actor has viewed the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-view>
    """

    as_type: TA_type = Field(default=TA_type.VIEW, alias="type")


@activitystreams_activity
class as_Dislike(as_TransitiveActivity):
    """The actor dislikes the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-dislike>
    """

    as_type: TA_type = Field(default=TA_type.DISLIKE, alias="type")


@activitystreams_activity
class as_Reject(as_TransitiveActivity):
    """The actor rejects the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-reject>
    """

    as_type: TA_type = Field(default=TA_type.REJECT, alias="type")


@activitystreams_activity
class as_TentativeReject(as_Reject):
    """A specialization of Reject indicating that the rejection is tentative.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tentativereject>
    """

    as_type: TA_type = Field(default=TA_type.TENTATIVE_REJECT, alias="type")


@activitystreams_activity
class as_Read(as_TransitiveActivity):
    """The actor has read the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-read>
    """

    as_type: TA_type = Field(default=TA_type.READ, alias="type")


def main():
    from vultron.as_vocab.base.utils import print_activity_examples

    print_activity_examples()


if __name__ == "__main__":
    main()
