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


"""Milestone groups and predicates over the CS sub-machine states."""

from vultron.core.states.cs.states import (
    CS_d,
    CS_pxa,
    CS_vf,
)

# --- CS_vf milestone groups and predicates ---

# Vendor is aware of the vulnerability (V bit set in the VF path).
VF_VENDOR_AWARE = (CS_vf.Vf, CS_vf.VF)

# Fix has been developed and is ready (F bit set in the VF path).
VF_FIX_READY = (CS_vf.VF,)


def is_vf_vendor_aware(state: CS_vf) -> bool:
    """Return True when vendor awareness is set (V bit in the VF path).

    Examples::

        is_vf_vendor_aware(CS_vf.Vf)  # True
        is_vf_vendor_aware(CS_vf.VF)  # True
        is_vf_vendor_aware(CS_vf.vf)  # False
    """
    return state in VF_VENDOR_AWARE


def is_vf_fix_ready(state: CS_vf) -> bool:
    """Return True when fix readiness is set (F bit; implies vendor awareness).

    Examples::

        is_vf_fix_ready(CS_vf.VF)  # True
        is_vf_fix_ready(CS_vf.Vf)  # False
        is_vf_fix_ready(CS_vf.vf)  # False
    """
    return state in VF_FIX_READY


# --- CS_d milestone groups and predicates ---

# Fix has been deployed (D bit set in the deployer path).
D_FIX_DEPLOYED = (CS_d.D,)


def is_d_fix_deployed(state: CS_d) -> bool:
    """Return True when fix deployment is set (D bit).

    Examples::

        is_d_fix_deployed(CS_d.D)  # True
        is_d_fix_deployed(CS_d.d)  # False
    """
    return state in D_FIX_DEPLOYED


# --- pxa milestone groups and predicates (LST-04-001) ---

# Public is aware of the vulnerability (P bit set).
PXA_PUBLIC_AWARE = (
    CS_pxa.Pxa,
    CS_pxa.PxA,
    CS_pxa.PXa,
    CS_pxa.PXA,
)

# Exploit code is publicly available (X bit set).
# Includes ephemeral pXa/pXA states (X set, P not yet set); those resolve to
# PXa/PXA immediately via the pX→PX invariant but are valid enum values.
PXA_EXPLOIT_PUBLIC = (
    CS_pxa.pXa,
    CS_pxa.pXA,
    CS_pxa.PXa,
    CS_pxa.PXA,
)

# Attacks have been observed in the wild (A bit set).
PXA_ATTACKS_OBSERVED = (
    CS_pxa.pxA,
    CS_pxa.PxA,
    CS_pxa.pXA,
    CS_pxa.PXA,
)


def is_pxa_public_aware(state: CS_pxa) -> bool:
    """Return True if the public is aware of the vulnerability (P bit set).

    Examples::

        is_pxa_public_aware(CS_pxa.Pxa)  # True
        is_pxa_public_aware(CS_pxa.PXA)  # True
        is_pxa_public_aware(CS_pxa.pxa)  # False
    """
    return state in PXA_PUBLIC_AWARE


def is_pxa_exploit_public(state: CS_pxa) -> bool:
    """Return True if exploit code is publicly available (X bit set).

    Note: pX is transient — the pX→PX invariant means an exploit being public
    without public awareness is ephemeral; in practice P will also be set.
    This predicate reflects the X bit only.

    Examples::

        is_pxa_exploit_public(CS_pxa.pXa)  # True
        is_pxa_exploit_public(CS_pxa.PXA)  # True
        is_pxa_exploit_public(CS_pxa.Pxa)  # False
    """
    return state in PXA_EXPLOIT_PUBLIC


def is_pxa_attacks_observed(state: CS_pxa) -> bool:
    """Return True if attacks have been observed in the wild (A bit set).

    Examples::

        is_pxa_attacks_observed(CS_pxa.pxA)  # True
        is_pxa_attacks_observed(CS_pxa.PXA)  # True
        is_pxa_attacks_observed(CS_pxa.pxa)  # False
    """
    return state in PXA_ATTACKS_OBSERVED
