#!/usr/bin/env python
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
"""
This module defines CVD Case State conditions as Behavior Tree nodes.
"""


from vultron.bt.base.bt_node import BtNode
from vultron.bt.base.factory import condition_check, invert, sequence
from vultron.case_states.states import (
    AttackObservation,
    ExploitPublication,
    FixDeployment,
    FixReadiness,
    PublicAwareness,
    VendorAwareness,
)


def cs_in_state_vendor_aware(obj: BtNode) -> bool:
    """True when the vendor is aware of the vulnerability"""
    return (
        obj.bb.q_cs.value.vfd_state.value.vendor_awareness == VendorAwareness.V
    )


CSinStateVendorAware = condition_check(
    "CSinStateVendorAware",
    cs_in_state_vendor_aware,
)


def cs_in_state_fix_ready(obj: BtNode) -> bool:
    """True when the vendor has a fix ready"""
    return obj.bb.q_cs.value.vfd_state.value.fix_readiness == FixReadiness.F


CSinStateFixReady = condition_check(
    "CSinStateFixReady",
    cs_in_state_fix_ready,
)


def cs_in_state_fix_deployed(obj: BtNode) -> bool:
    """True when the fix has been deployed"""
    return obj.bb.q_cs.value.vfd_state.value.fix_deployment == FixDeployment.D


CSinStateFixDeployed = condition_check(
    "CSinStateFixDeployed",
    cs_in_state_fix_deployed,
)


def cs_in_state_public_aware(obj: BtNode) -> bool:
    """True when the public is aware of the vulnerability"""
    return (
        obj.bb.q_cs.value.pxa_state.value.public_awareness == PublicAwareness.P
    )


CSinStatePublicAware = condition_check(
    "CSinStatePublicAware",
    cs_in_state_public_aware,
)


def cs_in_state_exploit_public(obj: BtNode) -> bool:
    """True when an exploit is public for the vulnerability"""
    return (
        obj.bb.q_cs.value.pxa_state.value.exploit_publication
        == ExploitPublication.X
    )


CSinStateExploitPublic = condition_check(
    "CSinStateExploitPublic",
    cs_in_state_exploit_public,
)


def cs_in_state_attacks_observed(obj: BtNode) -> bool:
    """True when attacks against the vulnerability have been observed"""
    return (
        obj.bb.q_cs.value.pxa_state.value.attack_observation
        == AttackObservation.A
    )


CSinStateAttacksObserved = condition_check(
    "CSinStateAttacksObserved",
    cs_in_state_attacks_observed,
)


CSinStatePublicAwareAndExploitPublic = sequence(
    "CSinStatePublicAwareAndExploitPublic",
    """Sequence node for whether the public is aware of the vulnerability and an exploit is public""",
    CSinStatePublicAware,
    CSinStateExploitPublic,
)


CSinStateVendorAwareAndFixReady = sequence(
    "CSinStateVendorAwareAndFixReady",
    """Sequence node for whether the vendor is aware of the vulnerability and has a fix ready""",
    CSinStateVendorAware,
    CSinStateFixReady,
)

CSinStateVendorAwareAndFixReadyAndFixDeployed = sequence(
    "CSinStateVendorAwareAndFixReadyAndFixDeployed",
    """Sequence node for whether the vendor is aware of the vulnerability,
    has a fix ready, and the fix has been deployed""",
    CSinStateVendorAware,
    CSinStateFixReady,
    CSinStateFixDeployed,
)

CSinStateVendorUnaware = invert(
    "CSinStateVendorUnaware",
    """Condition check for whether the vendor is unaware of the vulnerability""",
    CSinStateVendorAware,
)


CSinStateFixNotReady = invert(
    "CSinStateFixNotReady",
    """Condition check for whether the vendor does not have a fix ready""",
    CSinStateFixReady,
)


CSinStateFixNotDeployed = invert(
    "CSinStateFixNotDeployed",
    """Condition check for whether a fix has not been deployed""",
    CSinStateFixDeployed,
)


