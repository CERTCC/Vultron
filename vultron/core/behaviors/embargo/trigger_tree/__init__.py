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

"""Trigger-side embargo BT compositions.

A trigger writes shared EM state only as the CASE_MANAGER (EP-09-008,
ADR-0113).  Each trigger tree therefore splits, after its
read-only routing guards, into two mutually exclusive arms
(``create_case_manager_gated_tree`` beside ``_arms._skip_at_case_manager``,
BT-17-001):

- **As the CASE_MANAGER** the actor's decision is canonical: the
  ``EmbargoLifecycle`` operation runs ``STRICT``, the decision activity is
  committed as a ledger entry the announce slots replay (EP-09-007,
  RSH-08-004, #4085), and the ``Add(CaseStatus)`` declaration follows.  The
  propose and answer arms decide on a staged store and commit the act, then
  each consent row it changes, before applying them by copying (ADR-0124,
  CLP-07-013).
  Nothing is addressed to the manager itself (CLP-10-032): its own proposal
  is relayed to each participant (EP-09-002) and its teardown is told to
  every other one (EMB-19-001, #4112).
- **As any other participant** the tree writes no EM state and declares none:
  it builds the activity, queues it to the CASE_MANAGER (PCR-08-001) and
  writes the activity id to ``result_out[ASSERTED_ACTIVITY_KEY]``, which the
  use case records in the pending-assertion store (SYNC-11-002).  The replica
  moves when the manager's commit is announced.
"""

from vultron.core.behaviors.embargo.trigger_tree._arms import (
    ABANDONMENT_LEFT_TO_CASE_MANAGER,
)
from vultron.core.behaviors.embargo.trigger_tree.answer import (
    accept_embargo_trigger_bt,
    activate_embargo_trigger_bt,
    reject_embargo_proposal_trigger_bt,
    reject_embargo_trigger_bt,
    withdraw_embargo_trigger_bt,
)
from vultron.core.behaviors.embargo.trigger_tree.proposal import (
    propose_embargo_revision_trigger_bt,
    propose_embargo_trigger_bt,
)
from vultron.core.behaviors.embargo.trigger_tree.termination import (
    end_embargo_outliving_disclosure_bt,
    reject_proposed_embargo_bt,
    terminate_embargo_bt,
)

__all__ = [
    "ABANDONMENT_LEFT_TO_CASE_MANAGER",
    "accept_embargo_trigger_bt",
    "activate_embargo_trigger_bt",
    "end_embargo_outliving_disclosure_bt",
    "propose_embargo_revision_trigger_bt",
    "propose_embargo_trigger_bt",
    "reject_embargo_proposal_trigger_bt",
    "reject_embargo_trigger_bt",
    "reject_proposed_embargo_bt",
    "terminate_embargo_bt",
    "withdraw_embargo_trigger_bt",
]
