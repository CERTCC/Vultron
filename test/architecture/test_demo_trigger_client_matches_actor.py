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

"""Architecture invariant: a demo trigger POST names an actor its client hosts.

``post_to_trigger`` keeps only the *bare object ID* of ``actor_id`` and resolves
it against ``client.base_url``, so the pair decides which container answers.
Name an actor a different container hosts and the request does not go to that
actor: either the slug is unknown there and it 404s several hundred lines from
the mistake, or the slug *is* known and ``get_actor_dl`` mints an empty store for
it, so the behaviour runs against the wrong actor's state (#2549).

fvcv-handoff shipped the 404 form of this — the Coordinator's
``invite-actor-to-case`` posted to the vendor container, justified by a comment
claiming it was how the Invite got emitted as the CaseActor.  It is not:
``SvcInviteActorToCaseUseCase._prepare`` resolves the case's CaseActor and emits
as it regardless of which container the trigger arrived on (PCR-08-007).  The
identical pairing sat latent in fccv-handoff, invisible because CI's scenario
selection never ran it.

Two layers guard this now.  ``_assert_client_hosts_actor`` raises at the call
site when the two URIs disagree on authority — but only a container run has real
URIs to compare.  This test reads the scenario sources instead, so it is not
marked ``integration``, needs no Docker, and fails on the naming mismatch in the
default unit tier.

Issue: #2484
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

#: Suffix marking a scenario-local container client (``vendor_client``).
_CLIENT_SUFFIX = "_client"

#: Infix in an actor variable naming the container it was fetched from
#: (``vendor2_in_vendor2`` — the Vendor2 actor as Vendor2's own container holds
#: it).  Only the part *before* it identifies the actor.
_IN_INFIX = "_in_"

#: Lower bound on call sites the detector must see.  A source-reading ratchet
#: that matches nothing reports success, which is worse than not existing; the
#: scenarios carry far more than this, so the bound only catches a convention
#: change that blinds the detector wholesale.
_MIN_CHECKED_CALLS = 20


def _container_of_client(node: ast.expr) -> str | None:
    """Return the container token a ``client=`` argument names, or None.

    ``vendor2_client`` → ``vendor2``.  Anything not a bare ``*_client`` name is
    a generic parameter forwarded from a helper, which this test cannot resolve
    and deliberately does not guess at.
    """
    if not isinstance(node, ast.Name):
        return None
    if not node.id.endswith(_CLIENT_SUFFIX):
        return None
    return node.id[: -len(_CLIENT_SUFFIX)] or None


def _container_of_actor(node: ast.expr) -> str | None:
    """Return the container token an ``actor_id=`` argument names, or None.

    ``coordinator_in_coordinator.id_`` → ``coordinator``; ``vendor2.id_`` →
    ``vendor2``.  An actor lives on its own container, so the actor token *is*
    the container token — which is the whole reason a mismatch with the client
    is a defect rather than a style choice.
    """
    if not isinstance(node, ast.Attribute) or node.attr != "id_":
        return None
    base = node.value
    if not isinstance(base, ast.Name):
        return None
    name = base.id
    if _IN_INFIX in name:
        name = name.split(_IN_INFIX, 1)[0]
    return name or None


def _mismatched_trigger_posts(tree: ast.AST) -> list[tuple[int, str, str]]:
    """Return ``(lineno, client, actor)`` for each cross-container trigger POST.

    Only pairs where *both* sides resolve to a token are judged; an unresolvable
    side means the call came through a helper whose caller owns the pairing.
    """
    mismatches: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )
        if callee != "post_to_trigger":
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        client_arg, actor_arg = kwargs.get("client"), kwargs.get("actor_id")
        if client_arg is None or actor_arg is None:
            continue
        client = _container_of_client(client_arg)
        actor = _container_of_actor(actor_arg)
        if client is None or actor is None:
            continue
        if client != actor:
            mismatches.append((node.lineno, client, actor))
    return mismatches


def _checked_trigger_posts(tree: ast.AST) -> int:
    """Count trigger POSTs whose client/actor pair this detector can judge."""
    checked = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )
        if callee != "post_to_trigger":
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        client_arg, actor_arg = kwargs.get("client"), kwargs.get("actor_id")
        if client_arg is None or actor_arg is None:
            continue
        if (
            _container_of_client(client_arg) is not None
            and _container_of_actor(actor_arg) is not None
        ):
            checked += 1
    return checked


_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.files_mentioning(
        "post_to_trigger", under=_SCENARIO_DIR
    )
    if path.name != "__init__.py"
}


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_trigger_posts_go_to_the_named_actors_container(scenario: Path):
    """Every scenario ``post_to_trigger`` must pair a client with its own actor."""
    mismatches = _mismatched_trigger_posts(_SCENARIO_TREES[scenario])
    detail = "\n".join(
        f"  line {lineno}: client={client}_client but actor_id names {actor}"
        for lineno, client, actor in mismatches
    )
    assert not mismatches, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} posts triggers to a"
        f" container that does not host the named actor:\n{detail}\n"
        "The trigger URL is the actor's bare ID resolved against the client's"
        " base_url, so this addresses the wrong actor (404, or an empty store"
        " minted for a foreign slug). Post to the named actor's own container;"
        " emitting as the CaseActor is already handled by"
        " SvcInviteActorToCaseUseCase._prepare (PCR-08-007)."
    )


def test_the_detector_sees_the_scenarios_it_claims_to_guard():
    """Guard the guard: a rename must not silently reduce this to a no-op."""
    total = sum(_checked_trigger_posts(t) for t in _SCENARIO_TREES.values())
    assert total >= _MIN_CHECKED_CALLS, (
        f"only {total} scenario post_to_trigger call(s) had a resolvable"
        f" client/actor pair, expected at least {_MIN_CHECKED_CALLS} — the"
        " naming convention this ratchet reads has probably changed"
    )


def test_the_check_can_actually_fail():
    """The detector must flag the exact pairing fvcv-handoff shipped."""
    sample = _corpus.parse_inline(
        "post_to_trigger(\n"
        "    client=vendor_client,\n"
        "    actor_id=coordinator_in_coordinator.id_,\n"
        "    behavior='invite-actor-to-case',\n"
        "    body={},\n"
        ")\n"
    )
    assert _mismatched_trigger_posts(sample) == [(1, "vendor", "coordinator")]


def test_matching_pairs_are_not_flagged():
    """Both spellings of a correct pairing must pass."""
    sample = _corpus.parse_inline(
        "post_to_trigger(client=vendor2_client, actor_id=vendor2.id_, "
        "behavior='b', body={})\n"
        "post_to_trigger(client=vendor2_client, "
        "actor_id=vendor2_in_vendor2.id_, behavior='b', body={})\n"
    )
    assert _mismatched_trigger_posts(sample) == []


def test_generic_helper_parameters_are_left_alone():
    """A forwarded ``client``/``actor`` pair is the caller's business, not ours."""
    sample = _corpus.parse_inline(
        "post_to_trigger(client=client, actor_id=actor.id_, behavior='b', "
        "body={})\n"
    )
    assert _mismatched_trigger_posts(sample) == []


