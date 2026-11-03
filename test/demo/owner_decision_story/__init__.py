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


"""Tests of the two ``owner-keep-case`` continuations (#5535, #5592).

``owner-keep-case`` is decided in both halves of the scenario tree, so each of
its continuations is written once in
:mod:`vultron.demo.helpers.owner_decision_story` and takes its cast as
:class:`~vultron.demo.helpers.owner_decision_story.Part`\\ s off the running
story (DEMOMA-17-001).  Every test here therefore drives the continuations
with a **neutral** cast — ``owner``, ``joiner``, ``newcomer`` — which is the
claim itself: a continuation that named either pair's actors could not be run
this way at all.

``demo_gate`` / ``demo_check`` / ``demo_step`` stay real wherever a test is
about a gate skipping its dependents, and are stubbed to ``nullcontext`` only
where it is about call shape (``test_demo_context_managers.py`` owns their
behaviour).

One module per submodule of :mod:`vultron.demo.helpers.owner_decision_story`
(CS-18-004); the neutral cast and the stand-in story they share are in
``_support.py``.  Each patch names the submodule that looks the patched name
up, never the package (``test/demo_unit/test_story_patch_targets.py``).
"""
