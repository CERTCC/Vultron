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

"""In-process test for the trigger exchange demo (#4254).

Each demo is run inside its own ``demo_environment`` (as ``run_exchange_demos``
does) and asserted on its own settled outcome *before* teardown resets the
stores, rather than only on "no ERROR SUMMARY" (#2241).
"""

import pytest

from test.demo._helpers import make_client, route_exchange_demo_at_testclient
from vultron.adapters.driven.datalayer_sqlite import get_datalayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.states.rm import RM
from vultron.demo.exchange import trigger_demo as demo
from vultron.demo.utils import (
    assert_demo_success,
    demo_environment,
    reset_demo_failures,
)


@pytest.fixture(scope="module")
def demo_env(client):
    """Route the demo's client at the in-process TestClient (DEMOMA-26-002)."""
    with route_exchange_demo_at_testclient(client, demo) as base:
        yield base


def _run(base: str, demo_fn):
    """Run *demo_fn*; return ``(link, vendor_rm)`` read before teardown.

    *link* is the vendor's report link; *vendor_rm* is the vendor's RM state as
    a participant of the linked case, or ``None`` when there is no such case.
    """
    reset_demo_failures()
    client = make_client(base)
    with demo_environment(client) as (finder, vendor, coordinator):
        demo_fn(client, finder, vendor, coordinator)
        assert_demo_success()
        dl = get_datalayer(vendor.id_)
        (link,) = [
            obj
            for obj in dl.list_objects("ReportCaseLink")
            if isinstance(obj, VultronReportCaseLink)
        ]
        vendor_rm = None
        case = dl.read(link.case_id) if link.case_id else None
        if isinstance(case, VulnerabilityCase):
            pid = case.actor_participant_index.get(vendor.id_)
            participant = dl.read(pid) if pid else None
            if isinstance(participant, CaseParticipant):
                status = participant.participant_status
                assert status is not None
                vendor_rm = status.rm_state
        return link, vendor_rm


def test_validate_and_engage_settles_on_an_accepted_case(demo_env):
    """Validate then engage: the report is VALID and the vendor ACCEPTED a case."""
    link, vendor_rm = _run(demo_env, demo.demo_validate_and_engage)
    assert link.rm_state == RM.VALID
    assert link.case_id is not None
    assert vendor_rm == RM.ACCEPTED


def test_invalidate_and_close_settles_closed(demo_env):
    """Invalidate then close: the report is RM.CLOSED, never engaged.

    The CaseActor still creates the case when the report arrives (the vendor's
    ``Create(CaseProposal)``), so a case exists; what distinguishes this run
    is that the vendor never leaves ``RM.RECEIVED`` on it and the report ends
    closed.
    """
    link, vendor_rm = _run(demo_env, demo.demo_invalidate_and_close)
    assert link.rm_state == RM.CLOSED
    assert link.case_id is not None
    assert vendor_rm == RM.RECEIVED


def test_every_run_is_registered():
    """Both outcomes run under ``vultron-demo trigger``."""
    assert [fn for _, fn in demo._ALL_DEMOS] == [
        demo.demo_validate_and_engage,
        demo.demo_invalidate_and_close,
    ]
