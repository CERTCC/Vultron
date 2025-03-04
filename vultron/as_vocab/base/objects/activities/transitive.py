#!/usr/bin/env python
"""file: activities
author: adh
created_at: 12/8/22 4:01 PM
"""
#  Copyright (c) 2023-2025 Carnegie Mellon University and Contributors.
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

from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base import activitystreams_activity
from vultron.as_vocab.base.links import as_Link
from vultron.as_vocab.base.objects.activities.base import (
    as_Activity as Activity,
)
from vultron.as_vocab.base.objects.base import as_Object
from vultron.as_vocab.base.utils import name_of


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_TransitiveActivity(Activity):
    """A transitive activity is an activity that has an object.
    ActivityPub doesn't define transitive activities separately from activities, but we do it here for convenience.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity>
    """

    as_object: Optional[as_Object | as_Link | str] = field(
        metadata=config(field_name="object"), default=None, repr=True
    )

    def __post_init__(self):
        super().__post_init__()
        if self.name is None:
            parts = [
                name_of(self.actor),
                self.as_type,
            ]
            if self.as_object is not None:
                parts.append(name_of(self.as_object))
            if self.origin is not None:
                parts.extend(("from", self.origin))
            if self.target is not None:
                parts.extend(("to", self.target))
            if self.instrument is not None:
                parts.extend(("using", self.instrument))
            self.name = " ".join([str(part) for part in parts])


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Like(as_TransitiveActivity):
    """The actor likes, recommends or endorses the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-like>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Ignore(as_TransitiveActivity):
    """The actor is ignoring the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-ignore>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Block(as_Ignore):
    """The actor is blocking the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-block>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Offer(as_TransitiveActivity):
    """The actor is offering the object. If specified, the origin indicates the context from which the object originated.
    The target indicates the entity to which the object is being offered.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-offer>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Invite(as_Offer):
    """The actor is requesting that the target accept the object. The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-invite>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Flag(as_TransitiveActivity):
    """The actor is flagging the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-flag>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Remove(as_TransitiveActivity):
    """The actor removes the object from the target. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-remove>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Undo(as_TransitiveActivity):
    """The actor is undoing the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-undo>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Create(as_TransitiveActivity):
    """The actor is creating the object. If specified, the origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-create>
    """

    pass


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Delete(as_TransitiveActivity):
    """The actor is deleting the object. If specified, the origin indicates the context from which the object was deleted.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-delete>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Move(as_TransitiveActivity):
    """The actor is moving the object from the origin to the target.
    If the origin or target are not specified, either can be determined by context.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-move>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Add(as_TransitiveActivity):
    """The actor is adding the object to the target. If the target is not specified, it must be determined by context.
    The origin indicates the context from which the object originated.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-add>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Join(as_TransitiveActivity):
    """The actor has joined the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-join>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Update(as_TransitiveActivity):
    """The actor has updated the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-update>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Listen(as_TransitiveActivity):
    """The actor has listened to the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-listen>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Leave(as_TransitiveActivity):
    """The actor has left the object. The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-leave>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Announce(as_TransitiveActivity):
    """The actor is calling the target's attention to the object. The origin typically has no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-announce>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Follow(as_TransitiveActivity):
    """The actor is "following" the object.
    Following is defined in the sense commonly used in Social systems in which the actor is interested in any activity
    performed by or on the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-follow>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Accept(as_TransitiveActivity):
    """The actor accepts the object. The target property can be used in certain circumstances to indicate the context into
    which the object has been accepted.
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_TentativeAccept(as_Accept):
    """The actor tentatively accepts the object.
    A specialization of Accept indicating that the acceptance is tentative.
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_View(as_TransitiveActivity):
    """The actor has viewed the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-view>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Dislike(as_TransitiveActivity):
    """The actor dislikes the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-dislike>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Reject(as_TransitiveActivity):
    """The actor rejects the object.
    The target and origin typically have no defined meaning.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-reject>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_TentativeReject(as_Reject):
    """A specialization of Reject indicating that the rejection is tentative.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-tentativereject>
    """


@activitystreams_activity
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Read(as_TransitiveActivity):
    """The actor has read the object.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-read>
    """


def main():
    from vultron.as_vocab.base.utils import print_activity_examples

    print_activity_examples()


if __name__ == "__main__":
    main()
