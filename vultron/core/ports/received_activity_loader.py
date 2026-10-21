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

"""Driven port for loading a received activity from its archived body.

A receiver holds a received activity as the body that arrived, never as a
summary of it (CLP-10-017, ADR-0149).  Core cannot parse that body itself
(ARCH-01-001), so it loads it through this port: the adapter parses the body
through the inbox's own parse and extraction and returns the extracted
activity as a read-only view.  It is the one way core reads a received
activity's facts (DL-06-001).

The trigger-side adapter (``TriggerActivityAdapter``) implements it, since
the triggers that answer a received activity are its readers, and the same
adapter is the reply seam that parses the body again to embed it
(DL-06-004).  See ``vultron/adapters/received_archive.py``.
"""

from typing import Protocol

from vultron.core.models.received_activity_view import ReceivedActivityView


class ReceivedActivityLoader(Protocol):
    """Load a received activity from the body this actor holds."""

    def load_received_activity(
        self, activity_id: str
    ) -> ReceivedActivityView | None:
        """The received activity *activity_id* as this actor holds it.

        Loaded from intake's ``ReceivedActivityRecord``, or, while the inbox
        defers it until its case is known, from the ``DeferredInboxActivity``
        that holds it; both are keyed by the receiver (DL-06-006).  The body
        is parsed and extracted afresh on every call, so the view is what the
        delivery saw and nothing a caller does to it reaches the next load.

        Returns ``None`` when this actor holds no received activity under
        *activity_id*; nothing is read under the id its sender chose.
        """
        ...
