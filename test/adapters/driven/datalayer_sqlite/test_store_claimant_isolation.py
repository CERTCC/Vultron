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

"""A store claim must not leak from one test into the next (#3545).

``_STORE_CLAIMANTS`` is process-lifetime by design — see
``reset_store_claimants`` for why disposal deliberately does not clear it — so
the only thing standing between it and cross-test contamination is the autouse
reset in ``test/conftest.py``.

This file is that reset's regression guard, and it is deliberately shaped as an
**ordered pair** of tests rather than a single self-contained one, because the
defect only exists *across* a test boundary. ``test_engine.py`` cannot host it:
that module's own ``_clean_engine_caches`` fixture snapshots and restores
``_STORE_CLAIMANTS`` itself, which would mask exactly the conftest behaviour
under test here. There is intentionally no local claimant fixture in this file.

The original symptom: two fixtures whose actor ids differ only outside the final
path segment — ``https://example.org/actors/test-actor`` (``test_bridge.py``) and
``https://test.example/api/v2/actors/test-actor`` (the ``datalayer`` fixture) —
both resolve to slug ``test-actor``. Running ``test/core/behaviors`` before
``test/core/use_cases/received/test_create_report_received.py`` made two
"no WARNING should be emitted" assertions fail on a warning seeded by the
earlier directory.
"""

import logging

from vultron.adapters.driven.datalayer_sqlite.engine import get_actor_engine

#: Differ only outside the final path segment, so both resolve to slug
#: ``claimant-leak`` — the shape that collides.
_FIRST_AUTHORITY = "https://example.org/actors/claimant-leak"
_SECOND_AUTHORITY = "https://test.example/api/v2/actors/claimant-leak"


def test_a_first_test_claims_the_slug() -> None:
    """Claim the store, the way any test that merely uses an actor id does.

    This test asserts almost nothing on its own; its job is to leave state
    behind for the one below. That is the whole defect shape — the poisoning
    test looks completely innocent.
    """
    assert get_actor_engine("sqlite:///:memory:", _FIRST_AUTHORITY) is not None


def test_a_later_test_sees_no_collision_warning_from_the_earlier_one(
    caplog,
) -> None:
    """The guard: a different authority on the same slug must not warn here.

    If the autouse ``reset_store_claimants()`` in ``test/conftest.py`` is
    removed, the claim from the test above survives and this fails — which is
    precisely how #3545 presented, only with the two tests in different
    directories and hundreds of tests apart.
    """
    with caplog.at_level(logging.WARNING):
        get_actor_engine("sqlite:///:memory:", _SECOND_AUTHORITY)

    collisions = [
        r.message
        for r in caplog.records
        if "shared by two distinct actor ids" in r.message
    ]
    assert not collisions, (
        "a store claim leaked from an earlier test: "
        f"{collisions}\n\n"
        "_STORE_CLAIMANTS is process-lifetime by design (disposal must not"
        " erase a claim), so test/conftest.py's autouse fixture has to call"
        " reset_store_claimants() after each test.  Restore that call."
    )
