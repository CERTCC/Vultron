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

Runs the exact sequence the tutorial documents — create an actor, submit a
``Create(VulnerabilityReport)`` to its inbox, read the report back — against an
isolated FastAPI ``TestClient``.  If the API drifts from what the tutorial
tells the reader to expect, this test fails.

Marked ``integration`` automatically by ``test/demo/conftest.py``.
"""

from vultron.wire.as2.vocab.examples import submit_report_tutorial as t

from test.demo.conftest import _TestClientRouter, create_isolated_actor_app


def test_tutorial_flow_creates_submits_and_stores_report():
    router = _TestClientRouter()
    iso = create_isolated_actor_app(
        "http://vendor.test", router, actor_slug=t.VENDOR_SLUG
    )

    with iso.client as client:
        result = t.run_end_to_end(client)

    create, submit, reports = (
        result["create"],
        result["submit"],
        result["reports"],
    )

    # Step 3: creating the vendor actor returns 201 with the actor record.
    assert create.status_code == 201
    created = create.json()
    assert created["name"] == t.VENDOR_NAME
    assert created["type"] == t.VENDOR_ACTOR_TYPE
    assert created["id"].endswith(f"/actors/{t.VENDOR_SLUG}")

    # Step 4: the actor acknowledges the report with 202 Accepted.
    assert submit.status_code == 202

    # Step 5: the report is now in the vendor's store, keyed by its id.  Pin the
    # whole record: the tutorial renders ``STORED_REPORT_RESPONSE`` verbatim, so
    # if the datalayer serialization ever changes, this equality fails rather
    # than the docs drifting silently from what the reader actually sees.
    assert reports.status_code == 200
    assert reports.json() == t.STORED_REPORT_RESPONSE
