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
"""The records ``test/support/received.py`` seeds for the ingress are signed.

A resend is matched against the archived, intake or held body (IE-10-001),
and a delivery carries its author's proof (SIG-01-001), so each seed holds a
body that verifies against its author's key, proof included (SIG-04-001).
The test reads the public key from the author's seeded key, as the author's
profile publishes it; a verifier never does (SIG-05-002).
"""

import json
from typing import Any

import pytest

from test.support.received import (
    archive_received,
    hold_deferred,
    intake_received,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.activity import VultronActivity
from vultron.core.services.received_activity import sealed_body_of
from vultron.wire.as2 import signing
from vultron.wire.as2.factories import rm_create_report_activity
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

SENDER = "https://example.org/actors/finder"
RECEIVER = "https://example.org/actors/vendor"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(db_url="sqlite:///:memory:", actor_id=RECEIVER)


def _wire_activity() -> Any:
    report = as_VulnerabilityReport(
        id_="https://example.org/reports/signed-seed",
        content="signed seed",
        attributed_to=SENDER,
    )
    return rm_create_report_activity(report, actor=SENDER, to=[RECEIVER])


def _core_activity() -> VultronActivity:
    return VultronActivity(
        id_="https://example.org/activities/core-seed",
        type_="Create",
        actor=SENDER,
        object_="https://example.org/reports/core-seed",
    )


def _assert_signed_by_sender(text: str) -> None:
    body = json.loads(text)
    signing.verify(
        body, signing.seeded_signing_key(SENDER).public_key_multibase
    )
    assert body["proof"]["verificationMethod"] == signing.key_id_for(SENDER)


@pytest.mark.spec("SIG-01-001")
@pytest.mark.spec("SIG-04-001")
@pytest.mark.parametrize(
    "build", [_wire_activity, _core_activity], ids=["wire", "core"]
)
@pytest.mark.parametrize(
    "seed", [archive_received, intake_received], ids=["archive", "intake"]
)
def test_an_archived_or_intake_record_holds_a_signed_body(
    dl: SqliteDataLayer, build: Any, seed: Any
):
    record = seed(dl, build())

    _assert_signed_by_sender(sealed_body_of(record))


@pytest.mark.spec("SIG-01-001")
def test_a_held_record_holds_a_signed_body(dl: SqliteDataLayer):
    record = hold_deferred(dl, _wire_activity())

    _assert_signed_by_sender(sealed_body_of(record))
