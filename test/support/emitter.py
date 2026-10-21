#!/usr/bin/env python

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
"""An outbox emitter that records what it would deliver, sending nothing."""

import json
from typing import Any


class RecordingEmitter:
    """Keeps every body the outbox delivers, and to whom, sending nothing.

    A test app with no emitter delivers over HTTP; a receiver that answers a
    failed delivery with a fault (ASK-07-010) would then wait out the
    delivery retries against a host that does not exist.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[dict[str, Any], list[str]]] = []

    async def emit(
        self, activity_id: str, json_body: str, recipients: list[str]
    ) -> None:
        self.sent.append((json.loads(json_body), list(recipients)))

    def to(self, recipient: str) -> list[dict[str, Any]]:
        """Every body delivered to *recipient*."""
        return [body for body, to in self.sent if recipient in to]
