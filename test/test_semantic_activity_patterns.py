from typing import Any, Dict, cast
import itertools

import pytest
from pydantic import ValidationError

from vultron.core.models.events import MessageSemantics
from vultron.wire.as2.extractor import (
    ActivityPattern,
    SEMANTICS_ACTIVITY_PATTERNS,
    find_matching_semantics,
)
from vultron.wire.as2.vocab.activities.case import (
    OfferCaseOwnershipTransferActivity,
    RmAcceptInviteToCaseActivity,
    RmInviteToCaseActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Accept
from vultron.wire.as2.vocab.base.objects.actors import (
    as_Actor,
    as_Organization,
    as_Person,
    as_Service,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def test_all_message_semantics_have_activity_patterns():
    """Ensure every MessageSemantics member is present as a key in SEMANTICS_ACTIVITY_PATTERNS."""
    missing = [
        member
        for member in MessageSemantics
        if member not in SEMANTICS_ACTIVITY_PATTERNS
    ]

    # it's okay for MessageSemantics.UNKNOWN to not have a pattern, since it's a catch-all for unmatched semantics
    if MessageSemantics.UNKNOWN in missing:
        missing.remove(MessageSemantics.UNKNOWN)

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


def test_non_overlapping_activity_patterns():
    """
    Group patterns by activity_ and ensure no pattern's dumped structure is a top-level
    subset of another in the same activity_ group (either direction).
    """
    groups: dict[str, list[ActivityPattern]] = {}
    for pat in SEMANTICS_ACTIVITY_PATTERNS.values():
        groups.setdefault(getattr(pat, "activity_", ""), []).append(pat)

    problems = []

    for group_name, group_patterns in groups.items():
        if len(group_patterns) < 2:
            # skip groups with only one pattern since they can't overlap with anything else
            continue

        # Precompute dumps
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
            # ignore description differences
            dumped = {k: v for k, v in dumped.items() if k != "description"}
            enriched.append((pat, dumped))

        # pairwise check (only within group)
        for (pat_a, dump_a), (pat_b, dump_b) in itertools.combinations(
            enriched, 2
        ):
            # sanity: both should share same activity_ to be compared
            assert getattr(pat_a, "activity_", None) == getattr(
                pat_b, "activity_", None
            ), f"Patterns {pat_a!r} and {pat_b!r} should share activity_ to be grouped"

            # If one dump is a subset of the other (or equal) -> potential overlap
            a_in_b = _is_subset(dump_a, dump_b)
            b_in_a = _is_subset(dump_b, dump_a)
            if a_in_b or b_in_a:
                problems.append(
                    {
                        "group": group_name,
                        "pat_a": repr(pat_a),
                        "pat_b": repr(pat_b),
                        "dump_a_keys": sorted(dump_a.keys()),
                        "dump_b_keys": sorted(dump_b.keys()),
                        "reason": "top-level subset"
                        + (
                            " (a subset of b)"
                            if a_in_b
                            else " (b subset of a)"
                        ),
                    }
                )

    assert (
        not problems
    ), f"Problems found in activity pattern groups: {problems}"


def test_offer_case_ownership_transfer_rejects_string_object():
    """OfferCaseOwnershipTransferActivity must have an inline VulnerabilityCase,
    not a bare string URI as object_.

    Sending a string URI causes pattern-matching ambiguity: both
    OFFER_CASE_OWNERSHIP_TRANSFER and SUBMIT_REPORT are Offer activities, and
    the conservative string-passthrough in ActivityPattern._match_field makes
    both patterns match when the object is opaque.  Enforcing the inline object
    at the model level eliminates the ambiguity at its source.
    """
    with pytest.raises(ValidationError):
        OfferCaseOwnershipTransferActivity(
            actor="https://example.org/vendor",
            object_="urn:uuid:some-case-id",  # type: ignore[arg-type]  # intentional invalid type — must be rejected by Pydantic
        )


def test_offer_case_ownership_transfer_with_inline_case_dispatches_correctly():
    """An OfferCaseOwnershipTransferActivity with a full inline VulnerabilityCase
    must be classified as OFFER_CASE_OWNERSHIP_TRANSFER, not SUBMIT_REPORT."""
    case = VulnerabilityCase(
        id_="https://example.org/cases/urn:uuid:test-case",
        name="TEST-001",
    )
    offer = OfferCaseOwnershipTransferActivity(
        actor="https://example.org/vendor",
        object_=case,
    )
    result = find_matching_semantics(offer)
    assert result == MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER


def test_accept_with_bare_string_object_returns_unknown():
    """Accept with a bare string object_ (unrehydrated ref) must not match
    VALIDATE_REPORT or any other semantic requiring a nested-activity object.

    DR-03: _match_field() must check nested ActivityPattern before the
    conservative string-passthrough, so that bare-string refs don't
    accidentally satisfy typed nested-pattern constraints.
    """
    accept = as_Accept(
        actor="https://example.org/coordinator",
        object_="urn:uuid:some-offer-id",  # bare string — not rehydrated
    )
    result = find_matching_semantics(accept)
    assert result == MessageSemantics.UNKNOWN


# ---------------------------------------------------------------------------
# DR-07 — Actor subtype-aware pattern matching for InviteActorToCasePattern
# ---------------------------------------------------------------------------


CASE_URI = "https://example.org/cases/case1"
ACTOR_URI = "https://example.org/actors/alice"
OWNER_URI = "https://example.org/actors/owner"


def _make_case() -> VulnerabilityCase:
    return VulnerabilityCase(id_=CASE_URI, name="TEST-001")


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
def test_invite_actor_to_case_matches_all_actor_subtypes(actor_obj):
    """InviteActorToCasePattern must match Invite(actor_subtype, target=Case).

    DR-07: _match_field() must be subtype-aware for AOtype.ACTOR so that
    Person, Organization, and Service (the real actor subtypes used in
    production) are correctly identified as INVITE_ACTOR_TO_CASE.
    """
    invite = RmInviteToCaseActivity(
        id_="https://example.org/invitations/1",
        actor=OWNER_URI,
        object_=actor_obj,
        target=_make_case(),
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
def test_accept_invite_actor_to_case_matches_all_actor_subtypes(actor_obj):
    """AcceptInviteActorToCasePattern must match Accept(Invite(actor_subtype, target=Case)).

    The nested-pattern check propagates actor subtype-awareness through the
    AcceptInviteActorToCasePattern → InviteActorToCasePattern chain.
    """
    invite = RmInviteToCaseActivity(
        id_="https://example.org/invitations/1",
        actor=OWNER_URI,
        object_=actor_obj,
        target=_make_case(),
    )
    accept = RmAcceptInviteToCaseActivity(
        actor=ACTOR_URI,
        object_=invite,
    )
    result = find_matching_semantics(accept)
    assert result == MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE, (
        f"Expected ACCEPT_INVITE_ACTOR_TO_CASE for Accept(Invite({type(actor_obj).__name__})), "
        f"got {result}"
    )


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
