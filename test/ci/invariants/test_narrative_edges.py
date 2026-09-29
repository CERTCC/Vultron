"""Structural checks over the ``causal_edges:`` blocks of the scenario narratives.

The scenario narrative pages under ``docs/topics/scenarios/`` carry a
machine-readable ``causal_edges:`` list (DEMOMA-22-004) that invariant 16 of
the case-ledger harness checks against a real demo ledger (DEMOMA-22-005).
That check needs demo artifacts, so it runs only in CI.  The tests here run
in the regular unit suite and catch two authoring slips the ledger check
cannot, or cannot until CI runs:

- an edge list that omits an ordering constraint the scenario depends on, so
  that a mis-ordered ledger would pass (ISSUE-2754);
- an invitee's response attributed to the actor who sent the invitation
  (ISSUE-2753).  The ledger check reads ``consequent_actor`` only for its
  failure diagnostics, so no run would ever have flagged it.

They use synthetic replica data and the committed narrative pages; no
``devlogs/`` directory is needed.  They are deliberately NOT tagged
``@pytest.mark.case_ledger_invariants``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from test.ci.invariants.common import (
    _REPO_ROOT,
    check_causal_edges,
    load_narrative_edges,
)

_SCENARIOS_DIR = _REPO_ROOT / "docs" / "topics" / "scenarios"

_INVITE = "invite_actor_to_case"
_INVITE_RESPONSES = frozenset(
    {"accept_invite_actor_to_case", "reject_invite_actor_to_case"}
)
_OWNERSHIP_ACCEPTED = "accept_case_ownership_transfer"


def _narrative_pages() -> list[Path]:
    """Every scenario narrative page (the index is a routing page, not a scenario)."""
    pages = sorted(
        p for p in _SCENARIOS_DIR.glob("*.md") if p.name != "index.md"
    )
    assert pages, f"no scenario narratives found under {_SCENARIOS_DIR}"
    return pages


def _handoff_pages() -> list[Path]:
    """The narratives whose flow includes an ownership handoff."""
    pages = [p for p in _narrative_pages() if p.stem.endswith("-handoff")]
    assert pages, "no *-handoff narrative found"
    return pages


def _rel(page: Path) -> str:
    return str(page.relative_to(_REPO_ROOT))


def _ledger(*event_types: str) -> dict[str, list[dict]]:
    """A synthetic authoritative log with the given event types in order."""
    return {
        "case-actor": [
            {"log_index": i, "eventType": evt}
            for i, evt in enumerate(event_types)
        ]
    }


#: The handoff flow with every step in its causal place.  The two invites are
#: the first owner's invite of the second actor and the new owner's invite of
#: the last vendor; the ownership acceptance sits between them.
_HANDOFF_IN_ORDER = (
    "validate_report",
    "engage_case",
    "add_participant_status_to_participant",
    _INVITE,
    "accept_invite_actor_to_case",
    "offer_case_ownership_transfer",
    _OWNERSHIP_ACCEPTED,
    _INVITE,
    "accept_invite_actor_to_case",
    "add_note_to_case",
    "close_case",
)

#: The same flow with the new owner's invite sent before the ownership
#: acceptance was recorded — the defect the handoff edges must be able to see.
_HANDOFF_INVITE_BEFORE_OWNERSHIP = (
    "validate_report",
    "engage_case",
    "add_participant_status_to_participant",
    _INVITE,
    "accept_invite_actor_to_case",
    "offer_case_ownership_transfer",
    _INVITE,
    _OWNERSHIP_ACCEPTED,
    "accept_invite_actor_to_case",
    "add_note_to_case",
    "close_case",
)


@pytest.mark.parametrize("page", _handoff_pages(), ids=lambda p: p.stem)
def test_handoff_edges_accept_a_correctly_ordered_ledger(page: Path) -> None:
    """The declared handoff edges are satisfiable by the intended flow."""
    edges = load_narrative_edges(_rel(page))
    violations = check_causal_edges(_ledger(*_HANDOFF_IN_ORDER), edges)
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("page", _handoff_pages(), ids=lambda p: p.stem)
def test_handoff_edges_reject_invite_before_ownership_acceptance(
    page: Path,
) -> None:
    """A new owner's invite recorded before the ownership acceptance is caught.

    The handoff scenarios exist to show that the new owner invites the last
    vendor *as owner*.  An edge list that links the second invite only to the
    new owner's own invitation acceptance never asserts that, so a ledger in
    which the invite precedes ``accept_case_ownership_transfer`` passes
    (ISSUE-2754).  Every handoff narrative must declare the edge that makes
    the ordering visible to invariant 16.
    """
    edges = load_narrative_edges(_rel(page))
    violations = check_causal_edges(
        _ledger(*_HANDOFF_INVITE_BEFORE_OWNERSHIP), edges
    )
    assert violations, (
        f"{_rel(page)} declares no edge that orders "
        f"{_OWNERSHIP_ACCEPTED!r} before the new owner's {_INVITE!r}; a "
        "ledger with the invite first passes its causal-edge check"
    )
    assert any(
        _OWNERSHIP_ACCEPTED in v and _INVITE in v for v in violations
    ), "\n".join(violations)


@pytest.mark.parametrize("page", _narrative_pages(), ids=lambda p: p.stem)
def test_invitee_response_edge_is_not_attributed_to_the_inviter(
    page: Path,
) -> None:
    """An accept or reject of an invitation is never attributed to the inviter.

    ``consequent_actor`` names the actor whose act the consequent entry
    records (DEMOMA-22-004).  An invitation is answered by its invitee, so
    the actor on an ``invite_actor_to_case → accept/reject`` edge must differ
    from the actor on the invite edge it answers — the nearest preceding
    ``invite_actor_to_case`` consequent in the list, which is how every
    narrative orders its chain.  ISSUE-2753 attributed the Vendor's rejection
    to the Coordinator who sent the invite; the ledger check reads the label
    only for diagnostics, so nothing else would notice.
    """
    edges = load_narrative_edges(_rel(page))
    inviter: str | None = None
    mismatches: list[str] = []
    for edge in edges:
        consequent = edge.get("consequent")
        actor = edge.get("consequent_actor")
        if consequent == _INVITE:
            inviter = actor
            continue
        if (
            consequent in _INVITE_RESPONSES
            and edge.get("antecedent") == _INVITE
        ):
            assert inviter is not None, (
                f"{_rel(page)}: {consequent!r} edge has no preceding "
                f"{_INVITE!r} edge to answer"
            )
            if actor == inviter:
                mismatches.append(
                    f"{consequent!r} attributed to {actor!r}, who sent the "
                    "invitation it answers"
                )
    assert not mismatches, f"{_rel(page)}:\n" + "\n".join(mismatches)
