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

from vultron.core.models.case import VulnerabilityCase
from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AddEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    remove_embargo_from_case_activity,
)


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
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em1",
            name="EM Test Case",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
        )
        # Start from PROPOSED — the standard pre-condition for activation.
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)
        dl.create(embargo)

        activity = add_embargo_to_case_activity(
            embargo,
            target=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        assert case.active_embargo is not None
        assert case.current_status.em.state == EM.ACTIVE

    def test_add_embargo_event_to_case_warns_on_non_standard_transition(
        self, monkeypatch, make_payload, caplog
    ):
        """add_embargo_event_to_case ledgers WARNING when EM state is not on the standard machine path (state-sync override)."""
        import logging
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em1_warn",
            name="EM Warn Test Case",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_em1_warn/embargo_events/e1",
            content="Embargo test",
        )
        # Default em_state is NONE — not a valid predecessor for ACTIVE.
        dl.create(case)
        dl.create(embargo)

        activity = add_embargo_to_case_activity(
            embargo,
            target=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        with caplog.at_level(logging.WARNING):
            AddEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        assert any("state-sync override" in r.message for r in caplog.records)
        case = dl.read(case.id_)
        assert case is not None
        case = cast(VulnerabilityCase, case)
        # State is still updated (synchronization override proceeds).
        assert case.current_status.em.state == EM.ACTIVE

    def test_remove_embargo_from_proposed_clears_proposed_list(
        self, make_payload
    ):
        """remove_embargo_event removes embargo from proposed_embargoes."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_rem1",
            name="Remove Embargo Proposed",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem1/embargo_events/e1",
            context=case.id_,
        )
        case.proposed_embargoes.append(embargo.id_)
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
        )
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(as_VulnerabilityCase, updated)
        assert embargo.id_ not in [
            e if isinstance(e, str) else getattr(e, "id_", None)
            for e in updated.proposed_embargoes
        ]

    def test_remove_active_embargo_transitions_em_to_exited(
        self, make_payload
    ):
        """remove_embargo_event transitions EM from ACTIVE to EXITED via BT."""
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_rem2",
            name="Remove Embargo ACTIVE→EXITED",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem2/embargo_events/e2",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
        )
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em.state == EM.EXITED

    def test_remove_active_embargo_unusual_state_uses_override(
        self, caplog, make_payload
    ):
        """remove_embargo_event uses state-sync override when EM is PROPOSED but embargo is active."""
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_rem3",
            name="Remove Embargo unusual state override",
        )
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/case_rem3/embargo_events/e3",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.PROPOSED
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor="https://example.org/users/coord",
        )
        event = make_payload(
            activity, receiving_actor_id="https://example.org/users/coord"
        )

        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = dl.read(case.id_)
        assert updated is not None
        updated = cast(VulnerabilityCase, updated)
        assert updated.active_embargo is None
        assert updated.current_status.em.state == EM.EXITED
