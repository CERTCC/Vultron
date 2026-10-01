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
"""Accepting the active embargo backfills withheld ledger entries (CM-10-006).

Strict ``xfail`` until the gate lands: today nothing is withheld, so the
accept fans out only its own new entry and never re-sends an earlier one.
"""

from typing import cast

import pytest

from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
)

from .conftest import make_embargo_case_with_actor

MANAGER_ID = "https://example.org/actors/coordinator"
SIGNATORY_IDS = (
    "https://example.org/actors/vendor",
    "https://example.org/actors/deployer",
)
NON_SIGNATORY_ID = "https://example.org/actors/finder"
CASE_ID = "https://example.org/cases/fanout-backfill"


class _GateScenario:
    """A case under an active embargo that only the finder has not accepted."""

    def __init__(self, make_payload) -> None:
        self._make_payload = make_payload
        self.dl, _, case, embargo = make_embargo_case_with_actor(
            CASE_ID,
            MANAGER_ID,
            extra_participants=[*SIGNATORY_IDS, NON_SIGNATORY_ID],
            case_manager_actor_id=MANAGER_ID,
        )
        stored = cast(VulnerabilityCase, self.dl.read(case.id_))
        stored.current_status.em.state = EM.ACTIVE
        stored.set_embargo(embargo.id_)
        self.dl.save(stored)

        self.invite = em_propose_embargo_activity(
            embargo,
            context=CASE_ID,
            actor=MANAGER_ID,
            id_=f"{CASE_ID}/embargo_proposals/1",
        )
        self.dl.create(self.invite)

    def receive_accept(self, actor_id: str) -> None:
        accept = em_accept_embargo_activity(
            self.invite, context=CASE_ID, actor=actor_id
        )
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            self.dl,
            self._make_payload(accept, receiving_actor_id=MANAGER_ID),
            sync_port=SyncActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

    def ledger(self) -> list[CaseLedgerEntry]:
        entries = [
            e
            for e in self.dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry) and e.case_id == CASE_ID
        ]
        return sorted(entries, key=lambda e: e.log_index)

    def withhold_signatory_commits(self) -> list[str]:
        """Commit while the finder is outside the gate; return those entry ids.

        Under CM-10-005 none of these is ever sent to the finder.  Draining
        the outbox models that.
        """
        for signatory_id in SIGNATORY_IDS:
            self.receive_accept(signatory_id)
        withheld = [e.id_ for e in self.ledger()]
        while self.dl.outbox_pop() is not None:
            pass
        return withheld

    def announced_to(self, actor_id: str) -> list[str]:
        """Entry ids announced to *actor_id*, in outbox order."""
        announced = []
        for activity in (self.dl.read(i) for i in self.dl.outbox_list()):
            if getattr(activity, "type_", None) != "Announce":
                continue
            if actor_id not in (getattr(activity, "to", None) or []):
                continue
            if (entry := getattr(activity, "object_", None)) is not None:
                announced.append(entry.id_)
        return announced


def test_signatory_accepts_commit_entries_before_the_finder_is_admitted(
    make_payload,
) -> None:
    """Precondition for the CM-10-006 marker: more than one entry is withheld.

    Kept outside the strict ``xfail`` so that a change in what an accept
    commits fails loudly here instead of hiding inside the expected failure.
    """
    scenario = _GateScenario(make_payload)

    assert len(scenario.withhold_signatory_commits()) >= 2


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-10-006: no backfill of withheld ledger entries when the embargo"
        " content gate admits a participant. Tracked in #4042; source #3917."
    ),
)
@pytest.mark.spec("CM-10-006")
def test_accepting_the_active_embargo_backfills_withheld_entries(
    make_payload,
) -> None:
    scenario = _GateScenario(make_payload)
    withheld = scenario.withhold_signatory_commits()

    scenario.receive_accept(NON_SIGNATORY_ID)

    # Every withheld entry, in log order, before (or as) the admitting entry.
    assert scenario.announced_to(NON_SIGNATORY_ID)[: len(withheld)] == withheld
    # The backfill goes to the admitted participant only, not to everyone.
    for signatory_id in SIGNATORY_IDS:
        assert not set(withheld) & set(scenario.announced_to(signatory_id))
