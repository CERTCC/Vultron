#!/usr/bin/env python

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

"""``has_role`` is the one way to ask whether an actor holds a role in a case
(ADR-0153, CM-02-011)."""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants._lookup import iter_case_participants
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/role-predicate"
MANAGER_ID = "https://example.org/actors/coordinator"
VENDOR_ID = "https://example.org/actors/vendor"
STRANGER_ID = "https://example.org/actors/stranger"
SECOND_ID = "https://example.org/actors/second-coordinator"
OWNER_ID = "https://example.org/actors/owner"


def _participant(suffix: str, actor_id: str, *roles: CVDRole):
    return CaseParticipant(
        id_=f"{CASE_ID}/participants/{suffix}",
        attributed_to=actor_id,
        context=CASE_ID,
        case_roles=list(roles),
    )


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER_ID)


@pytest.fixture
def seeded(dl: SqliteDataLayer) -> SqliteDataLayer:
    manager = _participant("manager", MANAGER_ID, CVDRole.CASE_MANAGER)
    vendor = _participant("vendor", VENDOR_ID, CVDRole.VENDOR)
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="ROLE-PREDICATE",
        attributed_to=OWNER_ID,
        case_participants=[manager.id_, vendor.id_],
        actor_participant_index={
            MANAGER_ID: manager.id_,
            VENDOR_ID: vendor.id_,
        },
    )
    dl.create(manager)
    dl.create(vendor)
    dl.create(case)
    return dl


