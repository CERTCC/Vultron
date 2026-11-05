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

"""The ``vultron-demo rcvcv`` entry point and its help text.

:func:`main` is the scenario's registered entry point (ADR-0098): the demo
CLI builds the ``rcvcv`` sub-command from it, from
:data:`~vultron.demo.scenario.rcvcv_demo.cast.ROLES` and from
:data:`CLI_HELP` (DEMOCI-11-011).  It builds one client per container and
hands them to :func:`~vultron.demo.scenario.rcvcv_demo.story.run_rcvcv_demo`.
"""

from vultron.demo.helpers.actor_roles import resolved_actor_ids, role_map
from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.story_cast import (
    CASE_ACTOR_NAME,
    CastContainer,
    story_clients,
)
from vultron.demo.scenario.rcvcv_demo.cast import (
    C1_LABEL,
    C2,
    C2_LABEL,
    ROLES,
    V1_LABEL,
    V2,
    V2_LABEL,
)
from vultron.demo.scenario.rcvcv_demo.story import STORY, run_rcvcv_demo
from vultron.demo.scenario.registry import scenario

_ROLES = role_map(ROLES)

#: ``vultron-demo rcvcv --help`` text. It lives in the scenario rather than in
#: ``vultron/demo/cli/`` because the sub-command is generated from the
#: registry and the scenario is the only place that knows its own workflow.
CLI_HELP = """Run the RCVCV 5-party CVD demo (DEMOMA-19).

Five actors coordinate a full CVD lifecycle:
Reporter + C1 (CASE_OWNER) + V1 (VENDOR) + C2 (COORDINATOR) + V2
(VENDOR+DEPLOYER).

\b
Workflow:
  1. Reset all five containers and seed Reporter, C1 and V1.
  2. Reporter submits a report to C1; C1 validates and engages.
  3. C1 invites V1 (VENDOR); the Reporter asks, V1 and C1 answer in case
     notes; then C1 invites C2 (COORDINATOR).
  4. C2 suggests V2 via ADR-0026; C1 approves; V2 joins via CaseActor.
  5. Verify LedgerFanout replication across all five replicas.
  6. C2 and V2 add their notes to the thread.
  7. Fix lifecycle: V1 → VFd (no deploy); V2 → VFD (fix-deployed).
  8. Publication: V1 publishes first → embargo terminates; all publish.
  9. All actors close the case.
 10. Export case ledger JSONL for each actor (devlogs).
"""


@scenario(
    name="rcvcv",
    label="RCVCV",
    participants="Reporter + C1 + V1 + C2 + V2",
    feature="Actor-suggestion flow (ADR-0026)",
    in_pr_set=True,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    c1_url: str | None = None,
    v1_url: str | None = None,
    c2_url: str | None = None,
    v2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    v1_id: str | None = None,
    c2_id: str | None = None,
    v2_id: str | None = None,
) -> None:
    """Entry point for the RCVCV CVD workflow demo.

    Args:
        skip_health_check: Skip server availability checks.
        reporter_url: Override base URL for the Reporter container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        v1_url: Override base URL for the V1 (Vendor1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        v2_url: Override base URL for the V2 (VendorDeployer) container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        c1_id: Optional deterministic URI for the C1 actor.
        v1_id: Optional deterministic URI for the V1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        v2_id: Optional deterministic URI for the V2 actor.
    """
    clients = story_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer("c1", C1_LABEL, c1_url),
            CastContainer("v1", V1_LABEL, v1_url),
            CastContainer(C2, C2_LABEL, c2_url),
            CastContainer(V2, V2_LABEL, v2_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rcvcv_demo(
        reporter_client=clients[REPORTER],
        c1_client=clients["c1"],
        v1_client=clients["v1"],
        c2_client=clients[C2],
        v2_client=clients[V2],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            c1=(clients["c1"], c1_id),
            v1=(clients["v1"], v1_id),
            c2=(clients[C2], c2_id),
            v2=(clients[V2], v2_id),
        ),
    )
