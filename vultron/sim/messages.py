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
"""
Provides a basic message class for use in a Vultron simulation.
"""

from dataclasses import dataclass

from vultron.bt.messaging.states import MessageTypes


@dataclass(kw_only=True)
class Message:
    """
    Represents a message with a sender and body and optional message type.
    """

    sender: str
    body: str
    msg_type: MessageTypes = MessageTypes.GI
