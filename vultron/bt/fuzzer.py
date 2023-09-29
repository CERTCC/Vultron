#!/usr/bin/env python
"""file: cvd_proto_fuzzer
author: adh
created_at: 4/26/22 10:59 AM
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


import random

from vultron.cvd_states.states import all_states

from vultron.bt.embargo_management.states import EM
from vultron.bt.report_management.states import RM_UNCLOSED


def random_state():
    state = {
        "q_rm": random.choice(RM_UNCLOSED),
        "q_em": random.choice(list(EM)),
        "q_cs": random.choice(all_states),
    }
    return state


def main():
    pass


if __name__ == "__main__":
    main()
