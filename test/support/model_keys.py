#!/usr/bin/env python

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

"""The key sets a Pydantic model writes and reads.

Shared by the ratchets that hold ARCH-25-008: every key a wire class dumps
must be a key its core counterpart root declares, so a legitimate AS2 field is
never mistaken for an unknown one.
"""

from pydantic import AliasChoices, BaseModel


def dumped_keys(model: type[BaseModel]) -> set[str]:
    """Every key a ``by_alias`` dump of *model* can emit."""
    return {
        info.serialization_alias or info.alias or name
        for name, info in model.model_fields.items()
        if not info.exclude
    }


def accepted_keys(model: type[BaseModel]) -> set[str]:
    """Every input key *model* accepts: field names plus their aliases."""
    keys: set[str] = set()
    for name, info in model.model_fields.items():
        keys.add(name)
        for alias in (info.alias, info.validation_alias):
            if isinstance(alias, str):
                keys.add(alias)
            elif isinstance(alias, AliasChoices):
                keys.update(c for c in alias.choices if isinstance(c, str))
    return keys
