#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Shared set-up for the sweep's builders: a ``LedgerNetwork`` delivery."""

import json
from typing import Any

from test.support.received import received_event
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.wire.as2.parser import parse_activity

from .._ledger_network import MANAGER, LedgerNetwork
from . import Scenario


def event_for(net: LedgerNetwork, activity: Any, *, to: str = MANAGER) -> Any:
    """*activity* as *to*'s inbox extracts it, stamped as its sender sends it."""
    body = net.stamp(json.loads(dump_outbound_body(activity)), receiver=to)
    return received_event(
        parse_activity(body), as_sent=True, receiving_actor_id=to
    )


def deliver(
    net: LedgerNetwork, activity: Any, *, to: str = MANAGER, **kwargs: Any
) -> Scenario:
    """A scenario delivering *activity* from its sender's outbox to *to*."""
    return Scenario(
        dl=net.stores[to], event=event_for(net, activity, to=to), **kwargs
    )


__all__ = ["deliver", "event_for"]
