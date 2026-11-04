#!/usr/bin/env python
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


"""The six CVD Case State dimension enums, one per event (ADR-0060)."""

from enum import StrEnum


class VendorAwareness(StrEnum):
    """
    Represents the vendor awareness state of a case.
    """

    VENDOR_UNAWARE = "v"
    VENDOR_AWARE = "V"

    NO = VENDOR_UNAWARE
    YES = VENDOR_AWARE

    v = VENDOR_UNAWARE
    V = VENDOR_AWARE


class FixReadiness(StrEnum):
    """
    Represents the fix readiness state of a case.
    """

    FIX_NOT_READY = "f"
    FIX_READY = "F"

    NO = FIX_NOT_READY
    YES = FIX_READY

    f = FIX_NOT_READY
    F = FIX_READY


class FixDeployment(StrEnum):
    """
    Represents the fix deployment state of a case.
    """

    FIX_NOT_DEPLOYED = "d"
    FIX_DEPLOYED = "D"

    NO = FIX_NOT_DEPLOYED
    YES = FIX_DEPLOYED

    d = FIX_NOT_DEPLOYED
    D = FIX_DEPLOYED


class PublicAwareness(StrEnum):
    """
    Represents the public awareness state of a case.
    """

    PUBLIC_UNAWARE = "p"
    PUBLIC_AWARE = "P"

    NO = PUBLIC_UNAWARE
    YES = PUBLIC_AWARE

    p = PUBLIC_UNAWARE
    P = PUBLIC_AWARE


class ExploitPublication(StrEnum):
    """
    Represents the exploit publication state of a case.
    """

    NO_PUBLIC_EXPLOIT = "x"
    EXPLOIT_PUBLIC = "X"

    NO = NO_PUBLIC_EXPLOIT
    YES = EXPLOIT_PUBLIC

    x = NO_PUBLIC_EXPLOIT
    X = EXPLOIT_PUBLIC


class AttackObservation(StrEnum):
    """
    Represents the attack observation state of a case.
    """

    NO_ATTACKS_OBSERVED = "a"
    ATTACKS_OBSERVED = "A"

    NO = NO_ATTACKS_OBSERVED
    YES = ATTACKS_OBSERVED

    a = NO_ATTACKS_OBSERVED
    A = ATTACKS_OBSERVED
