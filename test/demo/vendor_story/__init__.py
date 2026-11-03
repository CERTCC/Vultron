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

"""Tests of the vendor-first family's story package (#5536, #5592).

``rv``, ``rvv``, ``rvcv-extension`` and ``rvcv-handoff`` open the same way —
the Reporter submits its report to a Vendor, the Vendor engages the case as
CASE_OWNER, and the Reporter then asks whether a workaround exists and the
Vendor answers — and :mod:`vultron.demo.helpers.vendor_story` is that one
copy of the code.  One module here per submodule of it (CS-18-004).

The tests here own what the family shares; each scenario's own module owns
its own fragments, and ``test_vendor_coordinator_story.py`` owns the
``rvcv`` pair's opening, which continues this one.  Every test patches the
collaborators out, so no HTTP happens; ``demo_gate`` / ``demo_check`` /
``demo_step`` stay real wherever the test is about control flow and are
stubbed to ``nullcontext`` only where it is about call shape
(``test_demo_context_managers.py`` owns their behaviour).  Each patch names
the submodule that looks the patched name up, never the package
(``test/demo_unit/test_story_patch_targets.py``).
"""
