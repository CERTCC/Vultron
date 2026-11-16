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

"""The ``REFUSED (IDs)`` group a refusal reason ends with, and who logs it.

A refusal reason names its condition and ends with the group citing the
requirements it rests on: ``"Sender 'a' is not the Case Owner of case 'c'
— REFUSED (HP-01-006)"``.  The reason travels as a node's
``feedback_message`` into the handler's ``HandlerResult.refused`` reason.

Only the received runner knows the delivery's verdict, so only it logs a
line carrying the group: one WARNING per refused delivery (SL-03-002).  A
node, the bridge or the outcome stage that logs the same reason states the
facts without the group (:func:`without_refusal_group`, SL-03-003), so the
token a reader greps and the demo tests match stays the verdict's.
"""

import re

#: One ``REFUSED (IDs)`` group, with the dash before it and an optional word
#: naming the move between them (``— removal REFUSED (CM-31-003)``).
_GROUP = re.compile(r"(?:\s*—\s*(?:\w+ )?)?REFUSED \([^)]*\)")

#: Any ``REFUSED (IDs)`` group, wherever it sits in a line.
REFUSAL_GROUP = re.compile(r"REFUSED \([^)]*\)")

#: The requirement a runner line cites when the reason it reports carries no
#: group of its own: a handler reports ``REFUSED`` only for an assertion it
#: rejected (HP-01-003).
DEFAULT_REFUSAL_CITATION = "HP-01-003"


def carries_refusal_group(text: str) -> bool:
    """``True`` when *text* holds a ``REFUSED (IDs)`` group."""
    return REFUSAL_GROUP.search(text) is not None


def without_refusal_group(reason: str) -> str:
    """*reason* with every ``— REFUSED (IDs)`` group removed.

    The facts the reason states stay; only the token that claims the
    verdict goes (SL-03-003).
    """
    return _GROUP.sub("", reason)


def with_refusal_group(reason: str) -> str:
    """*reason* as the received runner logs it: always carrying a group.

    A reason that already ends with its own group is returned unchanged, so
    the runner logs exactly the reason it reports.  One that carries none
    (a general failure's leaf reason) gains ``— REFUSED (HP-01-003)``.
    """
    if carries_refusal_group(reason):
        return reason
    return f"{reason} — REFUSED ({DEFAULT_REFUSAL_CITATION})"


__all__ = [
    "DEFAULT_REFUSAL_CITATION",
    "REFUSAL_GROUP",
    "carries_refusal_group",
    "with_refusal_group",
    "without_refusal_group",
]
