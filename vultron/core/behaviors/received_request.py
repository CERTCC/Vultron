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

"""The received request a delegated emit carries out, read from the blackboard.

A delegated emit in a received tree names the activity the CASE_MANAGER
received in ``inReplyTo`` (CM-24-020).  That activity is the ``activity`` run
key ``BTBridge`` places on every received run (BT-05-003), so a node reads it
from there instead of taking a per-act constructor parameter (BTND-01-009).
:class:`ReceivedRequestInputMixin` is the one reader.
"""

from typing import Any

from py_trees.ports import PortInformation


class ReceivedRequestInputMixin:
    """Read the received activity's id and sender from the ``/activity`` run key.

    Mix it in before the node's ports base.  It adds an optional
    ``activity`` input port remapped to ``/activity`` and reads it in
    :meth:`initialise`.  Outside a received run the port is empty and both
    readers return ``None``; the delegated-authorship helper then refuses a
    distinct asker with no request (CM-24-022).
    """

    # Annotation only: binding a value here would make every class that mixes
    # this in look like it had declared its ports (py_trees' abstract check).
    INPUT_PORTS: dict[str, PortInformation]
    #: The received event, read in ``initialise()``; ``None`` before.
    _received: object | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # As in ``RecordedOfferAnswerInputMixin``: add the port to whatever
        # ``INPUT_PORTS`` the class ends up with, before the ports base
        # validates them.
        cls.INPUT_PORTS = {
            **cls.INPUT_PORTS,
            "activity": PortInformation(data_type=object, required=False),
        }
        super().__init_subclass__(**kwargs)

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        remappings = dict(super()._domain_port_remappings())  # type: ignore[misc]
        remappings["activity"] = "/activity"
        return remappings

    def initialise(self) -> None:
        super().initialise()  # type: ignore[misc]
        self._received = self._try_get_input("activity")  # type: ignore[attr-defined]

    def _received_request_id(self) -> str | None:
        """The id of the received activity, or ``None`` outside a received run."""
        value = getattr(self._received, "activity_id", None)
        return value if isinstance(value, str) and value else None

    def _received_sender_id(self) -> str | None:
        """The received activity's sender, or ``None`` outside a received run."""
        value = getattr(self._received, "actor_id", None)
        return value if isinstance(value, str) and value else None


__all__ = ["ReceivedRequestInputMixin"]
