#!/usr/bin/env python
"""file: rm_states
author: adh
created_at: 4/7/22 11:23 AM
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
#
#  See LICENSE for details

import logging
from enum import Enum, auto

logger = logging.getLogger(__name__)


class RM(Enum):
    """
    Report Management States

    START: Report has not yet been received
    RECEIVED: Report has been received but not yet validated
    INVALID: Report has been received but is invalid
    VALID: Report has been received and is valid
    DEFERRED: Report has been received and is valid but has been deferred
    ACCEPTED: Report has been received, is valid, and has been accepted
    CLOSED: Report has been closed
    """

    REPORT_MANAGEMENT_START = auto()
    REPORT_MANAGEMENT_RECEIVED = auto()
    REPORT_MANAGEMENT_INVALID = auto()
    REPORT_MANAGEMENT_VALID = auto()
    REPORT_MANAGEMENT_DEFERRED = auto()
    REPORT_MANAGEMENT_ACCEPTED = auto()
    REPORT_MANAGEMENT_CLOSED = auto()

    # convenience aliases
    START = REPORT_MANAGEMENT_START
    RECEIVED = REPORT_MANAGEMENT_RECEIVED
    INVALID = REPORT_MANAGEMENT_INVALID
    VALID = REPORT_MANAGEMENT_VALID
    DEFERRED = REPORT_MANAGEMENT_DEFERRED
    ACCEPTED = REPORT_MANAGEMENT_ACCEPTED
    CLOSED = REPORT_MANAGEMENT_CLOSED

    S = REPORT_MANAGEMENT_START
    R = REPORT_MANAGEMENT_RECEIVED
    I = REPORT_MANAGEMENT_INVALID
    V = REPORT_MANAGEMENT_VALID
    D = REPORT_MANAGEMENT_DEFERRED
    A = REPORT_MANAGEMENT_ACCEPTED
    C = REPORT_MANAGEMENT_CLOSED


# Report Management States that can be closed
RM_CLOSABLE = (
    RM.INVALID,
    RM.DEFERRED,
    RM.ACCEPTED,
)

# Report Management States that are not closed
RM_UNCLOSED = (
    RM.START,
    RM.RECEIVED,
    RM.INVALID,
    RM.VALID,
    RM.DEFERRED,
    RM.ACCEPTED,
)

# Report Management States that are active
RM_ACTIVE = (
    RM.RECEIVED,
    RM.VALID,
    RM.ACCEPTED,
)


def to_string(value):
    """
    Convert a Report Management state to a string
    :param value: Report Management state value
    :return: Report Management state name
    """
    return RM(value).name


def from_string(name):
    """Convert a Report Management state name to a value

    Args:
        name: Report Management state name

    Returns:
        Report Management state value
    """
    return RM[name]


def main():
    rootlogger = logging.getLogger()
    rootlogger.setLevel(logging.DEBUG)
    hdlr = logging.StreamHandler()
    rootlogger.addHandler(hdlr)

    logger.debug(f"RM enum = {list(RM)}")
    logger.debug(f"RMclosable = {RM_CLOSABLE}")
    logger.debug(f"RMunclosed = {RM_UNCLOSED}")
    logger.debug(f"RMactive = {RM_ACTIVE}")


if __name__ == "__main__":
    main()
