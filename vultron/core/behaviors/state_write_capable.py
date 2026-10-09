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

"""The one marker every BT node that writes participant or case state carries.

A node is *state-write-capable* when its ``update()`` can write participant or
case state: a ``CaseParticipant`` or its ``ParticipantStatus`` history, the
``VulnerabilityCase`` (its participant index, notes, reports, case statuses,
embargo lists, recommendations), or an embargo's lifecycle and consent rows,
whether through the DataLayer directly or through ``EmbargoLifecycle`` and the
replica-seeding services.

RSH-08-003 lets a received-side tree make such a write only at the case's
CASE_MANAGER; every other replica obtains the state from the ledger
(PCR-03-001).  ``test/architecture/test_received_tree_state_writes_are_gated.py``
builds every received-side tree and holds each marked node outside a
CASE_MANAGER gate to an owned exemption, and checks that every class reaching
a state-write seam carries the marker or is pinned as writing no case state.

The marker is the state-write analogue of
:class:`~vultron.core.behaviors.emit_capable.EmitCapable`: it carries no
behaviour, and ``create_receive_activity_tree`` does not refuse it yet — the
gating half of RSH-08-003 (#3814) moves the writes under the gate.

Not marked, on purpose: storing the received activity or its object
(CLP-10-017 intake, ``StoreReceivedObjectNode``), ledger records and
replication state (gated by ledger authority, ADR-0073), and an actor's local
bookkeeping that is not a record of the case (report-case links, proposal
admission and retry markers, dead letters).
"""

__all__ = ["StateWriteCapable"]


class StateWriteCapable:
    """Marker mixin: this node can write participant or case state (RSH-08-003).

    Carries no behaviour.  Mix it into the node class (or its domain base) so
    an ``isinstance`` check finds every state writer, however it reaches the
    store.
    """
