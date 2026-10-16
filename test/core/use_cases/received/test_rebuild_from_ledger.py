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

"""The rebuild-from-ledger check itself (#4294 AC-5, CLP-07-013, CM-23-016).

Every per-actor-store scenario in this package is rebuilt from its
CASE_MANAGER's ledger when it ends (``conftest``), and every exchange demo is
rebuilt before its node is cleared (``test/demo/_helpers.py``).  These tests
show the check is not vacuous: it reaches the CASE_MANAGER's state through a
whole embargo cycle, it catches a change no entry records, it fails on a
missing entry, and its one embargo exclusion (#4748) hides only the
termination's cause.
"""

import json
from typing import Any, cast

import pytest

from test.support import ledger_rebuild
from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import (
    assert_rebuilds_from_ledger,
    case_file_differences,
    creation_records,
    rebuild_from_ledger,
)
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_termination import TerminationCauseKind
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.states.embargo_register import (
    EmbargoRegisterStatus,
    TerminationReason,
)
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.wire.as2.factories import em_propose_embargo_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)


def _applied(verdict: Any) -> None:
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _propose(net: LedgerNetwork, suffix: str, days: int) -> str:
    """PROPOSER sends a revision to the CASE_MANAGER (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{suffix}",
        content=f"Terms {suffix}",
        context=net.case_id,
        end_time=days_from_now_utc(days),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/{suffix}",
    )
    _applied(net.receive(MANAGER, json.loads(dump_outbound_body(proposal))))
    return revision.id_


def _answer(net: LedgerNetwork, actor: str) -> None:
    """*actor* accepts the Invite the CASE_MANAGER relayed to it."""
    for _type, verdict in net.deliver(MANAGER, to=actor, type_="Invite"):
        _applied(verdict)
    (invite,) = net.queued(MANAGER, to=actor, type_="Invite")
    _, sealed = TriggerActivityAdapter(net.stores[actor]).accept_embargo(
        proposal_id=invite.id_, case_id=net.case_id, actor=actor, to=[MANAGER]
    )
    _applied(net.receive(MANAGER, json.loads(sealed)))


def _owner_activates(net: LedgerNetwork, embargo_id: str) -> None:
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    _, sealed = TriggerActivityAdapter(net.stores[OWNER]).activate_embargo(
        embargo_id=embargo_id, case_id=net.case_id, actor=OWNER, to=[MANAGER]
    )
    _applied(net.receive(MANAGER, json.loads(sealed)))


def _negotiated(case_suffix: str) -> tuple[LedgerNetwork, str]:
    """A revision proposed, answered by the bystander, activated by the owner."""
    net = LedgerNetwork(f"https://example.org/cases/rebuild-{case_suffix}")
    revision_id = _propose(net, "shorter", 20)
    _answer(net, BYSTANDER)
    _owner_activates(net, revision_id)
    return net, revision_id


def _seed(net: LedgerNetwork) -> list[Any]:
    seed = net.rebuild_seed
    assert seed is not None, "the scenario committed no entry"
    return seed


@pytest.mark.spec("CLP-07-013")
@pytest.mark.spec("CM-23-016")
def test_a_negotiated_revision_rebuilds_from_the_ledger_alone():
    """Proposal, relayed Invites, rows, an answer, the activation and its
    carry-overs all reach an empty store from the ledger."""
    net, revision_id = _negotiated("cycle")
    manager = net.stores[MANAGER]

    replica = rebuild_from_ledger(
        manager, net.case_id, as_actor=BYSTANDER, seed=_seed(net)
    )

    rebuilt = cast(VulnerabilityCase, replica.read(net.case_id))
    assert rebuilt.em_state == EM.ACTIVE
    assert rebuilt.active_embargo_id == revision_id
    assert case_file_differences(manager, replica, net.case_id) == []


@pytest.mark.spec("CLP-07-013")
def test_a_change_no_entry_records_is_caught():
    """The check is not vacuous: a row written outside the ledger differs."""
    net, revision_id = _negotiated("unrecorded")
    manager = net.stores[MANAGER]
    record = cast(
        CaseParticipant,
        manager.read(net.case(MANAGER).actor_participant_index[BYSTANDER]),
    )
    record.embargo_consents = [
        row.model_copy(update={"state": EmbargoConsentState.DECLINED})
        if row.embargo_id == revision_id
        else row
        for row in record.embargo_consents
    ]
    manager.save(record)
    net.bypass_ledger()

    with pytest.raises(AssertionError, match="embargo_consents"):
        assert_rebuilds_from_ledger(
            manager, net.case_id, as_actor=BYSTANDER, seed=_seed(net)
        )


@pytest.mark.spec("CM-23-016")
def test_a_missing_entry_fails_the_rebuild(monkeypatch):
    """An entry the replica cannot apply is named, never passed over."""
    net, _ = _negotiated("gap")
    entries = ledger_entries(net.stores[MANAGER], net.case_id)
    dropped = entries[1]

    with monkeypatch.context() as patched:
        patched.setattr(
            ledger_rebuild,
            "ledger_entries",
            lambda *_a: [e for e in entries if e.id_ != dropped.id_],
        )
        with pytest.raises(AssertionError, match="was deferred"):
            rebuild_from_ledger(
                net.stores[MANAGER],
                net.case_id,
                as_actor=BYSTANDER,
                seed=_seed(net),
            )


def _terminated(cause: bool, reason: TerminationReason) -> VulnerabilityCase:
    """A case whose one register entry is TERMINATED as given."""
    termination: dict[str, Any] = {"reason": reason}
    if cause:
        termination["cause"] = {
            "kind": TerminationCauseKind.THREAT_SIGNAL,
            "signals": ["P"],
        }
    return VulnerabilityCase.model_validate(
        {
            "id_": "https://example.org/cases/rebuild-register",
            "name": "Register",
            "embargo_register": [
                {
                    "embargo": "https://example.org/embargo_events/e1",
                    "status": EmbargoRegisterStatus.TERMINATED,
                    "termination": termination,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    "replica, differs",
    [
        (_terminated(False, TerminationReason.EARLY), False),
        (_terminated(False, TerminationReason.END_TIME_REACHED), True),
    ],
    ids=["cause-only", "reason"],
)
def test_only_the_termination_cause_is_left_out(replica, differs):
    """#4748: a replica cannot learn the cause; the reason is still compared."""
    manager = _terminated(True, TerminationReason.EARLY)

    assert (
        ledger_rebuild._register(replica) != ledger_rebuild._register(manager)
    ) is differs


def test_creation_records_stop_at_the_first_act():
    """Only the leading creation entries seed the store; acts are replayed."""
    case = VulnerabilityCase(
        id_="https://example.org/cases/rebuild-seed", name="Seed"
    )
    entries = [
        CaseLedgerEntry.model_construct(
            event_type="create_case", payload_snapshot={"object": case}
        ),
        CaseLedgerEntry.model_construct(
            event_type="invite_to_embargo_on_case", payload_snapshot={}
        ),
        CaseLedgerEntry.model_construct(
            event_type="create_case",
            payload_snapshot={"object": case.model_copy(update={"name": "X"})},
        ),
    ]

    (record,) = creation_records(entries)

    assert record == case
