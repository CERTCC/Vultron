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
"""``broadcast_case_update``: who the CASE_MANAGER's case announcement reaches."""

from collections.abc import Collection
from unittest.mock import MagicMock

import pytest

from test.support.case_owner import CASE_OWNER_ID
from vultron.core.behaviors.case import update_support
from vultron.core.behaviors.case.update_support import broadcast_case_update
from vultron.core.models.case import VulnerabilityCase
from vultron.core.ports.case_persistence import CasePersistence

CASE_ID = "https://example.org/cases/broadcast-1"
MANAGER_ID = "https://example.org/actors/manager"
PARTICIPANT_ID = "https://example.org/actors/vendor"


def _stub_recipients(
    monkeypatch: pytest.MonkeyPatch, recipients: list[str]
) -> list[Collection[str]]:
    """Replace the shared selection; return the ``excluding`` values it saw."""
    seen: list[Collection[str]] = []

    def _recipients(
        case: VulnerabilityCase,
        dl: CasePersistence,
        *,
        excluding: Collection[str] = (),
    ) -> list[str]:
        seen.append(excluding)
        return recipients

    monkeypatch.setattr(update_support, "case_content_recipients", _recipients)
    return seen


@pytest.mark.spec("CM-06-001")
def test_announces_to_the_selected_recipients_and_queues_it(monkeypatch):
    _stub_recipients(monkeypatch, [PARTICIPANT_ID])
    dl = MagicMock()
    port = MagicMock()
    port.announce_vulnerability_case.return_value = "urn:uuid:announce-1"

    broadcast_case_update(
        dl,
        CASE_ID,
        VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID),
        MANAGER_ID,
        port,
    )

    port.announce_vulnerability_case.assert_called_once_with(
        case_id=CASE_ID,
        actor=MANAGER_ID,
        context_id=CASE_ID,
        to=[PARTICIPANT_ID],
    )
    dl.outbox_append.assert_called_once_with("urn:uuid:announce-1")


@pytest.mark.spec("CM-10-004")
def test_no_active_participant_means_no_announce(monkeypatch):
    _stub_recipients(monkeypatch, [])
    dl = MagicMock()
    port = MagicMock()

    broadcast_case_update(
        dl,
        CASE_ID,
        VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID),
        MANAGER_ID,
        port,
    )

    port.announce_vulnerability_case.assert_not_called()
    dl.outbox_append.assert_not_called()


def test_omitted_exclusions_exclude_nobody(monkeypatch):
    """CS-21: an omitted ``excluded_actor_ids`` is the empty set, not ``None``."""
    seen = _stub_recipients(monkeypatch, [])

    broadcast_case_update(
        MagicMock(),
        CASE_ID,
        VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID),
        MANAGER_ID,
        MagicMock(),
    )

    assert seen == [set()]


def test_given_exclusions_reach_the_selection(monkeypatch):
    seen = _stub_recipients(monkeypatch, [])

    broadcast_case_update(
        MagicMock(),
        CASE_ID,
        VulnerabilityCase(attributed_to=CASE_OWNER_ID, id_=CASE_ID),
        MANAGER_ID,
        MagicMock(),
        excluded_actor_ids={PARTICIPANT_ID},
    )

    assert seen == [{PARTICIPANT_ID}]
