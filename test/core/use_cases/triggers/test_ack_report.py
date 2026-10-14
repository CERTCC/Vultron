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
"""``execute()``-path tests for ``SvcAckReportUseCase`` (ack-report).

RK goes from an actor the ``Offer(VulnerabilityReport)`` was addressed to, to
the reporter, whether or not a case exists for the report; it is never sent to
the CASE_MANAGER (RMB-08-003).
"""

from collections.abc import Iterator

import pytest

from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.use_cases.triggers.report import SvcAckReportUseCase
from vultron.core.use_cases.triggers.requests import AckReportTriggerRequest
from vultron.errors import (
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Read
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

FINDER_ID = "https://example.org/actors/finder-ack-trigger"
CASE_ACTOR_ID = "https://example.org/actors/case-actor-ack-trigger"


class _Fixture:
    """The Vendor's store after it received the Finder's report Offer."""

    def __init__(self) -> None:
        self.vendor = as_Service(name="Vendor Co")
        reset_datalayer(self.vendor.id_)
        self.dl = SqliteDataLayer(
            "sqlite:///:memory:", actor_id=self.vendor.id_
        )
        self.dl.create(self.vendor)
        self.report = as_VulnerabilityReport(
            name="CVE-TEST", content="content", attributed_to=FINDER_ID
        )
        self.dl.create(self.report)
        self.offer = rm_submit_report_activity(
            self.report, self.vendor.id_, actor=FINDER_ID
        )
        self.dl.create(self.offer)
        self.dl.create(
            VultronOfferRecord(
                offer_id=self.offer.id_,
                report_id=self.report.id_,
                offer_actor_id=FINDER_ID,
                offer_to=[self.vendor.id_],
            )
        )

    def run(
        self,
        actor_id: str | None = None,
        offer_id: str | None = None,
        note: str | None = None,
    ):
        return SvcAckReportUseCase(
            self.dl,
            AckReportTriggerRequest(
                actor_id=actor_id or self.vendor.id_,
                offer_id=offer_id or self.offer.id_,
                note=note,
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
        ).execute()

    def add_case(self) -> None:
        case = as_VulnerabilityCase(name="Case", attributed_to=CASE_ACTOR_ID)
        case.vulnerability_reports.append(self.report.id_)
        self.dl.save(case)

    def close(self) -> None:
        self.dl.clear_all()
        self.dl.close()
        reset_datalayer(self.vendor.id_)


@pytest.fixture
def env() -> Iterator[_Fixture]:
    fixture = _Fixture()
    yield fixture
    fixture.close()


@pytest.mark.spec("RMB-08-003")
@pytest.mark.spec("TRIG-02-001")
@pytest.mark.spec("VP-03-009")
def test_ack_is_sent_to_the_reporter_alone(env: _Fixture):
    before = set(env.dl.outbox_list())

    result = env.run()

    activity = activity_of(result)
    assert activity.get("type") == "Read"
    queued = set(env.dl.outbox_list()) - before
    assert len(queued) == 1
    read = env.dl.read(queued.pop())
    assert isinstance(read, as_Read)
    assert read.actor == env.vendor.id_
    assert read.to == [FINDER_ID]


@pytest.mark.spec("RMB-08-003")
@pytest.mark.spec("PCR-08-001")
def test_ack_still_goes_to_the_reporter_alone_once_a_case_exists(
    env: _Fixture,
):
    """RK answers the reporter's Offer outside the case (PCR-08-001 exception)."""
    env.add_case()
    before = set(env.dl.outbox_list())

    env.run()

    queued = set(env.dl.outbox_list()) - before
    assert len(queued) == 1
    read = env.dl.read(queued.pop())
    assert isinstance(read, as_Read)
    assert read.to == [FINDER_ID]
    assert CASE_ACTOR_ID not in (read.cc or [])


@pytest.mark.spec("TRIG-03-003")
def test_note_is_carried_as_the_ack_content(env: _Fixture):
    before = set(env.dl.outbox_list())

    env.run(note="We have received your report.")

    queued = set(env.dl.outbox_list()) - before
    read = env.dl.read(queued.pop())
    assert isinstance(read, as_Read)
    assert read.content == "We have received your report."


def test_ack_without_a_note_has_no_content(env: _Fixture):
    before = set(env.dl.outbox_list())

    env.run()

    read = env.dl.read((set(env.dl.outbox_list()) - before).pop())
    assert isinstance(read, as_Read)
    assert read.content is None


def test_offer_recipient_spelled_with_a_trailing_slash_may_ack(
    env: _Fixture,
):
    """Recipient membership tolerates a trailing slash (HP-09-001)."""
    record = env.dl.read(VultronOfferRecord.build_id(env.offer.id_))
    assert isinstance(record, VultronOfferRecord)
    env.dl.save(record.model_copy(update={"offer_to": [env.vendor.id_ + "/"]}))
    before = set(env.dl.outbox_list())

    env.run()

    assert len(set(env.dl.outbox_list()) - before) == 1


@pytest.mark.spec("RMB-08-003")
def test_actor_the_offer_was_not_sent_to_is_refused(env: _Fixture):
    other = as_Service(name="Other Co")
    env.dl.create(other)
    before = set(env.dl.outbox_list())

    with pytest.raises(VultronValidationError, match="ack-report"):
        env.run(actor_id=other.id_)

    assert set(env.dl.outbox_list()) == before


def test_unknown_offer_raises_not_found(env: _Fixture):
    with pytest.raises(VultronNotFoundError):
        env.run(offer_id="urn:uuid:no-such-offer")


def test_unknown_actor_raises_not_found(env: _Fixture):
    with pytest.raises(VultronNotFoundError):
        env.run(actor_id="urn:uuid:no-such-actor")
