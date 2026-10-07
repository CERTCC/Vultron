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
)
from test.support.embargo_register import activate, propose
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    remove_embargo_from_case_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# The CASE_MANAGER is not the receiving store's owner, so the receiver is a
# participant replica and the sender is the CASE_MANAGER (ADR-0115).
_CASE_MANAGER = "https://example.org/users/case-manager"


class TestEmbargoTermRevise:
    """Tests for embargo add/remove and unusual-state transition use cases."""

    def test_add_embargo_event_to_case_activates_embargo(
        self, monkeypatch, make_payload
    ):
        """add_embargo_event_to_case sets the active embargo on the case (PROPOSED → ACTIVE)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/coord",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em1",
            name="EM Test Case",
            attributed_to="https://example.org/users/coord",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        # Start from PROPOSED — the standard pre-condition for activation.
        propose(case, embargo.id_)
        seed_case_manager_participant(dl, case, _CASE_MANAGER)
        dl.create(case)
        dl.create(embargo)

        activity = add_embargo_to_case_activity(
            embargo,
            target=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(activity)

        result = AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo is not None
        assert case.current_status.em.state == EM.ACTIVE

    def test_add_embargo_event_never_proposed_here_is_proposed_then_activated(
        self, monkeypatch, make_payload
    ):
        """An OBSERVED activation of an embargo this replica never saw proposed
        records the proposal first, then activates it (ADR-0122, EP-09-007).

        No EM state is forced: the register takes the two steps its rules
        allow, and EM derives ACTIVE from them.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/users/coord",
        )
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_em1_warn",
            name="EM Warn Test Case",
            attributed_to="https://example.org/users/coord",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_em1_warn/embargo_events/e1",
            content="Embargo test",
            context=case.id_,
            end_time=days_from_now_utc(45),
        )
        # The register is empty (EM NONE): the replica never saw a proposal.
        seed_case_manager_participant(dl, case, _CASE_MANAGER)
        dl.create(case)
        dl.create(embargo)

        activity = add_embargo_to_case_activity(
            embargo,
            target=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(activity)

        result = AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo_id == embargo.id_
        assert case.proposed_embargo_ids == []
        assert case.em_state == EM.ACTIVE
        assert case.current_status.em.state == EM.ACTIVE

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
            actor_id="https://example.org/users/coord",
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
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        result = RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()
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
            actor_id="https://example.org/users/coord",
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

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        result = RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()
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
            actor_id="https://example.org/users/coord",
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

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=as_VulnerabilityCase(id_=case.id_),
            actor=_CASE_MANAGER,
            to=["https://example.org/users/coord"],
        )
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        result = RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em.state == EM.EXITED
        assert updated.proposed_embargo_ids == []
