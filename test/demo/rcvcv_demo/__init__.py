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


"""Tests of the ``rcvcv`` scenario package (DEMOMA-19, #5825).

:mod:`vultron.demo.scenario.rcvcv_demo` is a package of four submodules —
``cast``, ``fragments``, ``story`` and ``cli`` — and one test module here
mirrors each (CS-18-004).  ``_support.py`` holds the five-party stand-in cast
the story and fragment tests share.  Each patch names the submodule that
looks the patched name up, never the package
(``test/demo_unit/test_story_patch_targets.py``).
"""
