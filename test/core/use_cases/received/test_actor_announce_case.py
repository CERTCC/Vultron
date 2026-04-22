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
"""Tests for AnnounceVulnerabilityCaseReceivedUseCase (DR-10 / MV-10-003,004)."""

from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.use_cases.received.actor import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.wire.as2.vocab.activities.case import (
    AnnounceVulnerabilityCaseActivity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_OWNER_ID = "https://example.org/actors/owner"
_CASE_ID = "https://example.org/cases/case-ann-001"
_CASE_ID2 = "https://example.org/cases/case-ann-002"


@pytest.fixture()
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture()
def case():
    return VulnerabilityCase(id_=_CASE_ID, name="DR-10 Announce Case")


@pytest.fixture()
def announce_activity(case):
    return AnnounceVulnerabilityCaseActivity(
        actor=_OWNER_ID,
        object_=case,
    )


@pytest.fixture()
def event(make_payload, announce_activity):
    return make_payload(announce_activity)


class TestAnnounceVulnerabilityCaseReceivedUseCase:
    """AnnounceVulnerabilityCaseReceivedUseCase seeds the invitee's DataLayer."""

    def test_creates_case_when_absent(self, dl, event, case):
        """MV-10-003: Announce seeding creates the case in the invitee's DL."""
        assert dl.read(_CASE_ID) is None

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is not None

    def test_case_fields_preserved(self, dl, event, case):
        """The seeded case retains the name from the Announce payload."""
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = cast(Any, dl.read(_CASE_ID))
        assert result.name == "DR-10 Announce Case"

    def test_idempotent_when_case_already_exists(self, dl, event, case):
        """MV-10-004: A second Announce for an existing case is a no-op."""
        dl.create(case)

        # First call — case exists; should not fail or overwrite
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        # Confirm the case is still there and unchanged
        result = dl.read(_CASE_ID)
        assert result is not None

    def test_missing_activity_skips_gracefully(self, dl, event):
        """No-op (with a warning log) when event.activity is None."""
        event = event.model_copy(update={"activity": None})

        # Must not raise
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None

    def test_non_case_object_skips_gracefully(self, dl, make_payload):
        """No-op when the activity object_ is not a VulnerabilityCase."""
        from vultron.wire.as2.vocab.activities.case import (
            AnnounceVulnerabilityCaseActivity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            VulnerabilityReport,
        )

        # Build an Announce that wraps a non-case object; we can't use the typed
        # AnnounceVulnerabilityCaseActivity here because it requires VulnerabilityCase,
        # so we inject via model_copy to simulate a malformed incoming payload.
        good_case = VulnerabilityCase(id_=_CASE_ID2, name="Placeholder")
        announce = AnnounceVulnerabilityCaseActivity(
            actor=_OWNER_ID, object_=good_case
        )
        event = make_payload(announce)

        # Replace the object_ on the raw activity with a non-case
        report = VulnerabilityReport(name="Not a case")
        patched_activity = announce.model_copy(update={"object_": report})
        event = event.model_copy(update={"activity": patched_activity})

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID2) is None
