#!/usr/bin/env python
"""
Provides classes representing ActivityStreams Vocabulary Link objects.
"""
#  Copyright (c) 2023-2024 Carnegie Mellon University and Contributors.
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

from dataclasses import dataclass
from typing import Optional

from dataclasses_json import LetterCase, dataclass_json

from vultron.as_vocab.base import activitystreams_link
from vultron.as_vocab.base.base import as_Base


@activitystreams_link
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Link(as_Base):
    """A Link is an indirect, qualified reference to a resource identified by a URL.
    The fundamental model for links is established by [RFC5988].
    Many of the properties defined by the Activity Vocabulary allow values that are either instances of Object or a Link.
    When a Link is used, it establishes a qualified relation connecting the subject to the resource identified by the href property.
    Properties of the Link are properties of the reference as opposed to properties of the resource.
    Links are disjoint from the Object type.
    See definition in ActivityStreams Vocabulary <https://www.w3.org/TR/activitystreams-vocabulary/#dfn-link>
    """

    width: Optional[int] = None
    height: Optional[int] = None
    rel: Optional[str] = None
    href: Optional[str] = None
    hreflang: Optional[str] = None


@activitystreams_link
@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Mention(as_Link):
    """A Link that represents an @mention."""


def main():
    x = as_Link()
    print(x.to_dict())
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
