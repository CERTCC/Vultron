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

"""Unit tests for TriggerActivityAdapter case-proposal methods (CP-01-010)."""

import json
from datetime import timedelta

import pytest

from vultron.core.models.actor import VultronOrganization
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"


def _make_report(dl) -> as_VulnerabilityReport:
    report = as_VulnerabilityReport(name="CVE-2025-001", content="PoC details")
    dl.create(report)
    return report


class TestCreateCaseProposal:
    @pytest.mark.spec("CP-01-010")
    def test_the_create_carries_the_senders_stored_profile_inline(
        self, adapter, dl
    ):
        """The sender's own profile, policy included, is the Create's actor."""
        report = _make_report(dl)
        dl.save(
            VultronOrganization(
                id_=_VENDOR,
                embargo_policy=EmbargoPolicy(
                    actor_id=_VENDOR,
                    inbox=f"{_VENDOR}/inbox",
                    preferred_duration=timedelta(days=30),
                ),
            )
        )

        _, blob = adapter.create_case_proposal(
            actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
        )

        actor = json.loads(blob)["actor"]
        assert isinstance(actor, dict)
        assert actor["id"] == _VENDOR
        assert actor["embargoPolicy"]["actorId"] == _VENDOR
        assert actor["embargoPolicy"]["preferredDuration"] == "P30D"
        assert len(list(dl.list_objects("CaseProposal"))) == 1

    @pytest.mark.spec("CP-01-010")
    def test_a_sender_with_no_stored_profile_is_refused_and_persists_nothing(
        self, adapter, dl
    ):
        """Without a profile the CASE_MANAGER would refuse the proposal, so it
        is not built — and no orphan proposal is left in the store."""
        report = _make_report(dl)

        with pytest.raises(ValueError, match="CP-01-010"):
            adapter.create_case_proposal(
                actor=_VENDOR, report_id=report.id_, case_actor_id=_CASE_ACTOR
            )

        assert list(dl.list_objects("CaseProposal")) == []
