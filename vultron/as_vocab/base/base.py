#!/usr/bin/env python
"""file: base
author: adh
created_at: 2/17/23 3:59 PM
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

from dataclasses import dataclass, field
from typing import Optional

from dataclasses_json import LetterCase, config, dataclass_json

from vultron.as_vocab.base.utils import exclude_if_none, generate_new_id


@dataclass_json(letter_case=LetterCase.CAMEL)
@dataclass(kw_only=True)
class as_Base(object):
    as_context: str = field(
        metadata=config(field_name="@context"),
        default="https://www.w3.org/ns/activitystreams",
        init=False,
    )
    as_type: str = field(
        metadata=config(field_name="type"), default=None, init=False
    )
    as_id: str = field(
        metadata=config(field_name="id"), default_factory=generate_new_id
    )
    name: Optional[str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    preview: Optional[str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )
    mediaType: Optional[str] = field(
        metadata=config(exclude=exclude_if_none), default=None
    )

    def __post_init__(self):
        if self.as_type is None:
            self.as_type = self.__class__.__name__.lstrip("as_")
