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

from vultron.wire.as2.enums import as_TransitiveActivityType as TA_type
from vultron.wire.as2.vocab.base.objects.activities.base import (
    as_Activity as Activity,
)
from vultron.wire.as2.vocab.base.objects.base import as_ObjectRef
from vultron.wire.as2.vocab.base.utils import name_of


class as_TransitiveActivity(Activity):
    """A transitive activity is an activity that has an object.
    ActivityPub doesn't define transitive activities separately from activities, but we do it here for convenience.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity>
    """

    object_: as_ObjectRef = Field(
        None, validation_alias="object", serialization_alias="object"
    )

    @model_validator(mode="after")
    def set_name(self):
        """Set a default name if none is provided"""
        if self.name is not None:
            return self

        parts = []
        if self.actor is not None:
            parts.append(name_of(self.actor))
        if self.type_ is not None:
            parts.append(self.type_)
        if self.object_ is not None:
            parts.append(name_of(self.object_))
        if self.origin is not None:
            parts.extend(("from", name_of(self.origin)))
        if self.target is not None:
            parts.extend(("to", name_of(self.target)))
        if self.instrument is not None:
            parts.extend(("using", name_of(self.instrument)))

        if parts:
            self.name = " ".join([str(part) for part in parts])

        return self


class as_Like(as_TransitiveActivity):
    """The actor likes, recommends or endorses the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-like>
    """

    type_: TA_type = Field(
        default=TA_type.LIKE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Ignore(as_TransitiveActivity):
    """The actor is ignoring the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-ignore>
    """

    type_: TA_type = Field(
        default=TA_type.IGNORE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Block(as_Ignore):
    """The actor is blocking the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-block>
    """

    type_: TA_type = Field(
        default=TA_type.BLOCK,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Offer(as_TransitiveActivity):
    """The actor is offering the object. If specified, the origin indicates the context from which the object originated.
    The target indicates the entity to which the object is being offered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-offer>
    """

    type_: TA_type = Field(
        default=TA_type.OFFER,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Invite(as_Offer):
    """The actor is requesting that the target accept the object. The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-invite>
    """

    type_: TA_type = Field(
        default=TA_type.INVITE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Flag(as_TransitiveActivity):
    """The actor is flagging the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-flag>
    """

    type_: TA_type = Field(
        default=TA_type.FLAG,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Remove(as_TransitiveActivity):
    """The actor removes the object from the target. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-remove>
    """

    type_: TA_type = Field(
        default=TA_type.REMOVE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Undo(as_TransitiveActivity):
    """The actor is undoing the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-undo>
    """

    type_: TA_type = Field(
        default=TA_type.UNDO,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Create(as_TransitiveActivity):
    """The actor is creating the object. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-create>
    """

    type_: TA_type = Field(
        default=TA_type.CREATE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Delete(as_TransitiveActivity):
    """The actor is deleting the object. If specified, the origin indicates the context from which the object was deleted.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-delete>
    """

    type_: TA_type = Field(
        default=TA_type.DELETE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Move(as_TransitiveActivity):
    """The actor is moving the object from the origin to the target.
    If the origin or target are not specified, either can be determined by context.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-move>
    """

    type_: TA_type = Field(
        default=TA_type.MOVE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Add(as_TransitiveActivity):
    """The actor is adding the object to the target. If the target is not specified, it must be determined by context.
    The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-add>
    """

    type_: TA_type = Field(
        default=TA_type.ADD,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Join(as_TransitiveActivity):
    """The actor has joined the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-join>
    """

    type_: TA_type = Field(
        default=TA_type.JOIN,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Update(as_TransitiveActivity):
    """The actor has updated the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-update>
    """

    type_: TA_type = Field(
        default=TA_type.UPDATE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Listen(as_TransitiveActivity):
    """The actor has listened to the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-listen>
    """

    type_: TA_type = Field(
        default=TA_type.LISTEN,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Leave(as_TransitiveActivity):
    """The actor has left the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-leave>
    """

    type_: TA_type = Field(
        default=TA_type.LEAVE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Announce(as_TransitiveActivity):
    """The actor is calling the target's attention to the object. The origin typically has no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-announce>
    """

    type_: TA_type = Field(
        default=TA_type.ANNOUNCE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Follow(as_TransitiveActivity):
    """The actor is "following" the object.
    Following is defined in the sense commonly used in Social systems in which the actor is interested in any activity
    performed by or on the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-follow>
    """

    type_: TA_type = Field(
        default=TA_type.FOLLOW,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Accept(as_TransitiveActivity):
    """The actor accepts the object. The target property can be used in certain circumstances to indicate the context into
    which the object has been accepted.
    """

    type_: TA_type = Field(
        default=TA_type.ACCEPT,
        validation_alias="type",
        serialization_alias="type",
    )


class as_TentativeAccept(as_Accept):
    """The actor tentatively accepts the object.
    A specialization of Accept indicating that the acceptance is tentative.
    """

    type_: TA_type = Field(
        default=TA_type.TENTATIVE_ACCEPT,
        validation_alias="type",
        serialization_alias="type",
    )


class as_View(as_TransitiveActivity):
    """The actor has viewed the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-view>
    """

    type_: TA_type = Field(
        default=TA_type.VIEW,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Dislike(as_TransitiveActivity):
    """The actor dislikes the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-dislike>
    """

    type_: TA_type = Field(
        default=TA_type.DISLIKE,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Reject(as_TransitiveActivity):
    """The actor rejects the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-reject>
    """

    type_: TA_type = Field(
        default=TA_type.REJECT,
        validation_alias="type",
        serialization_alias="type",
    )


class as_TentativeReject(as_Reject):
    """A specialization of Reject indicating that the rejection is tentative.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tentativereject>
    """

    type_: TA_type = Field(
        default=TA_type.TENTATIVE_REJECT,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Read(as_TransitiveActivity):
    """The actor has read the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-read>
    """

    type_: TA_type = Field(
        default=TA_type.READ,
        validation_alias="type",
        serialization_alias="type",
    )


def main():
    from vultron.wire.as2.vocab.base.utils import print_activity_examples

    print_activity_examples()


if __name__ == "__main__":
    main()
