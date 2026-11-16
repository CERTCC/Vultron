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
"""Committed VINCE data: synthetic fixtures and the check that refuses the
rest (VSD-02, ADR-0189).

- :mod:`.marker` holds the fixture directory, the synthetic marker and the
  names of the two tools that may write it: the generator and the sanitizer
  (#6348).
- :mod:`.shape` tells a VINCE API response apart from other JSON.
- :mod:`.generator` writes the synthetic fixtures (``vince-data generate``).
- :mod:`.cleared` reads the cleared-case list.
- :mod:`.check` is the committed-data check (``vince-data check``), run by
  pre-commit and by the ``VINCE Data Check`` workflow.
"""
