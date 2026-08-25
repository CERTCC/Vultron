from typing import Any, Dict, cast
import itertools

import pytest

from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import (
    SEMANTIC_REGISTRY,
    find_matching_semantics,
)
from vultron.wire.as2.extractor import (
    ActivityPattern,
)
from vultron.wire.as2.factories import (
    accept_case_participant_role_activity,
    announce_vulnerability_case_activity,
    offer_case_ownership_transfer_activity,
    offer_case_participant_role_activity,
    reject_case_participant_role_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
    VulnerabilityCaseStub,
)


@pytest.mark.spec("SE-03-001")
@pytest.mark.spec("VAM-01-001")
def test_all_message_semantics_have_activity_patterns():
    """Ensure every non-UNKNOWN* MessageSemantics member has a pattern in SEMANTIC_REGISTRY."""
    no_pattern_sentinels = {
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }
    missing = [
        e.semantics
        for e in SEMANTIC_REGISTRY
        if e.semantics not in no_pattern_sentinels and e.pattern is None
    ]
    assert not missing, f"Missing activity patterns for semantics: {missing}"


def _pattern_dump(pattern: Any) -> Dict[str, Any]:
    """
    Return a top-level dict representation of the given pattern.

    Accepts either a class (callable) or an instance and prefers model_dump()/dict().
    """
    try:
        obj = (
            pattern()
            if callable(pattern) and not hasattr(pattern, "model_dump")
            else pattern
        )
    except Exception:
        obj = pattern

    if hasattr(obj, "model_dump"):
        dumped = cast(Any, obj).model_dump(exclude_none=True)
    elif hasattr(obj, "dict"):
        dumped = cast(Any, obj).dict(exclude_none=True)
    else:
        raise TypeError(
            f"Pattern {pattern!r} does not expose model_dump() or dict()"
        )

    if not isinstance(dumped, dict):
        raise TypeError(
            f"Dump of pattern {pattern!r} is not a dict (got {type(dumped)})"
        )

    return dumped


def _elem_matches(a: Any, b: Any) -> bool:
    """Return True if element 'a' can be considered matched by element 'b' (b is at least as specific)."""
    # dicts: all keys in a must be present in b and values must match recursively
    if isinstance(a, dict) and isinstance(b, dict):
        return _is_subset(a, b)
    # lists: every element in a must have a matching element in b
    if isinstance(a, list) and isinstance(b, list):
        for item_a in a:
            if not any(_elem_matches(item_a, item_b) for item_b in b):
                return False
        return True
    # scalars: require equality (conservative)
    return bool(a == b)


