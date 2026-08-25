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

"""Tests for per-actor store resolution in ``datalayer_sqlite.engine``.

This module is where ADR-0073's central claim lives: a URL *template* plus an
actor id resolves to exactly one store, and two different actors never resolve to
the same one under a single authority.  Everything above it — which store a route
reads, which store a BT node writes — is that resolution applied.

Covers ``actor_slug``, ``actor_db_url``, ``_is_memory_url``,
``_memory_base_name``, ``get_actor_engine`` (including the ``_STORE_CLAIMANTS``
cross-authority collision warning) and ``dispose_actor_engines``.
"""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import engine as engine_mod
from vultron.adapters.driven.datalayer_sqlite.engine import (
    _ENGINES,
    _STORE_CLAIMANTS,
    _is_memory_url,
    _memory_base_name,
    actor_db_url,
    actor_slug,
    dispose_actor_engines,
    get_actor_engine,
)


@pytest.fixture(autouse=True)
def _clean_engine_caches():
    """Leave both module caches exactly as they were found.

    ``_ENGINES`` and ``_STORE_CLAIMANTS`` are process-level, so a test that
    claims a store URL would otherwise change what a later test observes — the
    collision warning in particular fires only on the *second* distinct claim.
    """
    engines_before = dict(_ENGINES)
    claimants_before = dict(_STORE_CLAIMANTS)
    yield
    for key, eng in list(_ENGINES.items()):
        if key not in engines_before:
            eng.dispose()
    _ENGINES.clear()
    _ENGINES.update(engines_before)
    _STORE_CLAIMANTS.clear()
    _STORE_CLAIMANTS.update(claimants_before)


class TestActorSlug:
    """``actor_slug`` maps an actor URI to a filename component."""

    def test_uses_the_final_path_segment(self):
        assert (
            actor_slug("https://example.org/api/v2/actors/vendor") == "vendor"
        )

    def test_ignores_a_trailing_slash(self):
        assert (
            actor_slug("https://example.org/api/v2/actors/vendor/") == "vendor"
        )

    def test_uses_the_path_of_an_opaque_uri_not_the_whole_string(self):
        """A ``urn:`` id *does* parse, so the scheme is dropped like any other.

        The raw-string fallback is reached only when ``urlsplit`` yields an empty
        path — a bare name. Pinning this keeps the two branches distinguishable:
        two urns differing only in scheme would share a store.
        """
        assert (
            actor_slug("urn:uuid:2f0c1e6a-0000-0000-0000-000000000001")
            == "uuid_2f0c1e6a-0000-0000-0000-000000000001"
        )

    def test_accepts_a_bare_name(self):
        assert actor_slug("finder") == "finder"

    @pytest.mark.parametrize(
        "unsafe, expected",
        [
            ("https://example.org/actors/a b", "a_b"),
            ("https://example.org/actors/a;rm -rf", "a_rm_-rf"),
            ("https://example.org/actors/a%2Fb", "a_2Fb"),
        ],
    )
    def test_collapses_characters_that_are_unsafe_in_a_filename(
        self, unsafe, expected
    ):
        """A slug becomes a path component, so it must not escape or quote."""
        assert actor_slug(unsafe) == expected

    @pytest.mark.parametrize("bad", ["", "/", "..", "/..", "./"])
    def test_rejects_an_id_that_yields_no_usable_slug(self, bad):
        """Failing loudly beats silently sharing another actor's store."""
        with pytest.raises(ValueError):
            actor_slug(bad)

    def test_two_authorities_with_one_segment_collide(self):
        """Documented limitation, not an accident — see issue #2549.

        The scheme and netloc are dropped, so a co-hosted ``case-actor`` and a
        *peer* whose URI also ends in ``case-actor`` produce one slug. The bug in
        that scenario is opening a store for a foreign id at all;
        ``get_actor_engine`` is what notices (see
        :class:`TestGetActorEngineCollisionWarning`).
        """
        assert actor_slug(
            "http://vendor:7999/api/v2/actors/case-actor"
        ) == actor_slug("http://case-actor:7999/api/v2/actors/case-actor")


