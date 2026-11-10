#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""End-to-end verification of the "Submit a report" tutorial flow.

Runs the exact sequence the tutorial documents — create the vendor and the
finder, hand a ``Create(VulnerabilityReport)`` to the finder's outbox, which
signs it and delivers it to the vendor's inbox, read the report back — against
an isolated FastAPI ``TestClient``.  If the API drifts from what the tutorial
tells the reader to expect, this test fails.

Marked ``integration`` automatically by ``test/demo/conftest.py``.
"""

import pytest

from vultron.adapters.driving.fastapi.outbox_handler import (
    configure_default_emitter,
    get_default_emitter,
)
from vultron.demo.in_process import (
    InProcessRouter,
    create_isolated_actor_app,
)
from vultron.wire.as2.vocab.examples import submit_report_tutorial as t


@pytest.mark.spec("SIG-03-002")
def test_tutorial_flow_creates_submits_and_stores_report():
    """The tutorial's report reaches the vendor signed and verified.

    The finder's outbox signs the report, and the vendor's inbox fetches the
    finder's profile from the same server to verify the proof before it
    stores anything (SIG-01-001, SIG-02-001, SIG-03-002).
    """
    router = InProcessRouter()
    iso = create_isolated_actor_app(
        t.SERVER_ORIGIN, router, actor_slug=t.VENDOR_SLUG
    )

    # The finder's outbox delivers to the vendor through the router, as the
    # reference server delivers to its own inbox over HTTP.
    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]
    try:
        with iso.client as client:
            result = t.run_end_to_end(client)
    finally:
        configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
        iso.close()

    create, create_finder, submit, reports = (
        result["create"],
        result["create_finder"],
        result["submit"],
        result["reports"],
    )

    # Step 3: creating each actor returns 201 with the actor record.
    assert create.status_code == 201
    created = create.json()
    assert created["name"] == t.VENDOR_NAME
    assert created["type"] == t.VENDOR_ACTOR_TYPE
    assert created["id"] == t.VENDOR_ID
    assert create_finder.status_code == 201
    finder = create_finder.json()
    assert finder["name"] == t.FINDER_NAME
    assert finder["type"] == t.FINDER_ACTOR_TYPE
    assert finder["id"] == t.FINDER_ID

    # Step 4: the finder's outbox takes the report with 200 OK; it signs the
    # report and delivers it to the vendor's inbox.
    assert submit.status_code == 200, submit.text

    # Step 5: the report is now in the vendor's store, keyed by its id.  Pin the
    # whole record: the tutorial renders ``STORED_REPORT_RESPONSE`` verbatim, so
    # if the datalayer serialization ever changes, this equality fails rather
    # than the docs drifting silently from what the reader actually sees.
    assert reports.status_code == 200
    assert reports.json() == t.STORED_REPORT_RESPONSE