def _is_subset(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """
    Return True if dict 'a' is a top-level subset of dict 'b', comparing nested dicts/lists recursively.
    Only checks keys present in 'a' (assumes exclude_none was used).
    """
    keys_a = set(a.keys())
    keys_b = set(b.keys())
    if not keys_a.issubset(keys_b):
        return False

    for k in keys_a:
        val_a = a[k]
        val_b = b[k]
        if not _elem_matches(val_a, val_b):
            return False
    return True


def _registry_order_map() -> dict[int, int]:
    """Map each pattern object id to its index in SEMANTIC_REGISTRY."""
    return {
        id(entry.pattern): idx
        for idx, entry in enumerate(SEMANTIC_REGISTRY)
        if entry.pattern is not None
    }


def _subset_safe(
    dump_a: dict,
    dump_b: dict,
    idx_a: int,
    idx_b: int,
) -> bool:
    """Return True if any subset relationship between dump_a / dump_b is safe.

    Safe means the more-specific pattern (superset of constraints) appears
    first in the registry, so the first-match-wins algorithm dispatches
    correctly.  Ambiguous (equal) patterns are never safe.
    """
    a_in_b = _is_subset(dump_a, dump_b)  # a less specific than b
    b_in_a = _is_subset(dump_b, dump_a)  # b less specific than a
    if not (a_in_b or b_in_a):
        return True  # no overlap
    if b_in_a and not a_in_b:
        return idx_a < idx_b  # a more specific; safe if a is first
    if a_in_b and not b_in_a:
        return idx_b < idx_a  # b more specific; safe if b is first
    return False  # equal dumps — always ambiguous


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
def test_non_overlapping_activity_patterns():
    """Verify that no two patterns in the same activity_ group are ambiguous.

    A pair is ambiguous when one dump is a subset of the other AND the
    less-specific pattern appears first in the registry (wrong dispatch order).

    Ordering-based disambiguation is allowed: the more-specific pattern must
    come first.  This mirrors AGENTS.md: "order matters — specific before
    general".
    """
    registry_order = _registry_order_map()

    groups: dict[str, list[ActivityPattern]] = {}
    for entry in SEMANTIC_REGISTRY:
        if entry.pattern is None:
            continue
        pat = entry.pattern
        groups.setdefault(getattr(pat, "activity_", ""), []).append(pat)

    problems: list = []

    for group_name, group_patterns in groups.items():
        if len(group_patterns) < 2:
            continue
        enriched = []
        for pat in group_patterns:
            try:
                dumped = _pattern_dump(pat)
            except Exception as e:
                problems.append(
                    {
                        "group": group_name,
                        "pattern": repr(pat),
                        "reason": f"dump error: {e}",
                    }
                )
                continue
            dumped = {k: v for k, v in dumped.items() if k != "description"}
            enriched.append((pat, dumped))

        for (pat_a, dump_a), (pat_b, dump_b) in itertools.combinations(
            enriched, 2
        ):
            assert getattr(pat_a, "activity_", None) == getattr(
                pat_b, "activity_", None
            ), f"Patterns {pat_a!r} and {pat_b!r} should share activity_ to be grouped"
            idx_a = registry_order.get(id(pat_a), -1)
            idx_b = registry_order.get(id(pat_b), -1)
            if not _subset_safe(dump_a, dump_b, idx_a, idx_b):
                problems.append(
                    {
                        "group": group_name,
                        "pat_a": repr(pat_a),
                        "pat_b": repr(pat_b),
                        "registry_idx": (idx_a, idx_b),
                        "reason": "ambiguous subset: less-specific precedes more-specific",
                    }
                )

    assert not problems, f"Ambiguous activity pattern groups: {problems}"


@pytest.mark.spec("AF-01-003")
def test_offer_case_ownership_transfer_rejects_string_object():
    """OfferCaseOwnershipTransferActivity must have an inline as_VulnerabilityCase,
    not a bare string URI as object_.

    Sending a string URI causes pattern-matching ambiguity: both
    OFFER_CASE_OWNERSHIP_TRANSFER and SUBMIT_REPORT are Offer activities, and
    the conservative string-passthrough in ActivityPattern._match_field makes
    both patterns match when the object is opaque.  Enforcing the inline object
    at the model level eliminates the ambiguity at its source.
    """
    with pytest.raises(VultronActivityConstructionError):
        offer_case_ownership_transfer_activity(
            "urn:uuid:some-case-id",  # type: ignore[arg-type]  # intentional invalid type — must be rejected by Pydantic
            actor="https://example.org/vendor",
        )


@pytest.mark.spec("VAM-04-007")
@pytest.mark.spec("SE-02-001")
def test_offer_case_ownership_transfer_with_inline_case_dispatches_correctly():
    """An OfferCaseOwnershipTransferActivity with a full inline as_VulnerabilityCase
    must be classified as OFFER_CASE_OWNERSHIP_TRANSFER, not SUBMIT_REPORT."""
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/urn:uuid:test-case",
        name="TEST-001",
    )
    offer = offer_case_ownership_transfer_activity(
        case,
        actor="https://example.org/vendor",
    )
    result = find_matching_semantics(offer)
    assert result == MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER


@pytest.mark.spec("SE-04-002")
@pytest.mark.spec("VAM-01-009")
def test_accept_with_bare_string_object_returns_unresolvable():
    """Accept with a bare string object_ (unrehydrated ref) must return
    UNKNOWN_UNRESOLVABLE_OBJECT, not UNKNOWN, because Accept is a registered
    activity type and the failure is due to an unresolvable URI.

    DR-14: find_matching_semantics() distinguishes "no pattern match for a
    known type with bare-string object_" from "genuinely unknown activity type".
    """
    accept = as_Accept(
        actor="https://example.org/coordinator",
        object_="urn:uuid:some-offer-id",  # bare string — not rehydrated
    )
    result = find_matching_semantics(accept)
    assert result == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT


