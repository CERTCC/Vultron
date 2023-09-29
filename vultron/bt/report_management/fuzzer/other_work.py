#!/usr/bin/env python
"""file: other_work
author: adh
created_at: 2/21/23 2:41 PM
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


from vultron.bt.base import fuzzer as btz


class OtherWork(btz.AlwaysSucceed):
    """Placeholder for other work that may be done by in the do_work bt.
    This node could be replaced with any other tree of nodes that represent other work that may be done.
    In our stub implementation, this node always succeeds.
    """

    # do other work under this node
