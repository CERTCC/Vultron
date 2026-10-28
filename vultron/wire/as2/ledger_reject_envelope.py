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

"""Recognise the ``Reject`` that carries no object (SYNC-16-007).

A ``Reject`` names what it declines in ``object``.  One Vultron message has
nothing to name: a replica whose case was replaced by a copy ahead of its
chain, and whose chain stores no entry, asks the CASE_MANAGER to replay the
case from genesis.  That ``Reject(CaseLedgerEntry)`` carries no entry, a
``ledgerPosition`` that names none (index -1, SYNC-18-001) and the case as
its ``target``.  ``as_Reject`` refuses every other ``Reject`` without an object
when it is built or parsed (ADR-0032: validate at the edge); routing uses
:func:`is_genesis_replay_reject` to send this one to the ledger handler.
"""

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Reject,
)


def is_genesis_replay_reject(activity: object) -> bool:
    """Whether *activity* is the objectless genesis-replay ``Reject``.

    It is a plain ``Reject`` with no ``object``, the empty chain's
    ``ledgerPosition`` (index -1) and a ``target`` that names the case.
    """
    return isinstance(activity, as_Reject) and activity.asks_for_genesis_replay


__all__ = ["is_genesis_replay_reject"]