class TestActorDbUrl:
    """``actor_db_url`` treats the configured URL as a template."""

    def test_inserts_the_slug_into_a_file_url(self):
        assert (
            actor_db_url(
                "sqlite:////app/data/mydb.sqlite",
                "https://example.org/actors/vendor",
            )
            == "sqlite:////app/data/mydb-vendor.sqlite"
        )

    def test_supplies_a_default_suffix_when_the_template_has_none(self):
        assert (
            actor_db_url("sqlite:////app/data/mydb", "…/actors/vendor")
            == "sqlite:////app/data/mydb-vendor.sqlite"
        )

    def test_a_directory_only_template_names_a_sibling_of_the_directory(self):
        """Footgun, pinned so a change to it is visible.

        ``Path("/app/data/").stem`` is ``"data"``, so a template that looks like
        a directory produces ``/app/data-vendor.sqlite`` *next to* it rather than
        a file inside it. Configure the template as a file path, not a directory.
        """
        assert (
            actor_db_url("sqlite:////app/data/", "…/actors/vendor")
            == "sqlite:////app/data-vendor.sqlite"
        )

    def test_names_an_anonymous_in_memory_database(self):
        """The resolved URL, not an Engine object, must carry store identity."""
        assert actor_db_url("sqlite:///:memory:", "…/actors/vendor") == (
            "sqlite:///file:vultron-vendor?mode=memory&cache=shared&uri=true"
        )

    def test_preserves_a_named_in_memory_base(self):
        """``create_app()`` isolates each app by naming its template (#534)."""
        resolved = actor_db_url(
            "sqlite:///file:app7?mode=memory&cache=shared&uri=true",
            "…/actors/vendor",
        )
        assert resolved == (
            "sqlite:///file:app7-vendor?mode=memory&cache=shared&uri=true"
        )

    def test_two_named_deployments_hosting_one_actor_do_not_share(self):
        template_a = "sqlite:///file:app7?mode=memory&cache=shared&uri=true"
        template_b = "sqlite:///file:app8?mode=memory&cache=shared&uri=true"
        assert actor_db_url(template_a, "…/actors/vendor") != actor_db_url(
            template_b, "…/actors/vendor"
        )

    def test_two_actors_never_share_a_store(self):
        template = "sqlite:////app/data/mydb.sqlite"
        assert actor_db_url(template, "…/actors/vendor") != actor_db_url(
            template, "…/actors/finder"
        )

    def test_refuses_a_url_shape_it_cannot_rewrite(self):
        """Returning it unchanged would silently put two actors in one store."""
        with pytest.raises(ValueError, match="cannot derive"):
            actor_db_url("postgresql://localhost/vultron", "…/actors/vendor")

    def test_is_not_idempotent_and_that_is_documented(self):
        """Callers must pass the *template*; re-applying appends a second slug.

        ``_memory_base_name`` cannot unambiguously strip one, because base
        ``app7-vendor`` is indistinguishable from base ``app7`` plus slug
        ``vendor``.  Pinning this keeps the docstring's warning honest.
        """
        once = actor_db_url("sqlite:///:memory:", "…/actors/vendor")
        assert actor_db_url(once, "…/actors/vendor") == (
            "sqlite:///file:vultron-vendor-vendor"
            "?mode=memory&cache=shared&uri=true"
        )


class TestMemoryUrlHelpers:
    @pytest.mark.parametrize(
        "url",
        [
            "sqlite:///:memory:",
            "sqlite:///file:app7?mode=memory&cache=shared&uri=true",
        ],
    )
    def test_recognises_both_in_memory_spellings(self, url):
        assert _is_memory_url(url) is True

    def test_a_file_url_is_not_in_memory(self):
        assert _is_memory_url("sqlite:////app/data/mydb.sqlite") is False

    def test_anonymous_memory_base_name_defaults(self):
        assert _memory_base_name("sqlite:///:memory:") == "vultron"

    def test_named_memory_base_name_is_read_from_the_url(self):
        assert (
            _memory_base_name(
                "sqlite:///file:app7?mode=memory&cache=shared&uri=true"
            )
            == "app7"
        )


