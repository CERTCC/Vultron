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
"""Guards for the "Submit a report" tutorial's rendered examples.

The tutorial displays the output of the renderers in
``vultron.wire.as2.vocab.examples.submit_report_tutorial`` via ``markdown-exec``.
These tests pin the wire format of the payload and the content of the rendered
commands so the page cannot drift from a working request.  The end-to-end HTTP
flow is exercised separately in ``test/demo/test_submit_report_tutorial.py``.
"""

import json

from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.examples import submit_report_tutorial as t
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)


def test_payload_parses_as_create_vulnerability_report():
    """The rendered payload must parse as a Create wrapping a report.

    This is the guard that fails if the wire format changes underneath the
    tutorial: the server parses the inbox body with the same ``parse_activity``.
    """
    activity = parse_activity(t.create_report_activity_body())

    assert isinstance(activity, as_Create)
    assert isinstance(activity.object_, as_VulnerabilityReport)
    assert activity.object_.id_ == t.REPORT_ID
    assert activity.object_.content == t.REPORT_CONTENT


def test_activity_is_addressed_to_the_vendor():
    """The activity must address the vendor, or the inbox gate refuses it."""
    body = t.create_report_activity_body()

    assert body["to"] == [t.VENDOR_SLUG]
    assert body["actor"] == t.FINDER_ID


def test_vendor_create_body_matches_documented_fields():
    body = t.vendor_create_body()

    assert body == {
        "name": t.VENDOR_NAME,
        "actor_type": t.VENDOR_ACTOR_TYPE,
        "id": t.VENDOR_SLUG,
    }


def test_endpoint_paths_are_the_documented_ones():
    assert t.actors_path() == "/api/v2/actors/"
    assert t.inbox_path() == "/api/v2/actors/vendorco/inbox/"
    assert t.reports_path() == "/api/v2/actors/vendorco/datalayer/Reports/"
    assert t.health_path() == "/api/v2/health/live"


def test_rendered_commands_are_bash_blocks_with_canonical_values():
    create = t.render_create_actor()
    submit = t.render_submit_report()
    verify = t.render_verify()

    for block in (create, submit, verify):
        assert block.startswith("```bash\n")
        assert block.rstrip().endswith("```")
        assert "http://localhost:7999" in block

    # The create command carries the actor body; the submit command carries the
    # report; the verify command reads the reports store.
    assert '"id": "vendorco"' in create
    assert t.REPORT_CONTENT in submit
    assert t.reports_path() in verify


def test_rendered_payload_is_deterministic_json():
    payload = t.render_payload()

    assert payload.startswith("```json\n")
    # Fixed identifiers and timestamps keep the docs build reproducible.
    assert t.ACTIVITY_ID in payload
    assert "2026-01-01T00:00:00" in payload
    # The rendered block is valid JSON once the fences are removed.
    inner = payload.split("\n", 1)[1].rsplit("\n```", 1)[0]
    json.loads(inner)


def test_submit_command_body_matches_payload_and_is_deterministic():
    """The posted body must be reproducible and match the displayed payload.

    The activity's own ``published``/``updated`` default to build time; if they
    leaked into the posted body the docs would churn on every build and the
    command would disagree with the payload block above it.
    """
    body = t.create_report_activity_body()
    assert "published" not in body
    assert "updated" not in body

    # The command shows the same message the payload block shows.
    payload_inner = t.render_payload().split("\n", 1)[1].rsplit("\n```", 1)[0]
    assert json.loads(payload_inner) == body

    # The nested report keeps its fixed timestamp; no build-time date leaks in.
    assert "2026-01-01T00:00:00" in t.render_submit_report()


def test_render_stored_report_renders_the_pinned_record():
    """The Step 5 store response is rendered verbatim from the pinned record."""
    block = t.render_stored_report()

    assert block.startswith("```json\n")
    inner = block.split("\n", 1)[1].rsplit("\n```", 1)[0]
    assert json.loads(inner) == t.STORED_REPORT_RESPONSE
    # The record is keyed by the report id and carries the fixed timestamps.
    assert t.REPORT_ID in t.STORED_REPORT_RESPONSE
    assert t.STORED_REPORT_RESPONSE[t.REPORT_ID]["content"] == t.REPORT_CONTENT
