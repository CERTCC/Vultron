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

"""The story API: fragments, named prefixes, choices and the runner (#5533).

A scenario states its story once and the registry reads its path off the
story's choices, which is the only way it places itself on the tree
(DEMOCI-11-019, DEMOCI-11-024).  These tests cover the derivation, the
refusals, and the runner's own job: play the items in order and report each
choice to the harness with the deciding actor's id, so nothing places a
``reach_step`` by hand.

Kept in ``test/demo_unit/`` for the reason ``test_scenario_registry.py``
gives: ``test/demo/`` is auto-marked ``integration`` and deselected by default.

One module per submodule of :mod:`vultron.demo.helpers.story`
(CS-18-004, #5592).
"""