class TestGetActorEngine:
    def test_two_instances_for_one_actor_share_one_engine(self):
        """An actor's store must not split in two."""
        first = get_actor_engine("sqlite:///:memory:", "…/actors/eng-share")
        second = get_actor_engine("sqlite:///:memory:", "…/actors/eng-share")
        assert first is second

    def test_two_actors_get_different_engines(self):
        a = get_actor_engine("sqlite:///:memory:", "…/actors/eng-a")
        b = get_actor_engine("sqlite:///:memory:", "…/actors/eng-b")
        assert a is not b

    def test_caches_under_the_resolved_url(self):
        get_actor_engine("sqlite:///:memory:", "…/actors/eng-key")
        assert (
            "sqlite:///file:vultron-eng-key?mode=memory&cache=shared&uri=true"
            in _ENGINES
        )


class TestGetActorEngineCollisionWarning:
    """The ``_STORE_CLAIMANTS`` guard for the issue-#2549 slug collision."""

    _FOREIGN = "http://case-actor:7999/api/v2/actors/eng-collide"
    _LOCAL = "http://vendor:7999/api/v2/actors/eng-collide"

    def test_warns_when_a_second_authority_claims_the_same_store(self, caplog):
        get_actor_engine("sqlite:///:memory:", self._LOCAL)
        with caplog.at_level(logging.WARNING, logger=engine_mod.__name__):
            get_actor_engine("sqlite:///:memory:", self._FOREIGN)

        assert any(
            "shared by two distinct actor ids" in r.message
            and "#2549" in r.message
            for r in caplog.records
        ), caplog.text

    def test_warns_rather_than_raises(self):
        """Peer registration via ``POST /actors/`` still reaches this path."""
        first = get_actor_engine("sqlite:///:memory:", self._LOCAL)
        second = get_actor_engine("sqlite:///:memory:", self._FOREIGN)
        assert second is first

    def test_does_not_warn_for_a_repeat_claim_by_the_same_id(self, caplog):
        get_actor_engine("sqlite:///:memory:", self._LOCAL)
        with caplog.at_level(logging.WARNING, logger=engine_mod.__name__):
            get_actor_engine("sqlite:///:memory:", self._LOCAL)
        assert "shared by two distinct actor ids" not in caplog.text

    def test_the_claim_survives_disposal(self, caplog):
        """Disposal is a legitimate reset; it must not erase who claimed what.

        That is why ``_STORE_CLAIMANTS`` is a separate dict from ``_ENGINES``:
        a reset between tests would otherwise re-arm the warning and hide a real
        collision behind a "first claim".
        """
        get_actor_engine("sqlite:///:memory:", self._LOCAL)
        dispose_actor_engines("sqlite:///:memory:", self._LOCAL)
        with caplog.at_level(logging.WARNING, logger=engine_mod.__name__):
            get_actor_engine("sqlite:///:memory:", self._FOREIGN)
        assert "shared by two distinct actor ids" in caplog.text


class TestDisposeActorEngines:
    def test_disposes_one_actor_when_both_arguments_are_given(self):
        keep = get_actor_engine("sqlite:///:memory:", "…/actors/disp-keep")
        get_actor_engine("sqlite:///:memory:", "…/actors/disp-drop")

        dispose_actor_engines("sqlite:///:memory:", "…/actors/disp-drop")

        assert (
            "sqlite:///file:vultron-disp-drop"
            "?mode=memory&cache=shared&uri=true" not in _ENGINES
        )
        assert (
            get_actor_engine("sqlite:///:memory:", "…/actors/disp-keep")
            is keep
        )

    def test_disposes_every_actor_of_one_named_memory_deployment(self):
        template = "sqlite:///file:disp-app?mode=memory&cache=shared&uri=true"
        other = "sqlite:///file:disp-other?mode=memory&cache=shared&uri=true"
        get_actor_engine(template, "…/actors/disp-x")
        get_actor_engine(template, "…/actors/disp-y")
        untouched = get_actor_engine(other, "…/actors/disp-x")

        dispose_actor_engines(template)

        assert not [k for k in _ENGINES if "disp-app-" in k]
        assert get_actor_engine(other, "…/actors/disp-x") is untouched

    def test_disposes_everything_when_called_with_no_arguments(self):
        get_actor_engine("sqlite:///:memory:", "…/actors/disp-all")
        dispose_actor_engines()
        assert _ENGINES == {}

    def test_disposing_an_unknown_actor_is_a_no_op(self):
        before = dict(_ENGINES)
        dispose_actor_engines("sqlite:///:memory:", "…/actors/disp-absent")
        assert _ENGINES == before
