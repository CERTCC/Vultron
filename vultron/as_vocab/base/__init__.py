"""
Provides an implementation of the ActivityStreams 2.0 protocol.
"""

#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
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

OBJECT_TYPES = {}
ACTIVITY_TYPES = {}
LINK_TYPES = {}

VOCABULARY = {
    "objects": OBJECT_TYPES,
    "activities": ACTIVITY_TYPES,
    "links": LINK_TYPES,
}


def activitystreams_object(cls: type) -> type:
    """Register an object for a given object type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the object class.
    """
    key = cls.__name__.lstrip("as_")
    OBJECT_TYPES[key] = cls
    return cls


def activitystreams_activity(cls: type) -> type:
    """Register an activity for a given activity type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the activity class.
    """
    key = cls.__name__.lstrip("as_")
    ACTIVITY_TYPES[key] = cls
    return cls


def activitystreams_link(cls: type) -> type:
    """Register a link for a given link type.

    Args:
        cls: The class to register.

    Returns:
        A decorator that registers the link class.
    """
    key = cls.__name__.lstrip("as_")
    LINK_TYPES[key] = cls
    return cls
