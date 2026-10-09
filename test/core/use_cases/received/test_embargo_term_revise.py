#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for embargo add/remove (term/revise) use cases."""

from typing import cast

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from test.support.embargo_register import activate, propose
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    ActivateEmbargoOnCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    activate_embargo_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# RSH-08-003 (#3814): the embargo activation/teardown writes run only at the
# CASE_MANAGER, so these tests receive the Add/Remove(EmbargoEvent) in the
# CASE_MANAGER's own store (its actor is the role holder and the entitled
# sender); a replica would write nothing and take the change from the ledger.
_CASE_MANAGER = "https://example.org/users/case-manager"
_COORD = "https://example.org/users/coord"
_OWNER = "https://example.org/users/vendor"


class TestEmbargoTermRevise:
    """Tests for embargo add/remove and unusual-state transition use cases."""

    def _owner_activation_case(self, *, proposed: bool):
        """A CASE_MANAGER store (``coord``) for a case the vendor owns."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_COORD)
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em1",
            name="EM Test Case",
            attributed_to=_OWNER,
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        if proposed:
            propose(case, embargo.id_)
        seed_case_manager_participant(dl, case, _COORD)
        seed_case_owner_participant(dl, case, _OWNER)
        dl.create(case)
        dl.create(embargo)
        return dl, case, embargo

    def test_owner_accept_of_embargo_activates_it_at_the_case_manager(
        self, make_payload
    ):
        """The owner's Accept(EmbargoEvent) activates the proposal (ADR-0122)."""
        dl, case, embargo = self._owner_activation_case(proposed=True)

        activity = activate_embargo_activity(
            embargo,
            target=as_VulnerabilityCase(id_=case.id_),
            actor=_OWNER,
            to=[_COORD],
        )
        event = make_payload(activity, receiving_actor_id=_COORD)

        result = ActivateEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        stored = cast(VulnerabilityCase, dl.read(case.id_))
        assert stored.active_embargo_id == embargo.id_
        assert stored.proposed_embargo_ids == []
        assert stored.current_status.em.state == EM.ACTIVE

    def test_owner_accept_of_an_embargo_never_proposed_is_refused(
        self, make_payload
    ):
        """The received path adjudicates: no open proposal, nothing to activate.

        The guard refuses ahead of the commit, so the register is unchanged
        and no ledger entry is written (CLP-10-009).
        """
        dl, case, embargo = self._owner_activation_case(proposed=False)

        activity = activate_embargo_activity(
            embargo,
            target=as_VulnerabilityCase(id_=case.id_),
            actor=_OWNER,
            to=[_COORD],
        )
        event = make_payload(activity, receiving_actor_id=_COORD)

        result = ActivateEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()
        assert result.disposition is HandlerDisposition.REFUSED
        assert "not an open proposal" in (result.reason or "")

        stored = cast(VulnerabilityCase, dl.read(case.id_))
        assert stored.embargo_register == []
        assert stored.em_state == EM.NONE
        assert dl.list_objects("CaseLedgerEntry") == []

    def test_remove_naming_a_proposed_embargo_changes_nothing(
        self, make_payload
    ):
        """A Remove naming a merely-proposed embargo changes no register entry.

        Remove ends the embargo in force; an open proposal leaves the register
        only by being activated, rejected or cancelled (ADR-0122).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_MANAGER,
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem1",
            name="Remove Embargo Proposed",
            attributed_to="https://example.org/users/coord",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem1/embargo_events/e1",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        propose(case, embargo.id_)
        seed_case_manager_participant(dl, case, _CASE_MANAGER)
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(activity, receiving_actor_id=_CASE_MANAGER)

        result = RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.proposed_embargo_ids == [embargo.id_]
        assert updated.active_embargo_id is None
        assert updated.em_state == EM.PROPOSED

    def test_remove_active_embargo_transitions_em_to_exited(
        self, make_payload
    ):
        """remove_embargo_event transitions EM from ACTIVE to EXITED via BT."""
        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_MANAGER,
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem2",
            name="Remove Embargo ACTIVE→EXITED",
            attributed_to="https://example.org/users/coord",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem2/embargo_events/e2",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        activate(case, embargo.id_)
        seed_case_manager_participant(dl, case, _CASE_MANAGER)
        dl.create(case)
        dl.create(embargo)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(activity, receiving_actor_id=_CASE_MANAGER)

        result = RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em.state == EM.EXITED

    def test_remove_active_embargo_during_revise_cancels_open_revision(
        self, caplog, make_payload
    ):
        """Removing the active embargo while a revision is open ends both.

        At EM REVISE the Remove terminates the active entry and cancels the
        open proposal in the same step, so EM derives EXITED (ADR-0122).
        """
        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_CASE_MANAGER,
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_rem3",
            name="Remove Embargo unusual state override",
            attributed_to="https://example.org/users/coord",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem3/embargo_events/e3",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        activate(case, embargo.id_)
        revision_id = "https://example.org/cases/case_rem3/embargo_events/e4"
        propose(case, revision_id)
        assert case.em_state == EM.REVISE
        seed_case_manager_participant(dl, case, _CASE_MANAGER)
        dl.create(case)
        dl.create(embargo)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(activity, receiving_actor_id=_CASE_MANAGER)

        result = RemoveEmbargoEventFromCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            trigger_activity=TriggerActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em.state == EM.EXITED
        assert updated.proposed_embargo_ids == []
