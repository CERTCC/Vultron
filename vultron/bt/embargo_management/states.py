#!/usr/bin/env python
"""This module defines the Embargo Management states for the Vultron protocol."""
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


from enum import StrEnum


class EM(StrEnum):
    """Embargo Management States

    NO_EMBARGO: No embargo is in effect
    PROPOSED: Embargo is proposed but not yet active
    ACTIVE: Embargo is active
    REVISE: Embargo is active and a revision is proposed
    EXITED: Embargo had been active but has been exited
    """

    EMBARGO_MANAGEMENT_NONE = "NONE"
    EMBARGO_MANAGEMENT_PROPOSED = "PROPOSED"
    EMBARGO_MANAGEMENT_ACTIVE = "ACTIVE"
    EMBARGO_MANAGEMENT_REVISE = "REVISE"
    EMBARGO_MANAGEMENT_EXITED = "EXITED"

    # convenience aliases
    NO_EMBARGO = EMBARGO_MANAGEMENT_NONE
    PROPOSED = EMBARGO_MANAGEMENT_PROPOSED
    ACTIVE = EMBARGO_MANAGEMENT_ACTIVE
    REVISE = EMBARGO_MANAGEMENT_REVISE
    EXITED = EMBARGO_MANAGEMENT_EXITED

    N = EMBARGO_MANAGEMENT_NONE
    P = EMBARGO_MANAGEMENT_PROPOSED
    A = EMBARGO_MANAGEMENT_ACTIVE
    R = EMBARGO_MANAGEMENT_REVISE
    X = EMBARGO_MANAGEMENT_EXITED


def main():
    print("EM states:")
    print("----------")
    for x in EM:
        print(x.name, x.value)


if __name__ == "__main__":
    main()
