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

"""Received-side BT factory for the close-case workflow (ADR-0022).

Implements receiver-side role semantics for Leave(VulnerabilityCase):

- **Owner Leave** (sender holds ``CVDRole.CASE_OWNER``): expires every
  embargo Invite still awaiting a reply (CM-23-014), advances the leaving
  participant to ``RM.CLOSED``, then advances the CaseActor to ``RM.CLOSED``, committing
  one status entry per RM transition for each and fanning each out to the
  participants not at ``RM.CLOSED`` (CM-23-022, CM-23-002, CM-23-004,
  CM-23-033).  The CaseActor's own ``RM.CLOSED`` status entry is the last
  entry of the closure and the owner-close write boundary (ADR-0085); no
  entry marks the closure itself (ADR-0152) — **unless** an embargo is still
  live, in which case the close is declined with an ``as:Reject`` and none of
  the closure effects run (CM-23-011).
- **Non-owner Leave**: advances only the leaving participant to ``RM.CLOSED``,
  committing one status entry per RM transition; the case remains open for
  remaining participants (CM-23-003, CM-23-030).

Every RM closure step the CASE_MANAGER writes is its own ledger entry, after
the ``close_case`` entry that records the Leave.  A replica applies those
status entries and never works out a closure path itself; applying
``close_case`` changes no RM state (CM-23-023, CM-23-024).
- **Any Leave after the case is fully closed**: the factory's post-close guard
  refuses it ahead of both arms, so no ``close_case`` entry is committed or
  fanned out and no one advances (CM-23-013).  Under
  ``PostCloseReply.REJECT`` the sender gets ``Reject(Leave(VulnerabilityCase))``;
  under the default ``DROP`` it gets nothing (ADR-0131).
- **A Leave from a sender with no standing**: the sender guard the factory
  composes from the use case's declared rule refuses it before the
  close/decline decision, so nothing is committed, declined or sent
  (HP-01-006, HP-01-008).  A Leave from a sender whose closure the case
  already records never reaches this tree: the use case reports it
  ``SKIPPED`` first (CM-23-049, ID-05-003).

The owner-or-participant arm is picked by
:class:`~vultron.core.behaviors.role_condition.ActorHoldsRoleInCaseNode`
reading the sender's ``CVDRole.CASE_OWNER``, a tree-level condition node, per
BTND-08-001/BTND-08-002 (role checks MUST be in the tree, not in action node
``update()`` logic).

Per ADR-0050: ``Leave(VulnerabilityCase)`` is the only canonical RM closure
path.  The CaseActor's closure entries are written here on the Case Actor
receive path; every replica whose closure the ledger does not already record
learns of them via Announce(CaseLedgerEntry) fan-out.  A participant at RM
``CLOSED`` — every earlier leaver, and the Case Owner once its own status
entries are committed — is not sent them (CM-23-004): it receives the entries
that record its own closure and nothing after them.

The package is split by concern (CS-18-005): ``factory`` composes the tree
and ``closure_effects`` builds the role-discriminating RM closure.
"""

from vultron.core.behaviors.case.receive_close_case_tree.factory import (
    create_close_case_received_tree,
)

__all__ = ["create_close_case_received_tree"]
