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
"""The two errors the call-out seam raises (ADR-0183, BT-18-018).

Both are plain :class:`RuntimeError` subclasses and **not**
:class:`~vultron.errors.VultronError`, so ``BTBridge`` reports either as
``internal_error=True`` rather than as a protocol ``FAILURE``: the message is
not judged and stays in holding.
"""

from __future__ import annotations


class CallOutContractError(RuntimeError):
    """A call-out backend broke the seam's contract.

    Raised for a ``RUNNING`` return (BT-18-011), a backend that is not a
    :class:`~vultron.core.behaviors.call_out.backend.CallOutBackend`, and an
    answer outside the three verdicts or carrying data its declaration does
    not name (ADR-0183).

    Deliberately a plain :class:`RuntimeError` and **not** a
    :class:`~vultron.errors.VultronError`: ``BTBridge`` treats a
    ``VultronError`` as a protocol-attributable ``FAILURE`` but any other
    exception as ``internal_error=True``.  A mis-wired backend is a wiring
    bug, not a protocol outcome.
    """


class CallOutBackendError(RuntimeError):
    """A call-out backend answered *error*: it could not decide or act.

    Names the node and carries the backend's diagnostics.  A plain
    :class:`RuntimeError`, not a :class:`~vultron.errors.VultronError`, so
    ``BTBridge`` reports it as ``internal_error=True`` and the message is not
    judged: it stays in holding to be tried again (ADR-0183).
    """

    def __init__(self, node_name: str, diagnostics: str) -> None:
        super().__init__(
            f"Call-out backend {node_name!r} answered error: {diagnostics}"
        )
        self.node_name = node_name
        self.diagnostics = diagnostics


__all__ = ["CallOutBackendError", "CallOutContractError"]