@pytest.mark.spec("SE-02-003")
@pytest.mark.spec("VAM-01-007")
def test_unknown_activity_type_with_bare_string_object_returns_unknown():
    """An activity type with no registered patterns returns UNKNOWN (not
    UNKNOWN_UNRESOLVABLE_OBJECT) even when object_ is a bare string.

    DR-14: The unresolvable-object heuristic only fires for *known* activity
    types (those with at least one registered pattern).
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Undo,
    )

    # as_Undo has no registered Vultron patterns; a bare-string object_ should
    # return UNKNOWN, not UNKNOWN_UNRESOLVABLE_OBJECT.
    activity = as_Undo(
        actor="https://example.org/alice",
        object_="urn:uuid:some-object",
    )
    result = find_matching_semantics(activity)
    assert result == MessageSemantics.UNKNOWN


# ---------------------------------------------------------------------------
# DR-07 — Actor subtype-aware pattern matching for InviteActorToCasePattern
# ---------------------------------------------------------------------------


CASE_URI = "https://example.org/cases/case1"
ACTOR_URI = "https://example.org/actors/alice"
OWNER_URI = "https://example.org/actors/owner"


def _make_case() -> VulnerabilityCaseStub:
    return VulnerabilityCaseStub(id_=CASE_URI)


@pytest.mark.parametrize(
    "actor_obj",
    [
        as_Actor(id_=ACTOR_URI),
        as_Person(id_=ACTOR_URI),
        as_Organization(id_=ACTOR_URI),
        as_Service(id_=ACTOR_URI),
    ],
    ids=["base-Actor", "Person", "Organization", "Service"],
)
@pytest.mark.spec("SE-01-004")
@pytest.mark.spec("VAM-04-004")
def test_invite_actor_to_case_matches_all_actor_subtypes(actor_obj):
    """InviteActorToCasePattern must match Invite(actor_subtype, target=Case).

    DR-07: _match_field() must be subtype-aware for AOtype.ACTOR so that
    Person, Organization, and Service (the real actor subtypes used in
    production) are correctly identified as INVITE_ACTOR_TO_CASE.
    """
    invite = rm_invite_to_case_activity(
        actor_obj,
        target=_make_case(),
        actor=OWNER_URI,
        id_="https://example.org/invitations/1",
    )
    result = find_matching_semantics(invite)
    assert result == MessageSemantics.INVITE_ACTOR_TO_CASE, (
        f"Expected INVITE_ACTOR_TO_CASE for Invite({type(actor_obj).__name__}), "
        f"got {result}"
    )


@pytest.mark.parametrize(
    "actor_obj",
    [
        as_Actor(id_=ACTOR_URI),
        as_Person(id_=ACTOR_URI),
        as_Organization(id_=ACTOR_URI),
        as_Service(id_=ACTOR_URI),
    ],
    ids=["base-Actor", "Person", "Organization", "Service"],
)
@pytest.mark.spec("SE-01-004")
@pytest.mark.spec("VAM-04-005")
def test_accept_invite_actor_to_case_matches_all_actor_subtypes(actor_obj):
    """AcceptInviteActorToCasePattern must match Accept(Invite(actor_subtype, target=Case)).

    The nested-pattern check propagates actor subtype-awareness through the
    AcceptInviteActorToCasePattern → InviteActorToCasePattern chain.
    """
    invite = rm_invite_to_case_activity(
        actor_obj,
        target=_make_case(),
        actor=OWNER_URI,
        id_="https://example.org/invitations/1",
    )
    accept = rm_accept_invite_to_case_activity(
        invite,
        actor=ACTOR_URI,
    )
    result = find_matching_semantics(accept)
    assert result == MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE, (
        f"Expected ACCEPT_INVITE_ACTOR_TO_CASE for Accept(Invite({type(actor_obj).__name__})), "
        f"got {result}"
    )


@pytest.mark.spec("SE-01-004")
def test_invite_actor_to_case_without_actor_object_does_not_match():
    """Invite(Note, target=Case) must NOT match INVITE_ACTOR_TO_CASE.

    Enforces the object_ discriminator added by DR-07: a non-Actor object
    must not be accepted as an actor-invite pattern match.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Invite,
    )
    from vultron.wire.as2.vocab.base.objects.base import as_Object

    invite_with_non_actor = as_Invite(
        actor=OWNER_URI,
        object_=as_Object(id_="https://example.org/notes/1"),
        target=_make_case(),
    )
    result = find_matching_semantics(invite_with_non_actor)
    assert result != MessageSemantics.INVITE_ACTOR_TO_CASE


