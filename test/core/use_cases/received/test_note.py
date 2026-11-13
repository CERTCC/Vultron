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
"""Tests for note-related use-case classes."""

from typing import cast
from unittest.mock import MagicMock

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
    seed_case_participant,
)
from test.support.act_runner import run_in_act
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import authored_at, make
from test.support.received import delivered_body, received_event
from test.support.trigger_results import recipient_ids
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
    ActivityUnsupportedNode,
)
from vultron.core.behaviors.note.remove_note_received_tree import (
    REMOVE_NOTE_UNSUPPORTED,
    create_remove_note_from_case_received_tree,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.note import (
    AddNoteToCaseReceivedUseCase,
    RemoveNoteFromCaseReceivedUseCase,
)
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_STORE_ACTOR = "https://example.org/actors/cm-store"
_OWNER = "https://example.org/actors/case-owner"
_OTHER_MANAGER = "https://example.org/actors/the-manager"


class TestNoteUseCases:
    """Tests for note management handlers."""

    def _setup_case_with_case_manager(
        self,
        dl: SqliteDataLayer,
        case_id: str,
        case_actor_id: str,
        *,
        create_case_actor: bool = True,
    ) -> as_VulnerabilityCase:
        """Create a as_VulnerabilityCase with a CaseActor holding CASE_MANAGER.

        Pass ``create_case_actor=False`` to seed a *second* case onto a
        CaseActor this helper already created: one CaseActor manages several
        cases through one inbox, routing on ``context`` (PCR-04-003), so the
        ``Service`` is reused rather than re-created. The flag is explicit
        rather than an ``if`` on what is already in the store, so the call
        site says which case is the first (TB-09-004).
        """
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        if create_case_actor:
            dl.create(
                make(
                    VultronService,
                    id_=case_actor_id,
                    name="CaseActor",
                    attributed_to="https://example.org/users/vendor",
                    context=case_id,
                )
            )

        # attributed_to anchors the per-case ledger genesis, without which
        # the CaseActor's receipt commit fails (CLP-08-005).
        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="Note Case",
            attributed_to="https://example.org/users/vendor",
        )
        case_mgr_participant = make(
            as_CaseParticipant,
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_mgr_participant)
        case.case_participants.append(case_mgr_participant.id_)
        case.actor_participant_index[case_actor_id] = case_mgr_participant.id_
        # The tests' sender attaches notes as an active participant
        # (CM-23-018, HP-01-006).
        seed_case_participant(dl, case, "https://example.org/users/finder")
        dl.create(case)
        return case

    def test_add_note_to_case_appends_note(self, monkeypatch, make_payload):
        """CaseActor appends note ID to case.notes on Add(Note)[target=VulnerabilityCase]."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_n1/actor",
        )
        case_actor_id = "https://example.org/cases/case_n1/actor"
        case_id = "https://example.org/cases/case_n1"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)

        note = make(
            as_Note,
            id_="https://example.org/notes/note3",
            content="A note",
            context=case_id,
        )

        activity = add_note_to_case_activity(
            note,
            target=case,
            actor="https://example.org/users/finder",
            to=[dl.actor_id],
            at=authored_at(),
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id, at=dl)

        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        refreshed = dl.read(case_id)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert note.id_ in refreshed.notes
        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("PCR-04-001")
    @pytest.mark.spec("PCR-07-004")
    def test_the_context_decides_which_replica_the_note_lands_on(
        self, make_payload
    ):
        """PCR-07-004: the case ``context`` names is the one the note reaches.

        One actor holds one inbox and several replicas (PCR-04-003), so what
        this pins is that the activity acts on the case its ``context`` names
        and leaves the other alone.  Holding *two* cases is what makes that
        mean anything: against a store holding one case, "the note landed on
        the case" is true however the handler chose it.

        It does not isolate ``context`` from ``target``: a well-formed
        ``Add(Note)`` names the same case in both, so an activity naming one
        case in ``context`` and another in ``target`` is not a shape the
        protocol produces.  That ``context`` and not the inline object is what
        the resolver reads is pinned separately, by
        ``test_non_bootstrap_ignores_inline_object_id`` in
        ``test/core/models/events/test_case_context.py``.

        The bystander is seeded *first*, so the CaseActor ``Service`` the two
        cases share carries the bystander's id in its own single-valued
        ``context``: a handler that read the receiving actor's context instead
        of the activity's would land the note on the wrong case.
        """
        case_actor_id = "https://example.org/cases/case_n1r/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        bystander = self._setup_case_with_case_manager(
            dl, "https://example.org/cases/case_n1r_other", case_actor_id
        )
        addressed = self._setup_case_with_case_manager(
            dl,
            "https://example.org/cases/case_n1r",
            case_actor_id,
            create_case_actor=False,
        )
        note = make(
            as_Note,
            id_="https://example.org/notes/note-routed",
            content="For the addressed case only",
            context=addressed.id_,
        )

        event = make_payload(
            add_note_to_case_activity(
                note,
                target=addressed,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        )
        assert _as_id(event.context) == addressed.id_, (
            "the activity must route on context, so the extracted event must"
            " carry it (PCR-04-002)"
        )

        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert (
            note.id_
            in cast(as_VulnerabilityCase, dl.read(addressed.id_)).notes
        )
        assert (
            cast(as_VulnerabilityCase, dl.read(bystander.id_)).notes == []
        ), "the case the context did not name must be untouched"

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.spec("VAM-01-015")
    def test_add_note_to_case_stores_the_inline_note(self, make_payload):
        """An Add(Note) carrying a note the CASE_MANAGER has never seen
        stores that note, then attaches it (#4706): the case never names a
        note its own store cannot read."""
        case_actor_id = "https://example.org/cases/case_n1b/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1b"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note = make(
            as_Note,
            id_="https://example.org/notes/note3b",
            content="Carried inline",
            context=case_id,
        )
        assert dl.read(note.id_) is None

        event = make_payload(
            add_note_to_case_activity(
                note,
                target=case,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        )
        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.APPLIED
        stored = dl.read(note.id_)
        assert stored is not None
        assert getattr(stored, "content", None) == "Carried inline"
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert note.id_ in refreshed.notes

    @pytest.mark.spec("HP-08-006")
    def test_add_note_to_case_refuses_to_overwrite_a_different_note(
        self, make_payload
    ):
        """An Add(Note) whose note id already names a different stored note
        is refused before the commit: the stored note keeps its content, the
        case does not gain the id, and no ledger entry is written (#4706)."""
        case_actor_id = "https://example.org/cases/case_n1c/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1c"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note_id = "https://example.org/notes/note3c"
        dl.create(
            make(as_Note, id_=note_id, content="Original", context=case_id)
        )
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        event = make_payload(
            add_note_to_case_activity(
                make(
                    as_Note, id_=note_id, content="Rewritten", context=case_id
                ),
                target=case,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        )
        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert getattr(dl.read(note_id), "content", None) == "Original"
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert note_id not in refreshed.notes
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before

    def _add_note_through_ingress(
        self,
        dl: SqliteDataLayer,
        case_actor_id: str,
        note: as_Note,
        case: as_VulnerabilityCase,
    ):
        """Send an Add(Note) through inbox parse and rehydrate, then run it."""
        activity = add_note_to_case_activity(
            note,
            target=case,
            actor="https://example.org/users/finder",
            to=[dl.actor_id],
            at=authored_at(),
        )
        ingress = FastAPIIngressAdapter(dl)
        parsed = ingress.parse(delivered_body(activity, at=dl))
        assert parsed is not None
        event = received_event(ingress.rehydrate(parsed), at=dl).model_copy(
            update={"receiving_actor_id": case_actor_id}
        )
        assert isinstance(event, AddNoteToCaseReceivedEvent)
        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )
        # Ingress holds nothing under the Add's own id (DL-06-006).
        assert dl.read(activity.id_) is None
        return result

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.spec("DL-06-006")
    def test_add_note_through_ingress_with_a_taken_id_is_refused(self):
        """The conflicting Add of the test above, sent through the inbox
        ingress, is refused too: the routing rebuild hands the handler the
        stored note, but the id is taken either way (#4831)."""
        case_actor_id = "https://example.org/cases/case_n1d/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1d"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note_id = "https://example.org/notes/note3d"
        dl.create(
            make(as_Note, id_=note_id, content="Original", context=case_id)
        )
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        result = self._add_note_through_ingress(
            dl,
            case_actor_id,
            make(as_Note, id_=note_id, content="Rewritten", context=case_id),
            case,
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert getattr(dl.read(note_id), "content", None) == "Original"
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert note_id not in refreshed.notes
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before

    @pytest.mark.spec("HP-08-006")
    def test_add_note_through_ingress_naming_another_cases_note_is_refused(
        self,
    ):
        """An Add(Note) to case A whose note id names case B's note is
        refused on the inbox path: B's note is not attached to A and no
        entry carries it to A's participants (#4831, AC-1)."""
        case_actor_id = "https://example.org/cases/case_x/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_a = self._setup_case_with_case_manager(
            dl, "https://example.org/cases/case_xa", case_actor_id
        )
        case_b_id = "https://example.org/cases/case_xb"
        note_id = "https://example.org/notes/case-b-note"
        dl.create(
            make(
                as_Note, id_=note_id, content="Case B only", context=case_b_id
            )
        )
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        result = self._add_note_through_ingress(
            dl,
            case_actor_id,
            make(
                as_Note, id_=note_id, content="Case B only", context=case_a.id_
            ),
            case_a,
        )

        assert result.disposition == HandlerDisposition.REFUSED
        refreshed = cast(as_VulnerabilityCase, dl.read(case_a.id_))
        assert note_id not in refreshed.notes
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before
        assert _as_id(getattr(dl.read(note_id), "context", None)) == case_b_id

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.parametrize(
        "note_context",
        ["https://example.org/cases/some-other-case", None],
        ids=["another-case", "no-case"],
    )
    def test_add_note_whose_case_is_not_the_target_is_refused(
        self, make_payload, note_context
    ):
        """A new note whose own case is not the Add's target, or names no
        case, is refused before the commit and is not stored (#4831)."""
        case_actor_id = "https://example.org/cases/case_n1g/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1g"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note_id = "https://example.org/notes/note3g"
        entries_before = len(dl.list_objects("CaseLedgerEntry"))

        event = make_payload(
            add_note_to_case_activity(
                make(
                    as_Note,
                    id_=note_id,
                    content="Elsewhere",
                    context=note_context,
                ),
                target=case,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        )
        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(note_id) is None
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert note_id not in refreshed.notes
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_before

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.spec("VAM-01-015")
    def test_add_reply_note_through_ingress_is_applied(self):
        """A reply note sent through the inbox ingress is stored and attached
        with its ``in_reply_to``: the event carries the note as received, so
        the guard sees the same note the routing rebuild staged (#4706)."""
        case_actor_id = "https://example.org/cases/case_n1f/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1f"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note_id = "https://example.org/notes/note3f"
        replied_to = "https://example.org/notes/note3f-question"

        activity = add_note_to_case_activity(
            make(
                as_Note,
                id_=note_id,
                content="An answer",
                context=case_id,
                attributed_to="https://example.org/users/finder",
                in_reply_to=replied_to,
            ),
            target=case,
            actor="https://example.org/users/finder",
            to=[dl.actor_id],
            at=authored_at(),
        )
        ingress = FastAPIIngressAdapter(dl)
        parsed = ingress.parse(delivered_body(activity, at=dl))
        assert parsed is not None
        event = received_event(ingress.rehydrate(parsed), at=dl).model_copy(
            update={"receiving_actor_id": case_actor_id}
        )
        assert isinstance(event, AddNoteToCaseReceivedEvent)
        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.APPLIED
        assert _as_id(getattr(dl.read(note_id), "in_reply_to", None)) == (
            replied_to
        )
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert note_id in refreshed.notes
        assert dl.read(activity.id_) is None, "held only as received"

    @pytest.mark.spec("HP-01-005")
    def test_add_note_without_an_inline_note_is_refused(self, make_payload):
        """An Add(Note) event with no note object is refused before any
        tree runs: there is no note to store or attach (#4706)."""
        case_actor_id = "https://example.org/cases/case_n1e/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n1e"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        event = make_payload(
            add_note_to_case_activity(
                make(
                    as_Note,
                    id_="https://example.org/notes/note3e",
                    content="x",
                ),
                target=case,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        ).model_copy(update={"object_": None})

        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "inline note" in result.reason

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.spec("CM-13-007")
    def test_redelivered_add_note_is_skipped(self, make_payload):
        """A redelivery of an Add(Note) the case's ledger already records is
        SKIPPED: the note stays attached once and no second entry is
        committed (HP-01-003, #4831)."""
        case_actor_id = "https://example.org/cases/case_n2/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n2"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note = make(
            as_Note,
            id_="https://example.org/notes/note4",
            content="A note",
            context=case_id,
        )
        event = make_payload(
            add_note_to_case_activity(
                note,
                target=case,
                actor="https://example.org/users/finder",
                to=[dl.actor_id],
                at=authored_at(),
            ),
            receiving_actor_id=case_actor_id,
            at=dl,
        )

        def run():
            return run_in_act(
                AddNoteToCaseReceivedUseCase(
                    dl,
                    event,
                    wire_render_port=As2WireRenderAdapter(),
                    sync_port=SyncActivityAdapter(dl),
                )
            )

        assert run().disposition == HandlerDisposition.APPLIED
        entries_after_first = len(dl.list_objects("CaseLedgerEntry"))

        result = run()

        assert result.disposition == HandlerDisposition.SKIPPED
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert refreshed.notes.count(note.id_) == 1
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_after_first

    @pytest.mark.spec("HP-08-006")
    @pytest.mark.spec("CM-13-007")
    def test_new_add_naming_an_attached_note_is_refused(self, make_payload):
        """A second, different Add(Note) naming a note the case already holds
        is refused, even with the same content: an Add introduces a note,
        and changing one is an Update(Note) (#4831)."""
        case_actor_id = "https://example.org/cases/case_n2b/actor"
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=case_actor_id)
        case_id = "https://example.org/cases/case_n2b"
        case = self._setup_case_with_case_manager(dl, case_id, case_actor_id)
        note = make(
            as_Note,
            id_="https://example.org/notes/note4b",
            content="A note",
            context=case_id,
        )

        def run():
            return run_in_act(
                AddNoteToCaseReceivedUseCase(
                    dl,
                    make_payload(
                        add_note_to_case_activity(
                            note,
                            target=case,
                            actor="https://example.org/users/finder",
                            to=[dl.actor_id],
                            at=authored_at(),
                        ),
                        receiving_actor_id=case_actor_id,
                        at=dl,
                    ),
                    wire_render_port=As2WireRenderAdapter(),
                    sync_port=SyncActivityAdapter(dl),
                )
            )

        assert run().disposition == HandlerDisposition.APPLIED
        entries_after_first = len(dl.list_objects("CaseLedgerEntry"))

        result = run()

        assert result.disposition == HandlerDisposition.REFUSED
        refreshed = cast(as_VulnerabilityCase, dl.read(case_id))
        assert refreshed.notes.count(note.id_) == 1
        assert len(dl.list_objects("CaseLedgerEntry")) == entries_after_first

    @pytest.mark.spec("HP-01-005")
    def test_add_note_refused_for_non_case_manager(
        self, monkeypatch, make_payload
    ):
        """A non-manager receiving Add(Note)[target=VulnerabilityCase] neither attaches
        nor commits.

        Case replica updates arrive exclusively via Announce(CaseLedgerEntry)
        fan-out (SYNC-02-001, SYNC-02-003). The BT CheckIsCaseManagerNode guard
        keeps the non-manager from attaching or committing, and the handler
        reports the misaddressed note as a refusal (#3752).
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/actors/non-manager",
        )
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/case_n3_noop",
            name="Noop Case",
        )
        # Somebody else holds CASE_MANAGER, so the gate fails on "this actor
        # is not the manager" rather than on "no role holder" (BT-17-005).
        seed_case_manager_participant(
            dl, case, "https://example.org/actors/case-manager"
        )
        note = make(
            as_Note,
            id_="https://example.org/notes/note_noop",
            content="A note",
            context=case.id_,
        )
        dl.create(case)

        activity = add_note_to_case_activity(
            note,
            target=case,
            actor="https://example.org/users/finder",
            to=[dl.actor_id],
            at=authored_at(),
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/non-manager",
            at=dl,
        )

        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        refreshed = dl.read(case.id_)
        assert refreshed is not None
        refreshed = cast(as_VulnerabilityCase, refreshed)
        assert note.id_ not in refreshed.notes
        # HP-01-005: a note addressed to the wrong party is refused, not
        # reported as a processed no-op.
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "CASE_MANAGER" in result.reason

    def _managed_case_with_note(
        self, dl: SqliteDataLayer, case_id: str, note: as_Note, owner_id: str
    ) -> as_VulnerabilityCase:
        """A case the store's actor manages, owned by *owner_id*, holding *note*."""
        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="Remove Note Case",
            attributed_to=owner_id,
            notes=[note.id_],
        )
        seed_case_manager_participant(dl, case, _STORE_ACTOR)
        seed_case_owner_participant(dl, case, owner_id)
        dl.create(case)
        dl.create(note)
        return case

    def _remove(self, dl, make_payload, sender, note, case):
        event = make_payload(
            make(
                as_Remove,
                actor=sender,
                object_=note,
                target=case.id_,
                to=[dl.actor_id],
            ),
            at=dl,
        )
        return run_in_act(
            RemoveNoteFromCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

    @pytest.mark.spec("CM-30-003")
    @pytest.mark.spec("CM-30-001")
    @pytest.mark.parametrize("sender", ["author", "owner"])
    def test_every_receiver_refuses_remove_note(
        self, make_payload, sender: str
    ):
        """Removing ledgered content is not supported (CM-30-003, #6430).

        The CASE_MANAGER refuses a Remove(Note) even from the note's author
        or the Case Owner, the senders CM-30-001 names: the note stays
        attached and no entry is committed.
        """
        dl, note, case, author = self._removal_world(at_manager=True)
        sender_id = {"author": author, "owner": _OWNER}[sender]

        result = self._remove(dl, make_payload, sender_id, note, case)

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason == REMOVE_NOTE_UNSUPPORTED
        self._assert_note_kept(dl, note, case)

    @pytest.mark.spec("CM-30-003")
    @pytest.mark.spec("CM-30-004")
    def test_remove_note_from_an_unentitled_sender_is_refused(
        self, make_payload
    ):
        """A sender CM-30-001 does not name is refused by the sender guard."""
        dl, note, case, _ = self._removal_world(at_manager=True)

        result = self._remove(
            dl, make_payload, "https://example.org/actors/stranger", note, case
        )

        assert result.disposition == HandlerDisposition.REFUSED
        self._assert_note_kept(dl, note, case)

    @pytest.mark.spec("CM-30-003")
    @pytest.mark.spec("HP-01-005")
    @pytest.mark.parametrize("sender", ["author", "manager"])
    def test_a_replica_refuses_remove_note_at_its_path_stage(
        self, make_payload, sender: str
    ):
        """A replica is not addressed, so its path stage refuses the Remove,
        the CASE_MANAGER's own included (HP-01-005, PCR-08-001)."""
        dl, note, case, author = self._removal_world(at_manager=False)
        sender_id = {"author": author, "manager": _OTHER_MANAGER}[sender]

        result = self._remove(dl, make_payload, sender_id, note, case)

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason == f"not the CASE_MANAGER of case '{case.id_}'"
        self._assert_note_kept(dl, note, case)

    @pytest.mark.spec("CLP-10-018")
    @pytest.mark.parametrize(
        ("note_id", "case_id"),
        [(None, "https://example.org/cases/c"), ("urn:note", None)],
        ids=["no-note", "no-case"],
    )
    def test_a_remove_note_naming_no_note_or_case_is_refused_as_incomplete(
        self, note_id, case_id
    ):
        """The tree, not execute(), refuses a Remove with no note or no case:
        it archives the activity and refuses it as incomplete (CLP-10-018)."""
        tree = create_remove_note_from_case_received_tree(
            note_id=note_id,
            case_id=case_id,
            sender_id=_OWNER,
            sender_rule=RemoveNoteFromCaseReceivedUseCase.sender_entitlement,
        )
        guards = [
            n for n in tree.iterate() if isinstance(n, ActivityIncompleteNode)
        ]
        assert len(guards) == 1
        assert not isinstance(guards[0], ActivityUnsupportedNode)
        assert "missing its note id or case id" in guards[0].reason

    def _removal_world(self, *, at_manager: bool):
        """A case holding the author's note, at its CASE_MANAGER or a replica."""
        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_STORE_ACTOR)
        author = "https://example.org/actors/note-author"
        note = make(
            as_Note,
            id_="https://example.org/notes/note_unsupported",
            content="A note",
            attributed_to=author,
        )
        case = make(
            as_VulnerabilityCase,
            id_="https://example.org/cases/case_remove_unsupported",
            name="Remove Note Case",
            attributed_to=_OWNER,
            notes=[note.id_],
        )
        seed_case_manager_participant(
            dl, case, _STORE_ACTOR if at_manager else _OTHER_MANAGER
        )
        seed_case_owner_participant(dl, case, _OWNER)
        seed_case_participant(dl, case, author)
        dl.create(case)
        dl.create(note)
        return dl, note, case, author

    @staticmethod
    def _assert_note_kept(dl, note, case) -> None:
        stored = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert note.id_ in stored.notes
        assert dl.list_objects("CaseLedgerEntry") == []

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "use_case",
        [AddNoteToCaseReceivedUseCase],
    )
    def test_note_membership_change_without_ids_is_refused(self, use_case):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        event = MagicMock()
        event.note_id = None
        event.case_id = "https://example.org/cases/c"

        result = run_in_act(use_case(dl, event))

        assert result.disposition == HandlerDisposition.REFUSED

    @pytest.mark.spec("HP-01-003")
    def test_add_note_to_unknown_case_is_refused(self, make_payload):
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/actors/non-manager",
        )
        case = make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/never-stored",
            name="x",
        )
        note = make(
            as_Note, id_="https://example.org/notes/note9", content="x"
        )
        activity = add_note_to_case_activity(
            note,
            target=case,
            actor="https://example.org/users/finder",
            to=[dl.actor_id],
            at=authored_at(),
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/actors/non-manager",
            at=dl,
        )

        result = run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            )
        )

        assert result.disposition == HandlerDisposition.REFUSED

    # ------------------------------------------------------------------
    # CaseLedgerEntry cascade tests (PCR-08-003, PCR-08-004) — AC-1
    # ------------------------------------------------------------------

    @pytest.mark.spec("PCR-08-013")
    @pytest.mark.spec("PCR-08-003")
    @pytest.mark.spec("VP-18-001")
    @pytest.mark.spec("VP-18-003")
    def test_add_note_commits_log_entry_when_sync_port_provided(
        self, make_payload
    ):
        """AddNoteToCaseReceivedUseCase commits a CaseLedgerEntry (PCR-08-003).

        When a sync_port is injected and receiving_actor_id is set, the use
        case MUST commit one CaseLedgerEntry after accepting a note
        addition, and announce it to the case's participants.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_le1/actor",
        )
        case_actor_id = "https://example.org/cases/case_le1/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le1"

        case_actor = make(
            VultronService,
            id_=case_actor_id,
            name="CaseActor le1",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="Log Entry Cascade Case",
            attributed_to=author_id,
        )
        # The sender attaches the note as an active participant
        # (CM-23-018, HP-01-006).
        seed_case_participant(dl, case, author_id)
        seed_case_participant(dl, case, participant_id)
        dl.create(case)
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = make(
            as_CaseParticipant,
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)

        note = make(
            as_Note,
            id_="https://example.org/notes/note_le1",
            content="Log entry cascade note",
            context=case_id,
        )

        activity = add_note_to_case_activity(
            note,
            target=case,
            actor=author_id,
            to=[dl.actor_id],
            at=authored_at(),
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id, at=dl)

        sync_port = SyncActivityAdapter(dl)
        # Record, at each fan-out, whether the announced entry is already
        # in the ledger store: the entry is recorded before it is fanned
        # out (VP-18-003).
        stored_at_fan_out: list[bool] = []
        send_announce = sync_port.send_announce_log_entry

        def recording_send_announce(
            entry: CaseLedgerEntry, actor_id: str, to: list[str], *, at
        ) -> bool:
            stored_at_fan_out.append(dl.read(entry.id_) is not None)
            return bool(send_announce(entry, actor_id, to, at=at))

        sync_port.send_announce_log_entry = recording_send_announce  # type: ignore[method-assign]
        run_in_act(
            AddNoteToCaseReceivedUseCase(
                dl,
                event,
                sync_port=sync_port,
                wire_render_port=As2WireRenderAdapter(),
            )
        )

        assert stored_at_fan_out and all(stored_at_fan_out)

        # Exactly one CaseLedgerEntry should be persisted for this case.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        entry = cast(CaseLedgerEntry, entries[0])
        assert entry.semantic_type == "add_note_to_case"
        assert entry.log_object_id == activity.id_

        # The same processing announces that entry to both participants.
        announces = [
            queued
            for queued in (
                dl.read(activity_id) for activity_id in dl.outbox_list()
            )
            if getattr(queued, "type_", None) == "Announce"
            and _as_id(getattr(queued, "object_", None)) == entry.id_
        ]
        assert announces
        announced_to = {
            recipient
            for announce in announces
            for recipient in recipient_ids(announce)
        }
        assert announced_to == {author_id, participant_id}

    @pytest.mark.spec("SYNC-02-003")
    @pytest.mark.spec("BT-14-001")
    def test_add_note_without_sync_port_raises_as_wiring_fault(
        self, make_payload
    ):
        """A missing sync_port fails the commit instead of skipping fan-out.

        ``RequireSyncPortNode`` raises ``VultronWiringError`` before the entry
        is minted (#4113).  ``CommitCaseLedgerEntryNode`` carries the nested
        bridge's ``internal_error`` across the hop, so the handler raises
        ``VultronBTInternalError`` rather than reporting the sender as refused
        (ADR-0095).  The note is not attached and nothing is announced.
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://example.org/cases/case_le2/actor",
        )
        case_actor_id = "https://example.org/cases/case_le2/actor"
        author_id = "https://example.org/users/vendor"
        participant_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_le2"

        case_actor = make(
            VultronService,
            id_=case_actor_id,
            name="CaseActor le2",
            attributed_to=author_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = make(
            as_VulnerabilityCase,
            id_=case_id,
            name="No Sync Port Case",
            attributed_to=author_id,
        )
        # The sender attaches the note as an active participant
        # (CM-23-018, HP-01-006).
        seed_case_participant(dl, case, author_id)
        seed_case_participant(dl, case, participant_id)
        dl.create(case)
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        case_manager_participant = make(
            as_CaseParticipant,
            id_=f"{case_id}/participants/case-actor-p",
            attributed_to=case_actor_id,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)
        case.case_participants.append(case_manager_participant.id_)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant.id_
        )
        dl.save(case)

        note = make(
            as_Note,
            id_="https://example.org/notes/note_le2",
            content="No cascade note",
            context=case_id,
        )

        activity = add_note_to_case_activity(
            note,
            target=case,
            actor=author_id,
            to=[dl.actor_id],
            at=authored_at(),
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id, at=dl)

        # No sync_port — the commit's fan-out is a wiring fault.
        with pytest.raises(VultronBTInternalError, match="sync_port"):
            run_in_act(
                AddNoteToCaseReceivedUseCase(
                    dl,
                    event,
                    sync_port=None,
                    wire_render_port=As2WireRenderAdapter(),
                )
            )

        stored_case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert stored_case is not None
        assert note.id_ not in stored_case.notes

        # The port guard refuses before the mint, so no entry is written
        # that no replica would ever receive.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry)
            and cast(CaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

        # Nothing is announced to participants.
        assert dl.outbox_list() == []
