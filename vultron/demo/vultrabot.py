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


def main() -> None:
    """
    Instantiates a CvdProtocolBt object and runs it until either it closes or 1000 ticks have passed.
    This demo is basically simulating a CVD agent coordinating a CVD case with itself.
    The agent's role is set to FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR, which means it will
    perform all the roles in the CVD case.
    Messages emitted in one tick might be received later in the same tick, or in a future tick.

    !!! tip

       This demo leverages the ability to use leaf nodes as stochastic process fuzzers.
       Using this feature, we can simulate the behavior of a CVD agent without having to
       implement any actual communication mechanisms or simulate any complex real-world processes.

       One interesting effect of this design is that the places where the demo uses a fuzzer node are often
       indicative of places where an actual bot would either need to call out to either a data source or
       a human to decide what to do next. This is a good example of how the Vultron behavior tree
       can be used to model complex reactive processes in a way that is still easy to understand and reason about.

    !!! note

        There is no underlying communication mechanism in this demo, so messages are not actually
        sent anywhere. Instead, they are just added to the blackboard's incoming message queue.
        They also have no content, and are only represented as message types.

    !!! warning

        This demo is not intended to be a fully realistic simulation of a CVD case. It is only intended
        to demonstrate the behavior of the Vultron behavior tree.
    """

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

    shorten_names = lambda y: tuple([x.value for x in y])

    df.q_rm = df.q_rm.apply(lambda x: x.value)
    df.q_em = df.q_em.apply(lambda x: x.value)

    df.msgs_received_this_tick = df.msgs_received_this_tick.apply(
        shorten_names
    )
    df.msgs_emitted_this_tick = df.msgs_emitted_this_tick.apply(shorten_names)

    df.CVD_role = df.CVD_role.apply(lambda x: x.name)
    df.q_cs = df.q_cs.apply(lambda x: x.name)

    df = df.drop_duplicates()
    print(df)


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    hdlr = logging.StreamHandler()
    logger.addHandler(hdlr)

    # for i in range(1):
    # reset_statelog()
    main()