@pytest.mark.spec("SE-02-001")
def test_announce_vulnerability_case_pattern_matches():
    """AnnounceVulnerabilityCasePattern must match Announce(as_VulnerabilityCase).

    DR-10: the pattern must be registered so incoming AnnounceVulnerabilityCase
    activities are routed to AnnounceVulnerabilityCaseReceivedUseCase.
    """
    case = as_VulnerabilityCase(
        id_="https://example.org/cases/case-pattern-001", name="Pattern Test"
    )
    announce = announce_vulnerability_case_activity(
        case,
        actor="https://example.org/actors/owner",
    )
    result = find_matching_semantics(announce)
    assert (
        result == MessageSemantics.ANNOUNCE_VULNERABILITY_CASE
    ), f"Expected ANNOUNCE_VULNERABILITY_CASE, got {result}"


@pytest.mark.spec("VM-07-001")
@pytest.mark.spec("VM-07-002")
def test_vulnerability_case_stub_serialises_minimally():
    """VulnerabilityCaseStub must produce only {id, type} when serialised.

    DR-10 / MV-10-001: the stub is the selective-disclosure object used in
    Invite.target; it must not expose full case details to uninvited parties.
    """
    stub = VulnerabilityCaseStub(id_="https://example.org/cases/case-stub-001")
    dumped = stub.model_dump(by_alias=True, exclude_none=True)
    assert set(dumped.keys()) <= {"id", "type", "@context"}
    assert dumped.get("id") == "https://example.org/cases/case-stub-001"
    assert dumped.get("type") == "VulnerabilityCase"


@pytest.mark.spec("VM-07-001")
def test_vulnerability_case_stub_with_summary():
    """VulnerabilityCaseStub may expose a summary field (MV-10-002)."""
    stub = VulnerabilityCaseStub(
        id_="https://example.org/cases/case-stub-002",
        summary="Heap overflow in libfoo",
    )
    dumped = stub.model_dump(by_alias=True, exclude_none=True)
    assert "summary" in dumped
    assert dumped["summary"] == "Heap overflow in libfoo"


@pytest.mark.spec("CM-17-002")
def test_rm_invite_projects_full_vulnerability_case_to_stub():
    """rm_invite_to_case_activity projects a full as_VulnerabilityCase to a stub.

    DR-10 / MV-10-001: the factory accepts a full as_VulnerabilityCase as target
    for projection (CM-17-002 enrichment path) but the resulting wire activity's
    target is always a VulnerabilityCaseStub — full case details never reach
    uninvited parties on the wire.
    """
    actor = as_Actor(id_="https://example.org/actors/alice")
    full_case = as_VulnerabilityCase(
        id_="https://example.org/cases/c1", name="Full"
    )
    activity = rm_invite_to_case_activity(
        actor,
        target=cast(Any, full_case),
        actor=actor.id_,
    )
    assert isinstance(
        activity.target, VulnerabilityCaseStub
    ), "DR-10: wire activity target must be VulnerabilityCaseStub, not full as_VulnerabilityCase"
    assert activity.target.id_ == full_case.id_


# ---------------------------------------------------------------------------
# CASE_MANAGER role delegation pattern tests (DEMOMA-08-002, DEMOMA-08-003)
# ---------------------------------------------------------------------------

_VENDOR_URI = "https://example.org/actors/vendor"
_CASE_ACTOR_URI = "https://example.org/actors/case-actor"
_CASE_URI = "https://example.org/cases/urn:uuid:test-case-mgr"


def _make_case_manager_case() -> as_VulnerabilityCase:
    return as_VulnerabilityCase(id_=_CASE_URI, name="CASE-001")


@pytest.mark.spec("SE-08-003")
@pytest.mark.spec("VAM-04-007")
def test_offer_case_manager_role_not_confused_with_ownership_transfer():
    """Offer(as_VulnerabilityCase) without a as_CaseParticipant target must be
    classified as OFFER_CASE_OWNERSHIP_TRANSFER, not OFFER_CASE_MANAGER_ROLE.

    The presence of a typed as_CaseParticipant target is the sole discriminator.
    """
    case = _make_case_manager_case()
    offer = offer_case_ownership_transfer_activity(
        case,
        actor=_VENDOR_URI,
    )
    result = find_matching_semantics(offer)
    assert (
        result == MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    ), f"Expected OFFER_CASE_OWNERSHIP_TRANSFER, got {result}"


