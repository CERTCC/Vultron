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

"""Tests of the coordinator-first family's story package (#5533, #5534, #5592).

One module per submodule of :mod:`vultron.demo.helpers.coordinated_story`
(CS-18-004).  The client and ledger-dump plumbing every family shares is
pinned in ``test/demo/test_story_cast.py``.

Every test patches the collaborators out, so no HTTP happens; ``demo_gate`` /
``demo_check`` / ``demo_step`` are left real wherever the test is about
control flow, and stubbed to ``nullcontext`` only where it is about call
shape (``test_demo_context_managers.py`` owns their behaviour).  Each patch
names the submodule that looks the patched name up, never the package
(``test/demo/test_story_patch_targets.py``).

These tests are mock-only, yet they live under ``test/demo/`` rather than
``test/demo_unit/`` — and so are auto-marked ``integration`` by that
directory's ``conftest.py`` — because they depend on its autouse fixtures:
``stub_summary_seed`` and ``stub_full_case_reply`` skip the two chain steps
that have no container to talk to when the client is a mock (#5444), and the
ledger-rebuild guard runs on the way out.  ``test/demo_unit/test_story.py``
states the other half of the rule: a test that needs none of those fixtures
belongs there.
"""
