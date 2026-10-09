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

"""``reporter_submits_report`` carries the Reporter's terms on both arms.

The trigger arm hands ``proposed_embargo_end_time`` to ``ActorSession``; the
in-memory arm builds the ``EmbargoEvent`` itself, about the report
(EP-04-009), and hands it to the factory.  Transport and verification are
stubbed: what is under test is the Offer the helper produces, not delivery.
"""

from datetime import UTC, datetime

import pytest

from vultron.demo.helpers import workflow
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_NODE = "http://vendor:7999/api/v2"
_REPORTER = as_Actor(id_=f"{_NODE}/actors/finndervul", name="Finn")
_RECEIVER = as_Actor(id_=f"{_NODE}/actors/vendorco", name="VendorCo")
_END = datetime(2030, 6, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def quiet_transport(monkeypatch):
    """No node is running: delivery, provisioning and store checks are stubs."""
    monkeypatch.setattr(
        workflow, "post_to_inbox_and_wait", lambda *a, **k: None
    )
    monkeypatch.setattr(
        workflow, "_provision_case_actor", lambda *a, **k: None
    )
    monkeypatch.setattr(workflow, "verify_object_stored", lambda *a, **k: None)
    monkeypatch.setattr(
        workflow, "wait_for_report_submission_stored", lambda *a, **k: None
    )


def _client() -> DataLayerClient:
    return DataLayerClient(base_url=_NODE, actor_id=_RECEIVER.id_)


class TestInMemoryArm:
    @pytest.mark.spec("EP-04-004")
    @pytest.mark.spec("EP-04-009")
    def test_terms_ride_the_offer_about_the_report(self):
        report, offer = workflow.reporter_submits_report(
            _client(), _REPORTER, _RECEIVER, proposed_embargo_end_time=_END
        )

        proposed = offer.proposed_embargo
        assert isinstance(proposed, as_EmbargoEvent)
        assert proposed.context == report.id_
        assert proposed.end_time == _END

    def test_no_terms_means_the_default_path(self):
        _, offer = workflow.reporter_submits_report(
            _client(), _REPORTER, _RECEIVER
        )

        assert offer.proposed_embargo is None


class TestTriggerArm:
    def test_terms_are_handed_to_the_reporters_trigger(self, monkeypatch):
        seen: dict = {}

        class _FakeSession:
            def __init__(self, *, client, actor):
                seen["actor"] = actor.id_

            def submit_report(self, **kwargs):
                seen["kwargs"] = kwargs
                report_id = "urn:uuid:11111111-1111-1111-1111-111111111111"
                offer = {
                    "type": "Offer",
                    "actor": _REPORTER.id_,
                    "to": [_RECEIVER.id_],
                    "object": {
                        "type": "VulnerabilityReport",
                        "id": report_id,
                        "attributedTo": _REPORTER.id_,
                        "name": "n",
                        "content": "c",
                    },
                    "proposedEmbargo": {
                        "type": "EmbargoEvent",
                        "context": report_id,
                        "endTime": _END.isoformat(),
                    },
                }
                return type("R", (), {"offer": offer})()

        monkeypatch.setattr(workflow, "ActorSession", _FakeSession)

        report, offer = workflow.reporter_submits_report(
            _client(),
            _REPORTER,
            _RECEIVER,
            reporter_client=_client(),
            proposed_embargo_end_time=_END,
        )

        assert seen["actor"] == _REPORTER.id_
        assert seen["kwargs"]["proposed_embargo_end_time"] == _END
        assert isinstance(offer.proposed_embargo, as_EmbargoEvent)
        assert offer.proposed_embargo.context == report.id_


class TestTriggerArmDeliversOnlyThroughTheOutbox:
    """The trigger's outbox is the sole delivery; the demo never re-posts."""

    wait_args: tuple = ()

    def _record_wait(self, calls: list[str], args: tuple) -> None:
        calls.append("wait")
        self.wait_args = args

    def _run(self, monkeypatch) -> list[str]:
        calls: list[str] = []

        class _FakeSession:
            def __init__(self, *, client, actor):
                pass

            def submit_report(self, **kwargs):
                calls.append("trigger")
                report_id = "urn:uuid:22222222-2222-2222-2222-222222222222"
                offer = {
                    "type": "Offer",
                    "actor": _REPORTER.id_,
                    "to": [_RECEIVER.id_],
                    "object": {
                        "type": "VulnerabilityReport",
                        "id": report_id,
                        "attributedTo": _REPORTER.id_,
                        "name": "n",
                        "content": "c",
                    },
                }
                return type("R", (), {"offer": offer})()

        monkeypatch.setattr(workflow, "ActorSession", _FakeSession)
        monkeypatch.setattr(
            workflow,
            "post_to_inbox_and_wait",
            lambda *a, **k: calls.append("post"),
        )
        monkeypatch.setattr(
            workflow,
            "_provision_case_actor",
            lambda *a, **k: calls.append("provision"),
        )
        monkeypatch.setattr(
            workflow,
            "wait_for_report_submission_stored",
            lambda client, *args, **k: self._record_wait(calls, args),
        )
        workflow.reporter_submits_report(
            _client(), _REPORTER, _RECEIVER, reporter_client=_client()
        )
        return calls

    def test_never_hand_delivers(self, monkeypatch):
        assert "post" not in self._run(monkeypatch)

    def test_provisions_before_the_trigger_then_waits(self, monkeypatch):
        assert self._run(monkeypatch) == ["provision", "trigger", "wait"]

    def test_waits_on_the_receivers_store(self, monkeypatch):
        self._run(monkeypatch)
        receiver_id, report_id, offer_id = self.wait_args
        assert receiver_id == _RECEIVER.id_
        assert report_id.startswith("urn:uuid:2222")
        assert offer_id