# ---------------------------------------------------------------------------
# CaseParticipantRole pattern tests (ADR-0039, SE-08-003)
# ---------------------------------------------------------------------------


def _make_target_actor() -> as_Actor:
    return as_Actor(id_=_CASE_ACTOR_URI)


@pytest.mark.spec("SE-08-003")
def test_offer_case_participant_role_dispatches_correctly():
    """Offer(CaseParticipantRole, target=Actor, context=VulnerabilityCase) must
    be classified as OFFER_CASE_PARTICIPANT_ROLE (ADR-0039, SE-08-003).

    The self-describing object type eliminates the target-field ambiguity of
    the deprecated Offer(VulnerabilityCase, target=CaseParticipant) format.
    """
    from vultron.enums.roles import CVDRole

    case = _make_case_manager_case()
    actor = _make_target_actor()
    offer = offer_case_participant_role_activity(
        role=CVDRole.CASE_MANAGER,
        target_actor=actor,
        case=case,
        actor=_VENDOR_URI,
    )
    result = find_matching_semantics(offer)
    assert (
        result == MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE
    ), f"Expected OFFER_CASE_PARTICIPANT_ROLE, got {result}"


@pytest.mark.spec("SE-08-003")
def test_offer_case_participant_role_not_confused_with_ownership_transfer():
    """Offer(CaseParticipantRole) must NOT be classified as
    OFFER_CASE_OWNERSHIP_TRANSFER or OFFER_CASE_MANAGER_ROLE.

    The distinct object type (CASE_PARTICIPANT_ROLE) makes the shape
    unambiguously self-describing. See SE-08-003.
    """
    from vultron.enums.roles import CVDRole

    case = _make_case_manager_case()
    actor = _make_target_actor()
    offer = offer_case_participant_role_activity(
        role=CVDRole.CASE_MANAGER,
        target_actor=actor,
        case=case,
        actor=_VENDOR_URI,
    )
    result = find_matching_semantics(offer)
    assert (
        result != MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
    ), "OFFER_CASE_PARTICIPANT_ROLE misclassified as OFFER_CASE_OWNERSHIP_TRANSFER"


@pytest.mark.spec("SE-08-003")
def test_offer_case_participant_role_for_coordinator():
    """offer_case_participant_role_activity accepts any CVDRole, not just CASE_MANAGER."""
    from vultron.enums.roles import CVDRole

    case = _make_case_manager_case()
    actor = _make_target_actor()
    offer = offer_case_participant_role_activity(
        role=CVDRole.COORDINATOR,
        target_actor=actor,
        case=case,
        actor=_VENDOR_URI,
    )
    result = find_matching_semantics(offer)
    assert result == MessageSemantics.OFFER_CASE_PARTICIPANT_ROLE


# ---------------------------------------------------------------------------
# CaseProposal pattern tests (CP-03-001 through CP-03-004, CP-07-001)
# ---------------------------------------------------------------------------

_CASE_ACTOR_URI = "https://example.org/case-actors/alpha"


def _make_case_proposal():
    """Return a minimal as_CaseProposal for pattern-matching tests."""
    from vultron.wire.as2.vocab.examples._base import gen_report
    from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

    return as_CaseProposal(
        attributed_to=_VENDOR_URI,
        object_=gen_report(),
        target=_CASE_ACTOR_URI,
    )


@pytest.mark.spec("SE-02-001")
def test_create_case_proposal_dispatches_correctly():
    """Create(as_CaseProposal) must be classified as CREATE_CASE_PROPOSAL.

    CP-03-001, CP-07-001.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    proposal = _make_case_proposal()
    activity = as_Create(
        actor=_VENDOR_URI,
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    result = find_matching_semantics(activity)
    assert (
        result == MessageSemantics.CREATE_CASE_PROPOSAL
    ), f"Expected CREATE_CASE_PROPOSAL, got {result}"


@pytest.mark.spec("SE-02-001")
def test_accept_case_proposal_dispatches_correctly():
    """Accept(as_CaseProposal) must be classified as ACCEPT_CASE_PROPOSAL.

    CP-03-002, CP-07-001.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Accept,
    )

    proposal = _make_case_proposal()
    activity = as_Accept(
        actor=_CASE_ACTOR_URI,
        object_=proposal,
        to=[_VENDOR_URI],
    )
    result = find_matching_semantics(activity)
    assert (
        result == MessageSemantics.ACCEPT_CASE_PROPOSAL
    ), f"Expected ACCEPT_CASE_PROPOSAL, got {result}"


