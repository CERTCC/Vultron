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
"""The base class every call-out backend subclasses (ADR-0183).

A backend implements one method, :meth:`CallOutBackend.answer`, which returns
a :class:`~vultron.core.behaviors.call_out.answer.CallOutAnswer`.  It declares
the data each verdict carries in its ``contract`` class attribute.  It never
writes its declared ports itself and never chooses a ``Status``: the seam
(:class:`~vultron.core.behaviors.call_out.guard.SynchronousCallOut`) reads the
answer, checks it against ``contract``, and turns it into tree behaviour.

How the answer reaches the seam is a returned value held in a slot: the seam
ticks the backend, the backend's ``update()`` stores what ``answer()``
returned, and the seam takes it in its own ``update()`` immediately after.
The seam arms the backend for that one tick (:meth:`CallOutBackend.arm`), and
a backend ticked without it, whether in a tree or directly through
``unwrap_call_out``, raises, so nothing but the seam reads an answer.
"""

from __future__ import annotations

from typing import ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.call_out.answer import (
    BINARY_CONTRACT,
    CallOutAnswer,
    CallOutContract,
    CallOutVerdict,
)
from vultron.core.behaviors.call_out.errors import CallOutContractError


class CallOutBackend(py_trees.behaviour.Behaviour):
    """A call-out backend: answers *yes*, *no* or *error* (ADR-0183).

    Subclasses override :meth:`answer` and, when the capability carries data,
    ``contract``.  They do not override ``update()``.

    The backend's own ``status`` after a tick is ``SUCCESS`` for *yes* and
    ``FAILURE`` otherwise; it is for display only.  The seam decides what the
    tree sees.
    """

    #: The capability declaration this backend answers against (AC-1).
    contract: ClassVar[CallOutContract] = BINARY_CONTRACT

    def __init__(self, name: str = "") -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._answer: object | None = None
        self._armed = False

    def answer(self) -> CallOutAnswer:
        """Return this backend's answer for the current tick."""
        raise NotImplementedError(
            f"{type(self).__name__}.answer() must be implemented"
        )

    def update(self) -> Status:
        """Hold :meth:`answer`'s return for the seam; never read by a tree."""
        armed, self._armed = self._armed, False
        if not armed:
            raise CallOutContractError(
                f"Call-out backend {self.name!r} ({type(self).__name__}) was "
                "ticked outside the call-out seam; build it through a "
                "call-out bundle so SynchronousCallOut reads its answer "
                "(ADR-0183)."
            )
        answer = self.answer()
        self._answer = answer
        if (
            isinstance(answer, CallOutAnswer)
            and answer.verdict is CallOutVerdict.YES
        ):
            return Status.SUCCESS
        return Status.FAILURE

    def arm(self) -> None:
        """Admit one tick; called only by the seam, just before it ticks us."""
        self._armed = True

    def disarm(self) -> None:
        """Withdraw an unused arm; the seam calls it when its tick ends."""
        self._armed = False

    def take_answer(self) -> object | None:
        """Return the held answer and clear the slot (the seam's one read)."""
        answer, self._answer = self._answer, None
        return answer


__all__ = ["CallOutBackend"]
