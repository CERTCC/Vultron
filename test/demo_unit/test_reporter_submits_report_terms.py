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

"""``reporter_submits_report`` submits through the reporter's own trigger.

It hands ``proposed_embargo_end_time`` and the report text to
``ActorSession``, and never posts an Offer into the receiver's inbox: the
trigger is where the reporter writes the anchor it later checks the
receiver's case introduction against (CBT-01-005, #4675).  Transport and
verification are stubbed: what is under test is the call the helper makes,
not delivery.
"""

import pytest

from test.support.future_dates import FAR_FUTURE
from test.support.objects import make
from vultron.demo.helpers.workflow import report as workflow_report
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

_NODE = "http://vendor:7999/api/v2"
_REPORTER = make(as_Actor, id_=f"{_NODE}/actors/finndervul", name="Finn")
_RECEIVER = make(as_Actor, id_=f"{_NODE}/actors/vendorco", name="VendorCo")
_END = FAR_FUTURE  # far-future; tests that terms flow to the trigger, not a specific date


@pytest.fixture(autouse=True)
def quiet_transport(monkeypatch):
    """No node is running: provisioning and store checks are stubs."""
    monkeypatch.setattr(
        workflow_report, "_provision_case_actor", lambda *a, **k: None
    )
    monkeypatch.setattr(
        workflow_report,
        "wait_for_report_submission_stored",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        workflow_report,
        "verify_receiver_verified_sender_key",
        lambda *a, **k: None,
    )


def _client() -> DataLayerClient:
    return DataLayerClient(base_url=_NODE, actor_id=_RECEIVER.id_)


class TestTriggerArm:
    @pytest.mark.spec("EP-04-004")
    @pytest.mark.spec("EP-04-009")
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

        monkeypatch.setattr(workflow_report, "ActorSession", _FakeSession)

        report, offer = workflow_report.reporter_submits_report(
            _client(),
            _REPORTER,
            _RECEIVER,
            reporter_client=_client(),
            proposed_embargo_end_time=_END,
        )

        assert seen["actor"] == _REPORTER.id_
        assert seen["kwargs"]["proposed_embargo_end_time"] == _END
        assert seen["kwargs"]["recipient_id"] == _RECEIVER.id_
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

        monkeypatch.setattr(workflow_report, "ActorSession", _FakeSession)
        # Any hand delivery leaves the demo as an inbox POST on some client, so
        # record it at the transport, wherever the posting helper is imported.

        def _record_call(_self, method, path: str, **_kwargs) -> dict:
            if str(method).upper().endswith("POST") and "/inbox" in path:
                calls.append("post")
            return {}

        monkeypatch.setattr(DataLayerClient, "call", _record_call)
        monkeypatch.setattr(
            workflow_report,
            "_provision_case_actor",
            lambda *a, **k: calls.append("provision"),
        )
        monkeypatch.setattr(
            workflow_report,
            "wait_for_report_submission_stored",
            lambda client, *args, **k: self._record_wait(calls, args),
        )
        workflow_report.reporter_submits_report(
            _client(), _REPORTER, _RECEIVER, reporter_client=_client()
        )
        return calls

    @pytest.mark.spec("DEMOMA-05-001")
    @pytest.mark.spec("CBT-01-005")
    def test_never_hand_delivers(self, monkeypatch):
        """No path builds the Offer and posts it into the receiver's inbox."""
        assert "post" not in self._run(monkeypatch)

    def test_provisions_before_the_trigger_then_waits(self, monkeypatch):
        assert self._run(monkeypatch) == ["provision", "trigger", "wait"]

    def test_waits_on_the_receivers_store(self, monkeypatch):
        self._run(monkeypatch)
        receiver_id, report_id, offer_id = self.wait_args
        assert receiver_id == _RECEIVER.id_
        assert report_id.startswith("urn:uuid:2222")
        assert offer_id


class TestReportText:
    def test_callers_name_their_own_report(self, monkeypatch):
        """Exchange demos submit their own report text through the trigger."""
        seen: dict = {}

        class _FakeSession:
            def __init__(self, *, client, actor):
                pass

            def submit_report(self, **kwargs):
                seen.update(kwargs)
                offer = {
                    "type": "Offer",
                    "actor": _REPORTER.id_,
                    "to": [_RECEIVER.id_],
                    "object": {
                        "type": "VulnerabilityReport",
                        "id": "urn:uuid:33333333-3333-3333-3333-333333333333",
                        "attributedTo": _REPORTER.id_,
                        "name": kwargs["report_name"],
                        "content": kwargs["report_content"],
                    },
                }
                return type("R", (), {"offer": offer})()

        monkeypatch.setattr(workflow_report, "ActorSession", _FakeSession)

        report, _ = workflow_report.reporter_submits_report(
            _client(),
            _REPORTER,
            _RECEIVER,
            reporter_client=_client(),
            report_name="Use-After-Free",
            report_content="A use-after-free in the allocator.",
        )

        assert seen["report_name"] == "Use-After-Free"
        assert seen["report_content"] == "A use-after-free in the allocator."
        assert report.name == "Use-After-Free"
