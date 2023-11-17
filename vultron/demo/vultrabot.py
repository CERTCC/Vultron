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
import argparse
import dataclasses
import logging
import sys

import pandas as pd

from vultron.bt.behaviors import CvdProtocolBt, CvdProtocolRoot, STATELOG
from vultron.bt.common import show_graph
from vultron.bt.messaging.behaviors import incoming_message
from vultron.bt.messaging.inbound.fuzzer import generate_inbound_message
from vultron.bt.roles.states import CVDRoles

logger = logging.getLogger(__name__)

pd.set_option("display.max_rows", 500)
pd.set_option("display.max_columns", 500)
pd.set_option("display.width", 1000)


def main(args) -> None:
    """
    Instantiates a `CvdProtocolBt` object and runs it until either it closes or 1000 ticks have passed.
    This demo is basically simulating a CVD agent coordinating a CVD case with itself.
    The agent's role is set to `FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR`, which means it will
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
    _setup_logger(args)

    if args.print_tree:
        logger.info("Printing tree and exiting")
        show_graph(CvdProtocolRoot)
        sys.exit()

    _run_simulation()
    _print_sim_result()


def _run_simulation():
    tick = 0
    with CvdProtocolBt() as tree:
        tree.bb.CVD_role = CVDRoles.FINDER_REPORTER_VENDOR_DEPLOYER_COORDINATOR

        for tick in range(1000):
            tick += 1
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
    logger.info(f"Closed in {tick} ticks")
    for k, v in dataclasses.asdict(tree.bb).items():
        if "history" in k:
            logger.info(f"### {k} ###")
            for i, row in enumerate(v, start=1):
                logger.info(f"  {i} {row}")


def _print_sim_result():
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


def _setup_logger(args):
    global logger
    logger = logging.getLogger()
    logger.setLevel(args.log_level)
    hdlr = logging.StreamHandler()
    logger.addHandler(hdlr)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run a Vultron behavior tree demo"
    )
    # verbpse = INFO
    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        action="store_const",
        const=logging.INFO,
        default=logging.WARNING,
        help="verbose output",
    )
    # debug = DEBUG
    parser.add_argument(
        "-d",
        "--debug",
        dest="log_level",
        action="store_const",
        const=logging.DEBUG,
        default=logging.WARNING,
        help="debug output",
    )
    # quiet = WARNING
    parser.add_argument(
        "-q",
        "--quiet",
        dest="log_level",
        action="store_const",
        const=logging.WARNING,
        default=logging.WARNING,
        help="quiet output",
    )
    # if print-tree just print the tree and exit
    parser.add_argument(
        "-t",
        "--print-tree",
        dest="print_tree",
        action="store_true",
        default=False,
        help="print the tree and exit",
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = _parse_args()
    main(args)