@pytest.mark.spec("SE-02-001")
def test_reject_case_proposal_dispatches_correctly():
    """Reject(as_CaseProposal) must be classified as REJECT_CASE_PROPOSAL.

    CP-03-003, CP-07-001.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Reject,
    )

    proposal = _make_case_proposal()
    activity = as_Reject(
        actor=_CASE_ACTOR_URI,
        object_=proposal,
        to=[_VENDOR_URI],
    )
    result = find_matching_semantics(activity)
    assert (
        result == MessageSemantics.REJECT_CASE_PROPOSAL
    ), f"Expected REJECT_CASE_PROPOSAL, got {result}"


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
def test_create_case_proposal_not_confused_with_create_case():
    """Create(as_CaseProposal) must NOT match CREATE_CASE.

    Ordering guard: CP-03-004 — CaseProposal patterns must not be shadowed
    by more general Create/Accept/Reject patterns.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    proposal = _make_case_proposal()
    activity = as_Create(
        actor=_VENDOR_URI,
        object_=proposal,
        to=[_CASE_ACTOR_URI],
    )
    result = find_matching_semantics(activity)
    assert (
        result != MessageSemantics.CREATE_CASE
    ), "CREATE_CASE_PROPOSAL must not be misrouted as CREATE_CASE"


@pytest.mark.spec("SE-03-002")
@pytest.mark.spec("VAM-01-003")
def test_accept_case_proposal_not_confused_with_other_accept_semantics():
    """Accept(as_CaseProposal) must NOT match any non-CaseProposal semantic.

    CP-03-004 ordering invariant.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Accept,
    )

    proposal = _make_case_proposal()
    activity = as_Accept(
        actor=_CASE_ACTOR_URI,
        object_=proposal,
        to=[_VENDOR_URI],
    )
    result = find_matching_semantics(activity)
    assert result not in {
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.UNKNOWN,
    }, f"Accept(CaseProposal) misrouted as {result}"


@pytest.mark.spec("VAM-01-009")
@pytest.mark.spec("SE-04-002")
def test_case_proposal_with_string_object_returns_unresolvable():
    """Accept with a bare CaseProposal URI returns UNKNOWN_UNRESOLVABLE_OBJECT.

    After rehydration, if the object_ is still a string the extractor cannot
    match a specific pattern; it should return UNKNOWN_UNRESOLVABLE_OBJECT.
    """
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Accept,
    )

    activity = as_Accept(
        actor=_CASE_ACTOR_URI,
        object_="https://example.org/proposals/xyz",
        to=[_VENDOR_URI],
    )
    result = find_matching_semantics(activity)
    assert (
        result == MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT
    ), f"Expected UNKNOWN_UNRESOLVABLE_OBJECT for bare URI, got {result}"


# ---------------------------------------------------------------------------
# AC-1: strict target_ field — bare string URIs must be rejected (ADR-0039)
# ---------------------------------------------------------------------------


@pytest.mark.spec("VAM-01-006")
@pytest.mark.spec("SE-08-004")
def test_strict_target_rejects_bare_string_uri():
    """ActivityPattern with strict=True must not match when target is a bare string URI.

    AC-1: The target_ field pair must use self.strict (not hardcoded False) so
    that bare URI strings do not satisfy a typed target_ constraint when the
    pattern is in strict mode.
    """
    from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
    from vultron.core.models.enums import VultronObjectType as VOtype
    from vultron.wire.as2.enums import as_ObjectType as AOtype
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Offer,
    )

    strict_pattern = ActivityPattern(
        activity_=TAtype.OFFER,
        object_=VOtype.VULNERABILITY_CASE,
        target_=AOtype.ACTOR,
        strict=True,
    )

    case = as_VulnerabilityCase(
        id_="https://example.org/cases/strict-target-test", name="T-001"
    )

    # Bare string target must NOT match when strict=True (AC-1 fix)
    activity_string_target = as_Offer(
        actor=_VENDOR_URI,
        object_=case,
        target="https://example.org/actors/alice",
    )
    assert not strict_pattern.match(
        activity_string_target
    ), "strict=True pattern must not match when target is a bare string URI"


@pytest.mark.spec("VAM-01-006")
@pytest.mark.spec("SE-08-004")
def test_strict_target_matches_typed_actor():
    """ActivityPattern with strict=True must match when target is a typed Actor.

    Complement of test_strict_target_rejects_bare_string_uri — confirms that
    the fix only blocks bare strings, not properly typed target values.
    """
    from vultron.wire.as2.enums import as_TransitiveActivityType as TAtype
    from vultron.core.models.enums import VultronObjectType as VOtype
    from vultron.wire.as2.enums import as_ObjectType as AOtype
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Offer,
    )

    strict_pattern = ActivityPattern(
        activity_=TAtype.OFFER,
        object_=VOtype.VULNERABILITY_CASE,
        target_=AOtype.ACTOR,
        strict=True,
    )

    case = as_VulnerabilityCase(
        id_="https://example.org/cases/strict-target-test", name="T-001"
    )
    actor = as_Actor(id_="https://example.org/actors/alice")

    activity_typed_target = as_Offer(
        actor=_VENDOR_URI,
        object_=case,
        target=actor,
    )
    assert strict_pattern.match(
        activity_typed_target
    ), "strict=True pattern must match when target is a typed Actor object"


# ---------------------------------------------------------------------------
# AC-2/AC-3/AC-4: Accept/Reject CaseParticipantRole dispatch (ADR-0039)
# ---------------------------------------------------------------------------


def _make_role_offer():
    """Build a valid Offer(CaseParticipantRole, target=Actor, context=Case) activity."""
    from vultron.enums.roles import CVDRole

    case = _make_case_manager_case()
    actor = _make_target_actor()
    return offer_case_participant_role_activity(
        role=CVDRole.CASE_MANAGER,
        target_actor=actor,
        case=case,
        actor=_VENDOR_URI,
    )


@pytest.mark.spec("SE-08-003")
def test_accept_case_participant_role_dispatches_correctly():
    """Accept(Offer(CaseParticipantRole, ...)) must be classified as
    ACCEPT_CASE_PARTICIPANT_ROLE (ADR-0039, SE-08-003).

    AC-2/AC-3/AC-4: the Accept pattern, registry entry, and MessageSemantics
    enum value must all be wired up so the semantic extractor routes correctly.
    """
    offer = _make_role_offer()
    accept = accept_case_participant_role_activity(
        offer, actor=_CASE_ACTOR_URI
    )
    result = find_matching_semantics(accept)
    assert (
        result == MessageSemantics.ACCEPT_CASE_PARTICIPANT_ROLE
    ), f"Expected ACCEPT_CASE_PARTICIPANT_ROLE, got {result}"


@pytest.mark.spec("SE-08-003")
def test_reject_case_participant_role_dispatches_correctly():
    """Reject(Offer(CaseParticipantRole, ...)) must be classified as
    REJECT_CASE_PARTICIPANT_ROLE (ADR-0039, SE-08-003).

    AC-2/AC-3/AC-4: the Reject pattern, registry entry, and MessageSemantics
    enum value must all be wired up so the semantic extractor routes correctly.
    """
    offer = _make_role_offer()
    reject = reject_case_participant_role_activity(
        offer, actor=_CASE_ACTOR_URI
    )
    result = find_matching_semantics(reject)
    assert (
        result == MessageSemantics.REJECT_CASE_PARTICIPANT_ROLE
    ), f"Expected REJECT_CASE_PARTICIPANT_ROLE, got {result}"


@pytest.mark.spec("SE-08-003")
@pytest.mark.spec("SE-03-002")
def test_accept_case_participant_role_not_confused_with_other_accepts():
    """Accept(Offer(CaseParticipantRole)) must NOT match any other Accept semantics.

    Ordering guard: the new ACCEPT_CASE_PARTICIPANT_ROLE entry must not be
    shadowed by existing Accept patterns.
    """
    offer = _make_role_offer()
    accept = accept_case_participant_role_activity(
        offer, actor=_CASE_ACTOR_URI
    )
    result = find_matching_semantics(accept)
    assert result not in {
        MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER,
        MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE,
        MessageSemantics.ACCEPT_OFFER_CASE_PARTICIPANT,
        MessageSemantics.UNKNOWN,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT,
    }, f"Accept(Offer(CaseParticipantRole)) misrouted as {result}"