# ---------------------------------------------------------------------------
# The runtime half of the guard: what happens on a pairing the source-reading
# ratchet above cannot see, because it arrived through a helper's parameters.
# ---------------------------------------------------------------------------


class _RecordingClient:
    """Minimal stand-in for ``DataLayerClient``: a base URL and a ``post``."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.posted: list[str] = []

    def post(self, path: str, json: dict) -> dict:
        self.posted.append(path)
        return {}


def test_post_to_trigger_rejects_an_actor_the_container_does_not_host():
    """The fvcv-handoff pairing, refused before it can become an HTTP 404."""
    from vultron.demo.utils import post_to_trigger

    client = _RecordingClient("http://vendor:7999/api/v2")

    with pytest.raises(ValueError, match="not.* hosted by"):
        post_to_trigger(
            client=client,  # type: ignore[arg-type]
            actor_id="http://coordinator:7999/api/v2/actors/coordinator",
            behavior="invite-actor-to-case",
            body={},
        )
    assert client.posted == [], "the request must not be sent at all"


def test_post_to_trigger_accepts_the_actors_own_container():
    """Same actor, its own container: the path keeps the bare object ID."""
    from vultron.demo.utils import post_to_trigger

    client = _RecordingClient("http://coordinator:7999/api/v2")

    post_to_trigger(
        client=client,  # type: ignore[arg-type]
        actor_id="http://coordinator:7999/api/v2/actors/coordinator",
        behavior="invite-actor-to-case",
        body={},
    )
    assert client.posted == [
        "/actors/coordinator/trigger/invite-actor-to-case"
    ]


def test_post_to_trigger_ignores_a_client_with_no_real_base_url():
    """``MagicMock`` clients cannot mis-address anything, so they are exempt.

    Most of the demo unit suite substitutes a mock client; a guard that treated
    a mock's ``base_url`` repr as a container would fail every one of them while
    catching no real defect.
    """
    from unittest.mock import MagicMock

    from vultron.demo.utils import post_to_trigger

    client = MagicMock()
    post_to_trigger(
        client=client,
        actor_id="http://coordinator:7999/api/v2/actors/coordinator",
        behavior="validate-report",
        body={},
    )
    client.post.assert_called_once()
