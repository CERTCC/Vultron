#!/usr/bin/env python
"""file: fuzzer
author: adh
created_at: 4/26/22 1:29 PM
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

from vultron.bt.messaging.states import MessageTypes
from vultron.bt.report_management.states import RM


def random_external_event_message():
    p_public = 0.6
    p_attacks_not_public = 0.6
    # thus p_attacks = 0.4 * 0.6 = 0.24
    # and p_exploit = 0.16

    if random.random() < p_public:
        return MessageTypes.CP
    if random.random() < p_attacks_not_public:
        return MessageTypes.CA
    return MessageTypes.CX


def generate_inbound_message(state):
    # if no report yet, receive a report with 1 in 5 chance
    if state.q_rm == RM.START:
        if random.random() < 0.4:
            return MessageTypes.RS

    # otherwise, with 1 in 20 chance, maybe something happened out in the world
    if random.random() < (0.05):
        return random_external_event_message()

    # if you got here, just return None
    return None
