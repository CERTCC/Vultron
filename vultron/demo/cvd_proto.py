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
Provides a simulated Vultron behavior tree simulator bot.
"""

import dataclasses
import logging

import pandas as pd

from vultron.bt.behaviors import CvdProtocolBt, STATELOG
from vultron.bt.messaging.behaviors import incoming_message
from vultron.bt.messaging.inbound.fuzzer import generate_inbound_message
from vultron.bt.roles.states import CVDRoles

logger = logging.getLogger(__name__)

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)


def main():

    tick = 0
    with CvdProtocolBt() as tree:
        tree.bb.CVD_role = CVDRoles.FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR

        for tick in range(1000):
            tick += 1
            logger.debug("")
            logger.debug(f"# tick {tick} #")
            tree.tick()

            # maybe add a random message to the incoming queue
            msg = generate_inbound_message(tree.bb)
            if msg is not None:
                incoming_message(tree.bb, msg)

            if tree.closed:
                # do one last snapshot
                tree.root.children[0].tick()
                break

    logger.info("")
    logger.info(f"Closed in {tick} ticks")
    for k, v in dataclasses.asdict(tree.bb).items():
        if "history" in k:
            logger.info(f"{k}: {v}")

    df = pd.DataFrame(STATELOG)
    df.index += 1

    shorten_names = lambda y: [x.value for x in y]

    df.q_rm = df.q_rm.apply(lambda x: x.value)
    df.q_em = df.q_em.apply(lambda x: x.value)
    df.msgs_received_this_tick = df.msgs_received_this_tick.apply(shorten_names)
    df.msgs_emitted_this_tick = df.msgs_emitted_this_tick.apply(shorten_names)

    print(df)


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    hdlr = logging.StreamHandler()
    logger.addHandler(hdlr)

    # for i in range(1):
    # reset_statelog()
    main()
