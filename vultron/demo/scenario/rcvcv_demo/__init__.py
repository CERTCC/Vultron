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

"""Reporter + Coordinator1 + Vendor1 + Coordinator2 + VendorDeployer (RCVCV) demo.

Orchestrates the full CVD lifecycle across five actor containers plus a
dedicated CaseActor:
  - Reporter: the report submitter
  - C1 (cast slot 2, the first Coordinator): CASE_OWNER throughout; receives
    the report
  - V1 (cast slot 1, the first Vendor): CVDRole.VENDOR only; advances to VFd
    (fix-ready, no deploy step)
  - C2 (cast slot 3, a character actor): CVDRole.COORDINATOR participant;
    asks its participant suggester who else belongs (BT-24-007) and
    suggests the V2 it names via the ADR-0026 suggest-actor flow
  - V2 (cast slot 4, a character actor): CVDRole.VENDOR + CVDRole.DEPLOYER;
    advances to VFD (fix-ready then fix-deployed).  Both roles come from the
    Invite that seats it, not from its container (DEMOCI-11-021).

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.

The scenario is a package of one name (DEMOCI-11-003), grouped by concern
(CS-18-001):

* :mod:`~.cast` — the scenario's names for its five actors, their seats
  (``ROLES``) and the devlogs names the invariant harness reads.
* :mod:`~.fragments` — the story fragments only ``rcvcv`` tells.
* :mod:`~.story` — the assembled ``STORY`` and the run that plays it.
* :mod:`~.cli` — the registered ``main()`` entry point and its help text.

This ``__init__`` only re-exports (CS-18-003): importing the package
registers the scenario, and the demo CLI reads ``ROLES``, ``CLI_HELP`` and
``STORY`` here.  A test patches a name a fragment looks up on the submodule
that resolves it, never on this package
(``test/demo_unit/test_story_patch_targets.py``).

Spec: DEMOMA-19 (GitHub issue #1925).
"""

from vultron.demo.scenario.rcvcv_demo.cast import (
    C1,
    C1_LABEL,
    C2,
    C2_LABEL,
    DEVLOG_REPLICAS,
    ROLES,
    V1,
    V1_LABEL,
    V2,
    V2_LABEL,
)
from vultron.demo.scenario.rcvcv_demo.cli import CLI_HELP, main
from vultron.demo.scenario.rcvcv_demo.story import STORY, run_rcvcv_demo

__all__ = [
    "C1",
    "C1_LABEL",
    "C2",
    "C2_LABEL",
    "CLI_HELP",
    "DEVLOG_REPLICAS",
    "ROLES",
    "STORY",
    "V1",
    "V1_LABEL",
    "V2",
    "V2_LABEL",
    "main",
    "run_rcvcv_demo",
]