CSinStatePublicUnaware = invert(
    "CSinStatePublicUnaware",
    """Condition check for whether the public is unaware of the vulnerability""",
    CSinStatePublicAware,
)

CSinStateNoExploitPublic = invert(
    "CSinStateNoExploitPublic",
    """Condition check for whether no exploit is public for the vulnerability""",
    CSinStateExploitPublic,
)

CSinStateNoAttacksObserved = invert(
    "CSinStateNoAttacksObserved",
    """Condition check for whether no attacks against the vulnerability have been observed""",
    CSinStateAttacksObserved,
)

CSinStateNotPublicNoExploitNoAttacks = sequence(
    "CSinStateNotPublicNoExploitNoAttacks",
    """Sequence node for whether the public is unaware of the vulnerability, no exploit is public, and no attacks 
    have been observed""",
    CSinStatePublicUnaware,
    CSinStateNoExploitPublic,
    CSinStateNoAttacksObserved,
)


CSinStatePublicAwareOrExploitPublicOrAttacksObserved = invert(
    "CSinStatePublicAwareOrExploitPublicOrAttacksObserved",
    """Condition check for whether the public is aware of the vulnerability, an exploit is public, or attacks have 
    been observed""",
    CSinStateNotPublicNoExploitNoAttacks,
)


CSinStateNotDeployedNotPublicNoExploitNoAttacks = sequence(
    "CSinStateNotDeployedNotPublicNoExploitNoAttacks",
    """Condition check for whether a fix has not been deployed, the public is unaware of the vulnerability, 
    no exploit is public, and no attacks have been observed""",
    CSinStateFixNotDeployed,
    CSinStateNotPublicNoExploitNoAttacks,
)


CSinStateNotDeployedButPublicAware = sequence(
    "CSinStateNotDeployedButPublicAware",
    """Condition check for whether a fix has not been deployed but the public is aware of the vulnerability""",
    CSinStateFixNotDeployed,
    CSinStatePublicAware,
)


CSinStateVendorAwareFixReadyFixNotDeployed = sequence(
    "CSinStateVendorAwareFixReadyFixNotDeployed",
    """Condition check for whether the vendor is aware of the vulnerability and has a fix ready, but the fix has not 
    been deployed""",
    CSinStateVendorAware,
    CSinStateFixReady,
    CSinStateFixNotDeployed,
)


# aliases
CSisEmbargoCompatible = CSinStateNotPublicNoExploitNoAttacks
CSisEmbargoIncompatible = CSinStatePublicAwareOrExploitPublicOrAttacksObserved

# shorthand
q_cs_in_V = CSinStateVendorAware
q_cs_in_F = CSinStateFixReady
q_cs_in_D = CSinStateFixDeployed
q_cs_in_P = CSinStatePublicAware
q_cs_in_X = CSinStateExploitPublic
q_cs_in_A = CSinStateAttacksObserved

q_cs_in_PX = CSinStatePublicAwareAndExploitPublic
q_cs_in_VF = CSinStateVendorAwareAndFixReady
q_cs_in_VFD = CSinStateVendorAwareAndFixReadyAndFixDeployed

q_cs_in_v = CSinStateVendorUnaware
q_cs_in_f = CSinStateFixNotReady
q_cs_in_d = CSinStateFixNotDeployed
q_cs_in_p = CSinStatePublicUnaware
q_cs_in_x = CSinStateNoExploitPublic
q_cs_in_a = CSinStateNoAttacksObserved

q_cs_in_pxa = CSinStateNotPublicNoExploitNoAttacks
q_cs_not_in_pxa = CSinStatePublicAwareOrExploitPublicOrAttacksObserved
q_cs_in_dpxa = CSinStateNotDeployedNotPublicNoExploitNoAttacks
q_cs_in_dP = CSinStateNotDeployedButPublicAware
q_cs_in_VFd = CSinStateVendorAwareFixReadyFixNotDeployed
