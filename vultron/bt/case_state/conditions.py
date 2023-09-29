#!/usr/bin/env python
"""file: cs_conditions
author: adh
created_at: 4/26/22 10:12 AM
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



from vultron.cvd_states.states import CS

from vultron.bt.base.bt_node import ConditionCheck
from vultron.bt.base.composites import SequenceNode
from vultron.bt.base.decorators import Invert


class CSinStateVendorAware(ConditionCheck):
    """Condition check for whether the vendor is aware of the vulnerability"""

    def func(self):
        return self.bb.q_cs & CS.V


class CSinStateFixReady(ConditionCheck):
    """Condition check for whether the vendor has a fix ready"""

    def func(self):
        return self.bb.q_cs & CS.F


class CSinStateFixDeployed(ConditionCheck):
    """Condition check for whether a fix has been deployed"""

    def func(self):
        return self.bb.q_cs & CS.D


class CSinStatePublicAware(ConditionCheck):
    """Condition check for whether the public is aware of the vulnerability"""

    def func(self):
        return self.bb.q_cs & CS.P


class CSinStateExploitPublic(ConditionCheck):
    """Condition check for whether an exploit is public for the vulnerability"""

    def func(self):
        return self.bb.q_cs & CS.X


class CSinStateAttacksObserved(ConditionCheck):
    """Condition check for whether attacks against the vulnerability have been observed"""

    def func(self):
        return self.bb.q_cs & CS.A


class CSinStatePublicAwareAndExploitPublic(SequenceNode):
    """Sequence node for whether the public is aware of the vulnerability and an exploit is public"""

    _children = (CSinStatePublicAware, CSinStateExploitPublic)


class CSinStateVendorAwareAndFixReady(SequenceNode):
    """Sequence node for whether the vendor is aware of the vulnerability and has a fix ready"""

    _children = (CSinStateVendorAware, CSinStateFixReady)


class CSinStateVendorAwareAndFixReadyAndFixDeployed(SequenceNode):
    """Sequence node for whether the vendor is aware of the vulnerability, has a fix ready, and the fix has been deployed"""

    _children = (CSinStateVendorAware, CSinStateFixReady, CSinStateFixDeployed)


class CSinStateVendorUnaware(Invert):
    """Condition check for whether the vendor is unaware of the vulnerability"""

    _children = (CSinStateVendorAware,)


class CSinStateFixNotReady(Invert):
    """Condition check for whether the vendor does not have a fix ready"""

    _children = (CSinStateFixReady,)


class CSinStateFixNotDeployed(Invert):
    """Condition check for whether a fix has not been deployed"""

    _children = (CSinStateFixDeployed,)


class CSinStatePublicUnaware(Invert):
    """Condition check for whether the public is unaware of the vulnerability"""

    _children = (CSinStatePublicAware,)


class CSinStateNoExploitPublic(Invert):
    """Condition check for whether no exploit is public for the vulnerability"""

    _children = (CSinStateExploitPublic,)


class CSinStateNoAttacksObserved(Invert):
    """Condition check for whether no attacks against the vulnerability have been observed"""

    _children = (CSinStateAttacksObserved,)


class CSinStateNotPublicNoExploitNoAttacks(SequenceNode):
    """Sequence node for whether the public is unaware of the vulnerability, no exploit is public, and no attacks have been observed"""

    _children = (
        CSinStatePublicUnaware,
        CSinStateNoExploitPublic,
        CSinStateNoAttacksObserved,
    )


class CSinStatePublicAwareOrExploitPublicOrAttacksObserved(Invert):
    """Condition check for whether the public is aware of the vulnerability, an exploit is public, or attacks have been observed"""

    _children = (CSinStateNotPublicNoExploitNoAttacks,)


class CSinStateNotDeployedNotPublicNoExploitNoAttacks(SequenceNode):
    """Condition check for whether a fix has not been deployed, the public is unaware of the vulnerability, no exploit is public, and no attacks have been observed"""

    _children = (CSinStateFixNotDeployed, CSinStateNotPublicNoExploitNoAttacks)


class CSinStateNotDeployedButPublicAware(SequenceNode):
    """Condition check for whether a fix has not been deployed but the public is aware of the vulnerability"""

    _children = (CSinStateFixNotDeployed, CSinStatePublicAware)


class CSinStateVendorAwareFixReadyFixNotDeployed(SequenceNode):
    """Condition check for whether the vendor is aware of the vulnerability and has a fix ready, but the fix has not been deployed"""

    _children = (
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


def main():
    pass


if __name__ == "__main__":
    main()
