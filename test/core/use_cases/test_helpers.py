#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute
#    to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype
#  is licensed under a MIT (SEI)-style license, please see LICENSE.md
#  distributed with this Software or contact permission@sei.cmu.edu for full
#  terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Regression tests for ``resolve_case_participant_id_for_actor``.

Covers the divergence-detection contract between ``case_participants``
(canonical source) and ``actor_participant_index`` (derived cache):

- Happy path: both surfaces consistent → canonical ID returned.
- Cache miss: participant in ``case_participants`` but absent from index
  → canonical ID returned (cache-miss is not an error).
- Inline participant object in ``case_participants`` → canonical ID returned.
- Actor absent from both surfaces → None returned.
- Stale index: actor in ``actor_participant_index`` but no matching entry
  in ``case_participants`` → VultronValidationError raised.
- Index divergence: ``case_participants`` and ``actor_participant_index``
  disagree on the participant ID → VultronValidationError raised.
- Duplicate actor in ``case_participants``: two distinct participants share
  the same ``attributed_to`` actor → VultronValidationError raised.

Reference: AGENTS.md § "Case Participant Lookup Must Fail Fast on Surface
Divergence", issue #822, issue #825.
"""

from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.enums.roles import CVDRole
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.use_cases._helpers import (
    _find_case_actor_id,
    resolve_case_participant_id_for_actor,
    resolve_receiving_actor_id,
)
from vultron.errors import VultronValidationError

_ACTOR_ID = "https://example.org/actors/vendor-001"
_CASE_ID = "https://example.org/cases/case-001"
_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-001"
_ALT_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor-alt"


@pytest.fixture()
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture()
def participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_PARTICIPANT_ID,
        attributed_to=_ACTOR_ID,
        context=_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


@pytest.fixture()
def seeded_case(
    dl: SqliteDataLayer, participant: CaseParticipant
) -> VulnerabilityCase:
    """Case with participant stored in DL and registered on both surfaces."""
    dl.create(participant)
    case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
    case.add_participant(participant)
    dl.create(case)
    stored = dl.read(_CASE_ID)
    assert isinstance(
        stored, VulnerabilityCase
    ), "seeded_case: DL did not return a VulnerabilityCase"
    return stored


class TestResolveCaseParticipantIdForActor:
    """Contract tests for resolve_case_participant_id_for_actor."""

    def test_happy_path_returns_canonical_id(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer
    ) -> None:
        """Both surfaces consistent: canonical participant ID is returned."""
        result = resolve_case_participant_id_for_actor(
            seeded_case, _ACTOR_ID, dl
        )
        assert result == _PARTICIPANT_ID

    def test_cache_miss_returns_canonical_id(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Participant in case_participants but absent from index → no error.

        A missing index entry (cache miss) is not a divergence — the canonical
        list has the correct entry so the ID should be resolved without error.
        """
        dl.create(participant)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Populate only case_participants; omit actor_participant_index entry.
        case.case_participants.append(_PARTICIPANT_ID)
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)
        assert result == _PARTICIPANT_ID

    def test_inline_participant_object_resolved(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Inline CaseParticipant object in case_participants is resolved."""
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Store participant inline (not as a string ID) — simulates wire-layer
        # round-trips where objects arrive embedded rather than referenced.
        case.case_participants.append(participant)  # type: ignore[arg-type]
        case.actor_participant_index[_ACTOR_ID] = _PARTICIPANT_ID
        dl.create(participant)
        dl.create(case)

        # Re-read from DL: the DL normalises inline objects to typed records.
        # The case must still resolve via the inline-then-rehydrated path.
        stored = dl.read(_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)
        assert result == _PARTICIPANT_ID

    def test_not_found_returns_none(
        self, seeded_case: VulnerabilityCase, dl: SqliteDataLayer
    ) -> None:
        """Actor not in case at all → None returned without error."""
        unknown_id = "https://example.org/actors/unknown"
        result = resolve_case_participant_id_for_actor(
            seeded_case, unknown_id, dl
        )
        assert result is None

    def test_stale_index_raises(self, dl: SqliteDataLayer) -> None:
        """Actor in actor_participant_index but not in case_participants raises.

        This is the canonical stale-cache divergence: the index claims an entry
        exists but the authoritative list has no matching participant.  Any code
        that only populates the index (without case_participants) is in error.
        """
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Stale index: actor mapped to a participant ID, but case_participants
        # is empty so there is no canonical entry to validate against.
        case.actor_participant_index[_ACTOR_ID] = _PARTICIPANT_ID
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        with pytest.raises(
            VultronValidationError, match="actor_participant_index"
        ):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)

    def test_index_divergence_raises(
        self, dl: SqliteDataLayer, participant: CaseParticipant
    ) -> None:
        """Index maps actor to a different ID than case_participants → raises.

        This is the strict divergence case: both surfaces have an entry for the
        same actor, but they disagree on which participant ID is authoritative.
        """
        dl.create(participant)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        # Canonical list has the correct participant.
        case.case_participants.append(_PARTICIPANT_ID)
        # Index deliberately maps to a *different* ID.
        case.actor_participant_index[_ACTOR_ID] = _ALT_PARTICIPANT_ID
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        with pytest.raises(VultronValidationError, match="divergence"):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)

    def test_duplicate_actor_in_canonical_list_raises(
        self, dl: SqliteDataLayer
    ) -> None:
        """Two distinct participants with the same attributed_to actor → raises.

        The canonical list must be unique per actor; duplicates indicate a
        write-path bug that must surface immediately rather than silently
        choosing one entry.
        """
        p1 = CaseParticipant(
            id_=_PARTICIPANT_ID,
            attributed_to=_ACTOR_ID,
            context=_CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        p2 = CaseParticipant(
            id_=_ALT_PARTICIPANT_ID,
            attributed_to=_ACTOR_ID,
            context=_CASE_ID,
            case_roles=[CVDRole.VENDOR],
        )
        dl.create(p1)
        dl.create(p2)
        case = VulnerabilityCase(id_=_CASE_ID, name="Test Case")
        case.case_participants.append(_PARTICIPANT_ID)
        case.case_participants.append(_ALT_PARTICIPANT_ID)
        dl.create(case)

        stored = dl.read(_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        with pytest.raises(
            VultronValidationError, match="multiple participants"
        ):
            resolve_case_participant_id_for_actor(stored, _ACTOR_ID, dl)


# ---------------------------------------------------------------------------
# Tests for resolve_case_manager_id (consolidated canonical function)
# ---------------------------------------------------------------------------

_CM_ACTOR_ID = "https://example.org/actors/case-manager-001"
_CM_CASE_ID = "https://example.org/cases/cm-case-001"
_CM_PARTICIPANT_ID = f"{_CM_CASE_ID}/participants/case-manager-001"
_VENDOR_ACTOR_ID = "https://example.org/actors/vendor-002"
_VENDOR_PARTICIPANT_ID = f"{_CM_CASE_ID}/participants/vendor-002"


@pytest.fixture()
def cm_dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture()
def cm_participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_CM_PARTICIPANT_ID,
        attributed_to=_CM_ACTOR_ID,
        context=_CM_CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )


@pytest.fixture()
def vendor_participant() -> CaseParticipant:
    return CaseParticipant(
        id_=_VENDOR_PARTICIPANT_ID,
        attributed_to=_VENDOR_ACTOR_ID,
        context=_CM_CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )


class TestResolveCaseManagerId:
    """Contract tests for resolve_case_manager_id (consolidated helper).

    Verifies that the canonical implementation handles:
    - ID-only participants stored in the DataLayer
    - Inline participant objects (bootstrap path)
    - No CASE_MANAGER participant → None
    - Multiple participants where only one is CASE_MANAGER
    """

    def test_dl_participant_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """ID-only participant stored in DL: returns attributed_to actor ID."""
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="CM Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID

    def test_inline_participant_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """Inline participant object (bootstrap path): returns attributed_to."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="CM Inline Test")
        case.case_participants.append(cm_participant)  # type: ignore[arg-type]
        result = resolve_case_manager_id(cast(VulnerabilityCase, case), cm_dl)
        assert result == _CM_ACTOR_ID

    def test_no_case_manager_returns_none(
        self,
        cm_dl: SqliteDataLayer,
        vendor_participant: CaseParticipant,
    ) -> None:
        """No CASE_MANAGER participant: returns None."""
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="No CM Test")
        case.case_participants.append(_VENDOR_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_empty_case_participants_returns_none(
        self,
        cm_dl: SqliteDataLayer,
    ) -> None:
        """Empty case_participants: returns None."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Empty Test")
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_skips_non_manager_returns_manager(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
        vendor_participant: CaseParticipant,
    ) -> None:
        """Multiple participants: returns CASE_MANAGER actor ID, skips others."""
        cm_dl.create(cm_participant)
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Multi Test")
        case.case_participants.append(_VENDOR_PARTICIPANT_ID)
        case.case_participants.append(_CM_PARTICIPANT_ID)
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID

    def test_missing_dl_record_skipped(
        self,
        cm_dl: SqliteDataLayer,
    ) -> None:
        """ID-only reference with no DL record: skipped, returns None."""
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Missing DL Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)  # not in DL
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result is None

    def test_primary_index_path_returns_actor_id(
        self,
        cm_dl: SqliteDataLayer,
        cm_participant: CaseParticipant,
    ) -> None:
        """Primary fast-path via actor_participant_index returns actor ID."""
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Index Fast-Path Test")
        case.case_participants.append(_CM_PARTICIPANT_ID)
        case.actor_participant_index[_CM_ACTOR_ID] = _CM_PARTICIPANT_ID
        cm_dl.create(case)
        stored = cm_dl.read(_CM_CASE_ID)
        assert isinstance(stored, VulnerabilityCase)
        result = resolve_case_manager_id(stored, cm_dl)
        assert result == _CM_ACTOR_ID


# ---------------------------------------------------------------------------
# Tests for _find_case_actor_id
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-02-011")
@pytest.mark.spec("ARCH-24-004")
class TestFindCaseActorId:
    """Contract tests for the two resolution paths of _find_case_actor_id.

    This helper answers **"what address do I route to?"**, not "am I the
    authority" (ARCH-24-005).  Because authority *is* the
    ``CVDRole.CASE_MANAGER`` role (CM-02-011), the authority's address is the
    role-holder's address, so there are only two paths: the address recorded on
    a completed ``ReportCaseLink`` during bootstrap, and the role-holder on the
    case replica.

    ADR-0088 removed two former paths outright.  Neither a URL's *shape* nor a
    ``Service`` object's *hosting location* is evidence of anything
    protocol-salient (ARCH-24-004, CM-02-013), and a pending-link path existed
    only to supply the "is it really a CaseActor" evidence the shape gate
    demanded — once the role answers unconditionally, the replica's roster
    covers that window on its own (CP-09-004).
    """

    def test_link_path_takes_precedence(
        self, cm_dl: SqliteDataLayer, cm_participant: CaseParticipant
    ) -> None:
        """A link with trusted_case_actor_id wins over the pending-link path."""
        link_actor_id = "https://example.org/actors/case-actor-from-link"
        cm_dl.create(
            VultronReportCaseLink(
                report_id="https://example.org/reports/r1",
                case_id=_CM_CASE_ID,
                trusted_case_actor_id=link_actor_id,
            )
        )
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Link Path")
        case.add_participant(cm_participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) == link_actor_id

    def test_role_holder_resolves_without_any_service_object(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """The role alone resolves — no ``Service`` object required (CM-02-012).

        This is the bootstrap window that broke the old hosting scan: under
        ADR-0041 the ``Service`` object the receiver writes ahead of
        ``Create(as_CaseProposal)`` carries no ``context`` (the case does not
        exist yet), so a ``context == case_id`` scan found nothing and the real
        authority failed its own hosting test.  The roster has no such window.
        """
        case_actor_id = "https://case-actor.test/api/v2/actors/case-actor"
        participant = CaseParticipant(
            id_=f"{_CM_CASE_ID}/participants/case-actor",
            attributed_to=case_actor_id,
            context=_CM_CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        cm_dl.create(participant)
        # Present but context-less, exactly as ADR-0041 writes it.
        cm_dl.create(VultronCaseActor(id_=case_actor_id, name="CaseActor"))
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Role Is The Marker")
        case.add_participant(participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) == case_actor_id

    def test_an_ordinary_participant_enacting_case_manager_resolves(
        self, cm_dl: SqliteDataLayer, cm_participant: CaseParticipant
    ) -> None:
        """ADR-0088: the role-holder is the authority whatever its id looks like.

        ``_CM_ACTOR_ID`` is ``.../actors/case-manager-001`` — an ordinary
        participant identity, nothing CaseActor-shaped about it — and it holds
        ``CVDRole.CASE_MANAGER``.  It therefore *is* this case's authority and
        *is* the address to route to.

        This inverts what this helper used to do.  The old shape gate resolved
        ``None`` here, on the ADR-0021 reading that "a case whose manager is an
        ordinary participant has no CaseActor".  ADR-0088 retires that reading:
        there is no separate CaseActor entity that could be absent while the
        role is held, so ``None`` was withholding a perfectly good address and
        making routing depend on a naming convention (CM-02-013).
        """
        cm_dl.create(cm_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Ordinary Manager")
        case.add_participant(cm_participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) == _CM_ACTOR_ID

    def test_a_slugged_role_holder_resolves_to_its_own_id(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """A ``case-actor-<slug>`` role-holder is returned, not rejected.

        The old code special-cased this form as unhostable (#1872) and answered
        ``None``.  That was the URL shape deciding routing, which ARCH-24-004
        forbids: if an actor holds the role, its id is the address, and a
        delivery failure is the honest outcome of a mis-provisioned actor rather
        than something this lookup should paper over by claiming the case has no
        authority at all.
        """
        slugged = "https://case-actor.test/api/v2/actors/case-actor-abc123"
        participant = CaseParticipant(
            id_=f"{_CM_CASE_ID}/participants/slugged",
            attributed_to=slugged,
            context=_CM_CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        cm_dl.create(participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Slugged")
        case.add_participant(participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) == slugged

    def test_a_hosting_service_object_no_longer_resolves(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """ARCH-24-004: a ``Service`` whose ``context`` is the case is not an answer.

        The legacy scan this replaces would have returned *service_id* here.  It
        is gone: hosting location is not evidence of authority or of routing, and
        with no CASE_MANAGER on the roster this case genuinely has no resolvable
        authority address.
        """
        service_id = "https://example.org/actors/case-actor-legacy"
        cm_dl.create(
            VultronCaseActor(
                id_=service_id, name="Legacy CaseActor", context=_CM_CASE_ID
            )
        )
        cm_dl.create(VulnerabilityCase(id_=_CM_CASE_ID, name="Legacy Path"))

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) is None

    def test_a_pending_link_alone_does_not_resolve(
        self, cm_dl: SqliteDataLayer, vendor_participant: CaseParticipant
    ) -> None:
        """Only a *completed* link records a trusted address.

        A pending link carries ``trusted_case_creator_id`` — the actor a
        proposal went *to* — which is a proposal target, not a confirmed
        authority.  With no CASE_MANAGER on the roster to corroborate it, there
        is nothing to route to.
        """
        cm_dl.create(
            VultronReportCaseLink(
                report_id="https://example.org/reports/other",
                trusted_case_creator_id=(
                    "https://example.org/actors/case-actor-unrelated"
                ),
            )
        )
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Unrelated Proposal")
        case.add_participant(vendor_participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) is None

    def test_returns_none_when_unresolvable(
        self, cm_dl: SqliteDataLayer, vendor_participant: CaseParticipant
    ) -> None:
        """No completed link and no CASE_MANAGER participant → None."""
        cm_dl.create(vendor_participant)
        case = VulnerabilityCase(id_=_CM_CASE_ID, name="Unresolvable")
        case.add_participant(vendor_participant)
        cm_dl.create(case)

        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) is None

    def test_returns_none_for_an_unknown_case(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """A case absent from this store has no address to resolve."""
        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) is None

    def test_returns_none_when_case_absent(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """A missing case must not raise — the participant path just skips."""
        assert _find_case_actor_id(cm_dl, _CM_CASE_ID) is None


class TestResolveReceivingActorId:
    """``resolve_receiving_actor_id`` — whose replica is this message applied to?

    Under ADR-0073 ``actor_id`` *selects the store*, so this is not a labelling
    question. The ``or "unknown"`` fabrication it replaced would now route every
    read and write into an empty scratch store named ``unknown``, losing the work
    with no error raised anywhere (ARCH-15-001). That is why the no-answer case
    raises rather than defaulting.
    """

    _INBOX_ACTOR = "https://example.org/api/v2/actors/vendor"

    def test_the_inbox_supplied_id_is_authoritative(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """The inbox adapter knows which actor's inbox was POSTed to (BT-17-005)."""
        assert (
            resolve_receiving_actor_id(cm_dl, self._INBOX_ACTOR)
            == self._INBOX_ACTOR
        )

    def test_the_inbox_id_wins_over_the_stores_own_actor(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """Both are present and disagree; the request is the more specific fact."""
        assert cm_dl.actor_id != self._INBOX_ACTOR
        assert (
            resolve_receiving_actor_id(cm_dl, self._INBOX_ACTOR)
            == self._INBOX_ACTOR
        )

    def test_falls_back_to_the_actor_whose_store_we_hold(
        self, cm_dl: SqliteDataLayer
    ) -> None:
        """CLI dispatch, replay and tests carry no receiving_actor_id.

        The fallback is not a guess: a received-side use case is by construction
        invoked with the receiving actor's own store (CM-01-001), and under
        ADR-0073 a DataLayer is always some specific actor's.
        """
        assert (
            resolve_receiving_actor_id(cm_dl, None)
            == "https://test.example/api/v2/actors/test-actor"
        )

    @pytest.mark.parametrize("empty", [None, ""])
    def test_an_empty_inbox_id_is_treated_as_absent(
        self, cm_dl: SqliteDataLayer, empty: str | None
    ) -> None:
        """``""`` must not become the actor id — it names no store."""
        assert (
            resolve_receiving_actor_id(cm_dl, empty)
            == "https://test.example/api/v2/actors/test-actor"
        )

    @pytest.mark.parametrize("own", [None, "", 42])
    def test_raises_when_neither_source_yields_an_identity(
        self, own: object
    ) -> None:
        """No defensible answer to "whose replica is this?" — so refuse.

        ``42`` covers the non-string branch: a store reporting a non-string
        ``actor_id`` is as unusable as one reporting nothing, and silently
        stringifying it would mint a store named ``"42"``.
        """

        class _StoreWithoutAnActor:
            actor_id = own

        with pytest.raises(VultronValidationError, match="CM-01-001"):
            resolve_receiving_actor_id(
                cast(SqliteDataLayer, _StoreWithoutAnActor()), None
            )

    def test_raises_when_the_store_reports_no_actor_attribute_at_all(
        self,
    ) -> None:
        """``getattr`` default path: a stub port with no ``actor_id``."""
        with pytest.raises(VultronValidationError):
            resolve_receiving_actor_id(cast(SqliteDataLayer, object()), None)

    def test_propagates_not_implemented_from_actor_id_property(
        self,
    ) -> None:
        """A stub whose ``actor_id`` raises ``NotImplementedError`` propagates it.

        ``NotImplementedError`` from a property getter is a programming error
        (the adapter is incomplete), not a data-availability problem.  It must
        not be silently converted to ``VultronValidationError`` — callers need
        the unambiguous signal that the adapter is broken, not a misleading
        "no receiving actor" diagnosis (CM-01-001 port contract).
        """

        class _StubWithRaisingActorId:
            @property
            def actor_id(self) -> str:
                raise NotImplementedError(
                    "actor_id not implemented on this stub"
                )

        with pytest.raises(NotImplementedError):
            resolve_receiving_actor_id(
                cast(SqliteDataLayer, _StubWithRaisingActorId()), None
            )
