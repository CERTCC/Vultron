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

"""``ActorSession.submit_report`` states the Reporter's terms only when given.

The trigger body model ignores unknown keys (TRIG-03-002), so the one way a
proposal is silently lost is a body that spells the key differently or sends it
when nothing was proposed.  The kwargs ratchet pins the spelling; this pins
the presence rule and the wire form of the instant.  #3971.
"""

from datetime import datetime, timedelta, timezone

import pytest

from vultron.demo import actor_session as session_module
from vultron.demo.actor_session import ActorSession
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

_NODE = "http://vendor:7999/api/v2"
_REPORTER = as_Actor(id_=f"{_NODE}/actors/finndervul", name="Finn der Vul")


@pytest.fixture
def posted(monkeypatch):
    """Capture the body ``ActorSession`` hands to the trigger transport."""
    captured: dict = {}

    def fake_post_to_trigger(*, client, actor_id, behavior, body, path_prefix):
        captured.update(behavior=behavior, body=body)
        return {"offer": {"type": "Offer"}}

    monkeypatch.setattr(
        session_module, "post_to_trigger", fake_post_to_trigger
    )
    return captured


def _session() -> ActorSession:
    return ActorSession(
        client=DataLayerClient(base_url=_NODE), actor=_REPORTER
    ).quiet()


def test_no_terms_sends_no_proposed_end_key(posted):
    _session().submit_report(
        report_name="n", report_content="c", recipient_id=f"{_NODE}/actors/v"
    )

    assert posted["behavior"] == "submit-report"
    assert "proposed_embargo_end_time" not in posted["body"]


def test_terms_are_sent_as_an_iso_instant(posted):
    end = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc) + timedelta(0)

    _session().submit_report(
        report_name="n",
        report_content="c",
        recipient_id=f"{_NODE}/actors/v",
        proposed_embargo_end_time=end,
    )

    assert posted["body"]["proposed_embargo_end_time"] == end.isoformat()
    assert posted["body"]["proposed_embargo_end_time"].endswith("+00:00")
