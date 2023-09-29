#!/usr/bin/env python
"""file: fuzzer
author: adh
created_at: 2/22/23 10:24 AM
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

from vultron.bt.base import fuzzer as btz
from vultron.bt.base.composites import FallbackNode
from vultron.bt.messaging.outbound.behaviors import EmitGI


class FollowUpOnErrorMessage(FallbackNode):
    """This is a stub for following up on an error message. In our stub implementation, we just stochastically (0.5
    probability) emit a GI message to simulate sending a follow-up inquiry message.
    """

    _children = (btz.UniformSucceedFail, EmitGI)
