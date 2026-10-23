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

"""The CaseActor identity is the container's, and carries no case in its URI (#1872)."""

import pytest
from _pytest.monkeypatch import MonkeyPatch

from vultron.core.behaviors.case.case_actor_identity import (
    CASE_ACTOR_SEGMENT,
    case_actor_identity,
)

_BASE = "http://case-actor.test/api/v2"


@pytest.fixture
def configured_base():
    """Configure ``case_actor_service_url`` for the duration of a test."""
    from vultron.config.app import reload_config

    mp = MonkeyPatch()
    try:
        mp.setenv("VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", _BASE)
        reload_config()
        yield _BASE
    finally:
        mp.undo()
        reload_config()


@pytest.mark.spec("CP-04-003")
class TestCaseActorIdentity:
    def test_identity_is_the_container_not_the_case(self, configured_base):
        """One identity per container — no per-case slug (#1872 AC-1)."""
        assert case_actor_identity() == f"{_BASE}/actors/{CASE_ACTOR_SEGMENT}"

    def test_identity_does_not_vary_with_the_case(self, configured_base):
        """Two different reports resolve to the same CaseActor.

        This is the whole point: an actor participates in many cases, and which
        case a message concerns is carried by ``activity.context``. A derived
        per-case id made the identity unresolvable — the sender computed it and
        nobody hosted it, so delivery 404'd permanently.
        """
        assert case_actor_identity() == case_actor_identity()

    def test_explicit_base_overrides_config(self):
        other = "https://other.example/api/v2"
        assert case_actor_identity(other) == f"{other}/actors/case-actor"

    def test_an_identity_passed_in_is_returned_unchanged(self):
        """Idempotent, so a caller holding the identity need not special-case."""
        identity = f"{_BASE}/actors/{CASE_ACTOR_SEGMENT}"
        assert case_actor_identity(identity) == identity

    def test_trailing_slashes_do_not_produce_a_double_slash(self):
        assert case_actor_identity(_BASE + "///") == (
            f"{_BASE}/actors/{CASE_ACTOR_SEGMENT}"
        )

    def test_unconfigured_returns_none_rather_than_guessing(self):
        """``None`` is the honest answer; a default would be unresolvable.

        Substituting a placeholder base would reintroduce exactly the failure
        this module removes — an identity the sender invents and no container
        hosts.
        """
        from vultron.config.app import reload_config

        mp = MonkeyPatch()
        try:
            mp.delenv("VULTRON_ACTOR__CASE_ACTOR_SERVICE_URL", raising=False)
            reload_config()
            assert case_actor_identity() is None
        finally:
            mp.undo()
            reload_config()


@pytest.mark.spec("CM-02-013")
def test_this_module_exposes_no_shape_predicate():
    """ADR-0088: the identity's *shape* is not a protocol signal.

    ``is_case_actor_identity`` used to live here and answer "is this id really a
    CaseActor?" from the URL suffix.  Authority is the ``CVDRole.CASE_MANAGER``
    role and nothing else (CM-02-011), so the question the predicate answered is
    not one any caller should be asking.  This module still *builds* the
    provisioned identity — a convenience ADR-0041 established and ADR-0088 keeps
    — but it no longer offers a way to test one.

    The repo-wide guarantee is the ARCH-24-004 ratchet in
    ``test/architecture/test_role_authority_resolver.py``; this asserts the
    narrower module contract so a local re-add fails next to its own tests.
    """
    from vultron.core.behaviors.case import case_actor_identity as mod

    assert not hasattr(mod, "is_case_actor_identity")