@pytest.mark.spec("CM-02-011")
def test_the_role_holder_holds_the_role(seeded: SqliteDataLayer) -> None:
    assert has_role(MANAGER_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is True


@pytest.mark.spec("CM-02-011")
def test_another_participant_does_not(seeded: SqliteDataLayer) -> None:
    """A participant of the case without the role answers False, not an error."""
    assert has_role(VENDOR_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is False
    assert has_role(VENDOR_ID, CASE_ID, CVDRole.VENDOR, seeded) is True


@pytest.mark.spec("CM-02-011")
def test_an_actor_outside_the_roster_does_not(
    seeded: SqliteDataLayer,
) -> None:
    assert (
        has_role(STRANGER_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is False
    )


@pytest.mark.spec("CM-02-011")
def test_a_case_the_store_does_not_hold_answers_false(
    dl: SqliteDataLayer,
) -> None:
    """No replica means no role in it: False, never a raise (ADR-0153)."""
    assert has_role(MANAGER_ID, CASE_ID, CVDRole.CASE_MANAGER, dl) is False


@pytest.mark.spec("CM-02-011")
def test_a_role_changed_mid_case_is_read_fresh(
    seeded: SqliteDataLayer,
) -> None:
    """The roster is read per call, so a granted role answers at once.

    A role belongs to an ``(actor, case)`` pair and changes while the case
    runs (ADR-0153), so the answer may not be cached from an earlier read.
    """
    assert has_role(VENDOR_ID, CASE_ID, CVDRole.COORDINATOR, seeded) is False

    vendor = seeded.read(f"{CASE_ID}/participants/vendor")
    assert isinstance(vendor, CaseParticipant)
    vendor.add_role(CVDRole.COORDINATOR)
    seeded.save(vendor)

    assert has_role(VENDOR_ID, CASE_ID, CVDRole.COORDINATOR, seeded) is True

    vendor = seeded.read(f"{CASE_ID}/participants/vendor")
    assert isinstance(vendor, CaseParticipant)
    vendor.remove_role(CVDRole.COORDINATOR)
    seeded.save(vendor)

    assert has_role(VENDOR_ID, CASE_ID, CVDRole.COORDINATOR, seeded) is False


@pytest.mark.spec("CM-02-011")
def test_the_case_manager_role_follows_a_delegation_mid_case(
    seeded: SqliteDataLayer,
) -> None:
    """Handing the CASE_MANAGER role over changes the answer at once.

    The delegation sequence, as the resolver sees it: while the first holder
    still holds the role it is the authority, and only once the role moves
    does the new holder answer ``True`` (CM-33, ARCH-24-001).
    """
    manager = seeded.read(f"{CASE_ID}/participants/manager")
    vendor = seeded.read(f"{CASE_ID}/participants/vendor")
    assert isinstance(manager, CaseParticipant)
    assert isinstance(vendor, CaseParticipant)

    manager.remove_role(CVDRole.CASE_MANAGER)
    seeded.save(manager)
    vendor.add_role(CVDRole.CASE_MANAGER)
    seeded.save(vendor)

    assert has_role(VENDOR_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is True
    assert has_role(MANAGER_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is False


@pytest.mark.spec("OID-01-007")
def test_an_unnormalised_actor_id_names_no_participant(
    seeded: SqliteDataLayer,
) -> None:
    """An id is compared exactly, as every other role check compares it.

    Ids are normalised where they are extracted (OID-01-006, OID-01-007), so
    one carrying a trailing slash is an upstream defect; absorbing it here
    would make this predicate more lenient than the ``CheckIsCaseManagerNode``
    gates it has to agree with.
    """
    assert (
        has_role(f"{MANAGER_ID}/", CASE_ID, CVDRole.CASE_MANAGER, seeded)
        is False
    )
    assert has_role(f"{VENDOR_ID}/", CASE_ID, CVDRole.VENDOR, seeded) is False


@pytest.mark.spec("CM-26-001")
def test_role_stacking_is_a_union(seeded: SqliteDataLayer) -> None:
    """A participant holding several roles holds each of them."""
    manager = seeded.read(f"{CASE_ID}/participants/manager")
    assert isinstance(manager, CaseParticipant)
    manager.add_role(CVDRole.COORDINATOR)
    seeded.save(manager)

    assert has_role(MANAGER_ID, CASE_ID, CVDRole.CASE_MANAGER, seeded) is True
    assert has_role(MANAGER_ID, CASE_ID, CVDRole.COORDINATOR, seeded) is True
    assert has_role(MANAGER_ID, CASE_ID, CVDRole.VENDOR, seeded) is False


@pytest.mark.spec("ARCH-24-001")
@pytest.mark.spec("ARCH-24-006")
@pytest.mark.spec("ARCH-24-007")
def test_authority_agrees_with_the_single_resolver(
    seeded: SqliteDataLayer,
) -> None:
    """The CASE_MANAGER answer is the resolver's, on a two-manager roster.

    Authority has one answer per case, so the predicate must not derive a
    second one.  A roster that records the role on two participants — the
    window a role delegation opens (CM-33) — is where a second
    implementation disagrees: a roster scan reports ``True`` for *both*
    holders while :func:`resolve_case_manager_id`, and so every
    ``CheckIsCaseManagerNode`` in a tree, names only the first in roster
    order.  A tree admitted on one answer and gated on the other reports
    ``APPLIED`` with every gated effect skipped (HP-01-005), which is the
    defect ADR-0153 closes.

    The second record has to be **on the roster** for the divergence to
    exist: :func:`iter_case_participants` walks
    ``actor_participant_index`` and ``case_participants``, so a record that
    is only saved to the store is invisible to both implementations and the
    test passes whether the predicate delegates or not.  It is attributed to
    a third actor because ``add_participant`` refuses a second record for an
    actor the index already maps (ARCH-24-007).
    """
    second = _participant("second-manager", SECOND_ID, CVDRole.CASE_MANAGER)
    case = seeded.read_case(CASE_ID)
    assert case is not None
    case.add_participant(second)
    seeded.create(second)
    seeded.save(case)

    case = seeded.read_case(CASE_ID)
    assert case is not None
    holders = [
        participant.id_
        for participant in iter_case_participants(case, seeded)
        if participant.has_role(CVDRole.CASE_MANAGER)
    ]
    assert len(holders) == 2, (
        "the roster must record the role twice, or the divergence this test"
        f" is about does not exist; found {holders}"
    )

    resolved = resolve_case_manager_id(case, seeded)
    assert resolved == MANAGER_ID, (
        "the resolver names the first in roster order"
    )
    for actor_id in (MANAGER_ID, SECOND_ID, VENDOR_ID, STRANGER_ID):
        assert has_role(actor_id, CASE_ID, CVDRole.CASE_MANAGER, seeded) is (
            resolved == actor_id
        ), actor_id

    # Every other role is still answered from the roster, by union.
    assert has_role(VENDOR_ID, CASE_ID, CVDRole.VENDOR, seeded) is True
