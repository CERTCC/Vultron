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

"""The stage builders of the received-tree factory (ADR-0111, ADR-0135).

``create_receive_activity_tree`` in ``case/receive_activity_tree.py`` is the
one way to build a received-side tree; it composes the stages these modules
build, in the CLP-10-010 order.  Split out of the factory module by concern
(CS-18-001):

- ``tree``: the built tree's type, its stage list and the guarded commit.
- ``doors``: the door guards — post-close, addressee, closed sender, case
  resolution, sender guard.
- ``decisions``: the CASE_MANAGER's own decisions after the doors — clock
  decisions and the answer to a stamped ledger position.
- ``guards``: precondition guards, diversions and the refusal stage.
- ``effects``: the replica and CASE_MANAGER effect stages and their checks.

The factory module re-exports the public names, so existing imports hold.
"""
