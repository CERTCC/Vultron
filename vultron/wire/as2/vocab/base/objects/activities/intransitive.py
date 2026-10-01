#!/usr/bin/env python
"""This module provides intransitive activity classes"""

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

from datetime import datetime
from typing import TypeAlias

from pydantic import Field, model_validator

from vultron.primitives import NonEmptyString
from vultron.wire.as2.enums import as_IntransitiveActivityType as IA_type
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.base import (
    as_Activity as Activity,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object


class as_IntransitiveActivity(Activity):
    """Base class for all ActivityPub intransitive activities.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#intransitiveactivity>
    """

    def description(self):
        return f"{self.actor} {self.type_} to {self.target} with {self.result}"


class as_Travel(as_IntransitiveActivity):
    """The actor travels from the origin to the target.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-travel>
    """

    type_: IA_type = Field(
        default=IA_type.TRAVEL,
        validation_alias="type",
        serialization_alias="type",
    )


class as_Arrive(as_IntransitiveActivity):
    """The actor arrives at the target. The origin can be used to specify the previous location from which the actor arrived.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-arrive>
    """

    type_: IA_type = Field(
        default=IA_type.ARRIVE,
        validation_alias="type",
        serialization_alias="type",
    )


#: What a Question's ``anyOf``/``oneOf`` may hold: a collection of options (AS2
#: §4.1 non-functional), a lone option, or a URI reference to one.  A reference
#: is a ``NonEmptyString`` so a blank option is refused rather than carried
#: (CS-08-001).
_QuestionOptions: TypeAlias = (
    list[as_Object | as_Link | NonEmptyString]
    | as_Object
    | as_Link
    | NonEmptyString
    | None
)


class as_Question(as_IntransitiveActivity):
    """The actor poses a question to the target. The origin can be used to specify the context from which the question was posed.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-question>
    """

    type_: IA_type = Field(
        default=IA_type.QUESTION,
        validation_alias="type",
        serialization_alias="type",
    )

    # AS2 §4.1 defines ``anyOf``/``oneOf`` as non-functional: a Question carries
    # a *collection* of options.  Declaring them as a single value (the shape
    # this class had until #3469) serialised a list last-writer-wins and refused
    # it on re-validation, so a Question with several options could not parse
    # its own output.  A lone option is still accepted, as AS2 allows.
    anyOf: _QuestionOptions = None
    oneOf: _QuestionOptions = None
    closed: as_Object | as_Link | NonEmptyString | datetime | bool | None = (
        None
    )

    @model_validator(mode="after")
    def _options_are_exclusive(self) -> "as_Question":
        """AS2 §4.1: ``anyOf`` and ``oneOf`` are mutually exclusive.

        A Question is either a multiple-choice (``anyOf``) or a single-choice
        (``oneOf``) poll; carrying both leaves the receiver unable to tell
        which answer form is expected.
        """
        if self.anyOf is not None and self.oneOf is not None:
            raise ValueError(
                "as_Question: anyOf and oneOf are mutually exclusive "
                "(AS2 §4.1); set at most one"
            )
        return self


def main():
    from vultron.wire.as2.vocab.base.utils import print_activity_examples

    print_activity_examples()


if __name__ == "__main__":
    main()
