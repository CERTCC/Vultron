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

"""The RCVCV cast: its names for the five actors, their seats and devlogs.

C1 and V1 are the family's Coordinator and Vendor, so the story reaches them
under those names; ``c1`` and ``v1`` remain their names on the command line
and in the devlogs the invariant harness reads (DEMOMA-19-018).  C2 and V2 are
character actors, seated in cast slots 3 and 4 (DEMOCI-11-020).  The cast table
itself is ``vultron/demo/helpers/cast.py``.
"""

from vultron.demo.helpers.actor_roles import ActorRole, case_actor_role
from vultron.demo.helpers.cast import (
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
)

#: This scenario's names for the family's Coordinator and Vendor.  C1 is the
#: Coordinator that receives the report and holds CASE_OWNER, V1 the first
#: Vendor; the story seats them under the family's role names, so one copy of
#: the shared opening serves ``rcv`` and ``rcvcv`` alike (DEMOCI-11-018).
C1 = COORDINATOR
C1_LABEL = "C1"
V1 = VENDOR
V1_LABEL = "V1"
C2 = "c2"
C2_LABEL = "C2"
V2 = "v2"
V2_LABEL = "V2"

#: The devlogs directory each replica's ledger is dumped under: the scenario's
#: own name for the actor, which is what its invariant harness loads
#: (DEMOMA-19-018, DEMOMA-19-020).
DEVLOG_REPLICAS: tuple[tuple[str, str], ...] = (
    (REPORTER, REPORTER),
    ("c1", C1),
    ("v1", V1),
    (C2, C2),
    (V2, V2),
)

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(
        "c1", COORDINATOR_SLOT, "C1 (Coordinator1/CASE_OWNER)", has_id=True
    ),
    ActorRole("v1", VENDOR_SLOT, "V1 (Vendor1)", has_id=True),
    ActorRole(C2, CAST[3], "C2 (Coordinator2)", has_id=True),
    ActorRole(V2, CAST[4], "V2 (VendorDeployer)", has_id=True),
    case_actor_role(),
]
