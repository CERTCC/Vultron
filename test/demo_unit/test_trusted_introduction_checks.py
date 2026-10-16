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


"""The introduction checks: the demo's ``demo_check`` and the test assertion.

``verify_reporter_trusts_introduction`` records a failed wait and lets the demo
go on; ``expect_trusted_introductions`` turns what the demo checked into test
assertions (#4675).  Transport is stubbed: what is under test is how each one
reads a passing and a failing check.
"""

import logging

import pytest

from test.demo import _helpers
from test.demo._helpers import expect_trusted_introductions
from vultron.demo import utils
from vultron.demo.helpers import workflow
from vultron.demo.utils import DataLayerClient
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_NODE = "http://node.test/api/v2"
_REPORTER = as_Actor(id_=f"{_NODE}/actors/finder", name="Finder")
_RECEIVER = as_Actor(id_=f"{_NODE}/actors/vendor", name="Vendor")
_REPORT = as_VulnerabilityReport(
    id_="urn:uuid:88888888-8888-8888-8888-888888888888",
    attributed_to=_REPORTER.id_,
    name="n",
    content="c",
)
_CASE = "urn:uuid:99999999-9999-9999-9999-999999999999"


def _client() -> DataLayerClient:
    return DataLayerClient(base_url=_NODE, actor_id=_REPORTER.id_)


@pytest.fixture(autouse=True)
def _clean_failures():
    utils.reset_demo_failures()
    yield
    utils.reset_demo_failures()


def _check() -> str | None:
    return workflow.verify_reporter_trusts_introduction(
        _client(), _REPORTER, _RECEIVER, _REPORT, case_id=_CASE
    )


class TestVerifyReporterTrustsIntroduction:
    def test_returns_the_bound_case_and_passes_the_expected_one(
        self, monkeypatch
    ):
        seen: dict = {}

        def _wait(client, reporter_id, receiver_id, report_id, **kwargs):
            seen.update(
                reporter=reporter_id, receiver=receiver_id, report=report_id
            )
            seen.update(kwargs)
            return _CASE

        monkeypatch.setattr(workflow, "wait_for_reporter_introduction", _wait)

        assert _check() == _CASE
        assert seen == {
            "reporter": _REPORTER.id_,
            "receiver": _RECEIVER.id_,
            "report": _REPORT.id_,
            "case_id": _CASE,
        }
        assert utils._demo_failures == []

    def test_a_failed_wait_is_recorded_and_returns_none(self, monkeypatch):
        def _wait(*args, **kwargs):
            raise AssertionError("introduction refused (CBT-01-011)")

        monkeypatch.setattr(workflow, "wait_for_reporter_introduction", _wait)

        assert _check() is None
        assert len(utils._demo_failures) == 1
        assert "CBT-01-011" in utils._demo_failures[0]


class TestExpectTrustedIntroductions:
    """Each way the demo's introduction can go wrong fails the test."""

    def _stub(self, monkeypatch, *, case_id, links):
        def _wait(client, reporter_id, receiver_id, report_id, **kwargs):
            if case_id is None:
                raise AssertionError("timed out")
            return case_id

        monkeypatch.setattr(workflow, "wait_for_reporter_introduction", _wait)
        monkeypatch.setattr(
            _helpers, "_reporter_links", lambda *_args: list(links)
        )

    def test_a_trusted_introduction_passes(self, monkeypatch, caplog):
        self._stub(monkeypatch, case_id=_CASE, links=[(_RECEIVER.id_, _CASE)])
        with (
            caplog.at_level(logging.WARNING),
            expect_trusted_introductions(caplog),
        ):
            assert _check() == _CASE

    def test_a_logged_refusal_fails(self, monkeypatch, caplog):
        self._stub(monkeypatch, case_id=_CASE, links=[(_RECEIVER.id_, _CASE)])
        with pytest.raises(AssertionError, match="refused"):
            with (
                caplog.at_level(logging.WARNING),
                expect_trusted_introductions(caplog),
            ):
                _check()
                logging.getLogger("vultron.test").warning(
                    "Refusing the introduction (CBT-01-011)"
                )

    def test_no_check_fails(self, monkeypatch, caplog):
        self._stub(monkeypatch, case_id=_CASE, links=[])
        with pytest.raises(AssertionError, match="never checked"):
            with (
                caplog.at_level(logging.WARNING),
                expect_trusted_introductions(caplog),
            ):
                pass

    @pytest.mark.parametrize(
        "links",
        [
            [(f"{_NODE}/actors/someone-else", _CASE)],
            [(_RECEIVER.id_, None)],
            [(_RECEIVER.id_, _CASE), (_RECEIVER.id_, _CASE)],
        ],
        ids=["other_receiver", "unbound", "two_links"],
    )
    def test_a_wrong_link_fails(self, monkeypatch, caplog, links):
        self._stub(monkeypatch, case_id=_CASE, links=links)
        with pytest.raises(AssertionError, match="should name"):
            with (
                caplog.at_level(logging.WARNING),
                expect_trusted_introductions(caplog),
            ):
                _check()

    def test_a_failed_check_fails_beside_a_passing_one(
        self, monkeypatch, caplog
    ):
        results = iter([_CASE, None])

        def _wait(client, reporter_id, receiver_id, report_id, **kwargs):
            case_id = next(results)
            if case_id is None:
                raise AssertionError("timed out")
            return case_id

        monkeypatch.setattr(workflow, "wait_for_reporter_introduction", _wait)
        monkeypatch.setattr(
            _helpers, "_reporter_links", lambda *_a: [(_RECEIVER.id_, _CASE)]
        )
        with pytest.raises(AssertionError, match="never bound"):
            with (
                caplog.at_level(logging.WARNING),
                expect_trusted_introductions(caplog),
            ):
                _check()
                # The demo_check records the second and goes on.
                assert _check() is None

    def test_a_level_that_hides_warnings_fails_at_once(self, caplog):
        with pytest.raises(AssertionError, match="WARNING or lower"):
            with (
                caplog.at_level(logging.ERROR),
                expect_trusted_introductions(caplog),
            ):
                pass
