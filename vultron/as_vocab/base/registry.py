#!/usr/bin/env python
"""
Provides a registry for the Vultron ActivityStreams Vocabulary.
"""
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

from pydantic import BaseModel, Field

class Vocabulary(BaseModel):
    objects: dict[str, type] = Field(default_factory=dict)
    activities: dict[str, type] = Field(default_factory=dict)
    links: dict[str, type] = Field(default_factory=dict)

VOCABULARY = Vocabulary()

def activitystreams_object(cls: type) -> type:
    """Register an object for a given object type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the object class.
    """
    key = cls.__name__.lstrip("as_")
    VOCABULARY.objects[key] = cls
    return cls


def activitystreams_activity(cls: type) -> type:
    """Register an activity for a given activity type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the activity class.
    """
    key = cls.__name__.lstrip("as_")
    VOCABULARY.activities[key] = cls
    return cls


def activitystreams_link(cls: type) -> type:
    """Register a link for a given link type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the link class.
    """
    key = cls.__name__.lstrip("as_")
    VOCABULARY.links[key] = cls
    return cls

def main():
    pass


if __name__ == '__main__':
    main()
