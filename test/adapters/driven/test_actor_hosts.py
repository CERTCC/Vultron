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

"""Tests for ``vultron.adapters.driven.actor_hosts``.

``actor_hosts`` is the one node-level fact ADR-0073 leaves standing: which
actors run here, and what canonical URI a URL path segment means.  It holds no
protocol state, so these tests are about the *mapping* — in particular that it
is derivable in both directions, which is why no registry is persisted.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.actor_hosts import (
    ACTORS_SEGMENT,
    assert_hosted_slug,
    canonical_actor_uri,
    hosted_actor_ids,
    hosted_actor_slugs,
    local_actor_id,
    storage_ready,
)

_BASE = "https://example.org/api/v2"


class TestCanonicalActorUri:
    def test_builds_the_uri_from_a_bare_segment(self):
        assert (
            canonical_actor_uri("vendor", _BASE)
            == f"{_BASE}/{ACTORS_SEGMENT}/vendor"
        )

    def test_normalises_a_trailing_slash_on_the_base_url(self):
        assert (
            canonical_actor_uri("vendor", _BASE + "/")
            == f"{_BASE}/{ACTORS_SEGMENT}/vendor"
        )

    def test_strips_slashes_from_the_segment(self):
        assert (
            canonical_actor_uri("/vendor/", _BASE)
            == f"{_BASE}/{ACTORS_SEGMENT}/vendor"
        )

    def test_is_idempotent_on_an_already_canonical_uri(self):
        """Double-prefixing would name an endpoint the node does not serve."""
        canonical = f"{_BASE}/{ACTORS_SEGMENT}/vendor"
        assert canonical_actor_uri(canonical, _BASE) == canonical

    def test_adopts_a_foreign_authority_verbatim(self):
        """ADR-0073#peer-records-in-knowers-store: a peer's id is the URL delivery posts to.

        Rewriting it into this node's namespace would turn a reachable peer into
        a local phantom.  The cost — a local store minted for an actor this node
        does not host — is issue #2549, logged by ``get_actor_engine``.
        """
        foreign = "http://vendor:7999/api/v2/actors/vendor"
        assert canonical_actor_uri(foreign, _BASE) == foreign

    def test_rejects_an_empty_segment(self):
        with pytest.raises(ValueError, match="must not be empty"):
            canonical_actor_uri("", _BASE)

    @pytest.mark.parametrize("bad", ["/", "//", "///"])
    def test_rejects_a_segment_that_strips_to_nothing(self, bad):
        """``"/"`` is not empty but names nothing.

        Unchecked it produced ``{base}/actors/``, whose final path segment is
        ``actors`` — a usable slug — so the node opened a store for a phantom
        actor named after the path component and nothing downstream could tell.
        """
        with pytest.raises(ValueError, match="names no actor"):
            canonical_actor_uri(bad, _BASE)

    def test_falls_back_to_configured_base_url(self):
        with patch.object(actor_hosts, "get_config") as get_config:
            get_config.return_value.server.base_url = "https://cfg.test/api/v2"
            assert canonical_actor_uri("vendor") == (
                f"https://cfg.test/api/v2/{ACTORS_SEGMENT}/vendor"
            )

    def test_round_trips_with_actor_slug(self):
        """The reversibility that lets the node enumerate hosts without a registry."""
        from vultron.adapters.driven.datalayer_sqlite.engine import actor_slug

        assert actor_slug(canonical_actor_uri("vendor", _BASE)) == "vendor"


class TestHostedActorSlugs:
    """Slugs are discovered from the per-actor store files that exist."""

    def _template(self, directory: Path) -> str:
        return f"sqlite:///{directory / 'mydb.sqlite'}"

    def test_finds_every_per_actor_store(self, tmp_path):
        for name in ("mydb-vendor.sqlite", "mydb-finder.sqlite"):
            (tmp_path / name).touch()
        assert hosted_actor_slugs(self._template(tmp_path)) == {
            "vendor",
            "finder",
        }

    def test_includes_a_runtime_created_case_actor(self, tmp_path):
        """CP-08-003 CaseActors appear in no configuration file."""
        (tmp_path / "mydb-case-actor-9f3a.sqlite").touch()
        assert hosted_actor_slugs(self._template(tmp_path)) == {
            "case-actor-9f3a"
        }

    def test_ignores_the_bare_template_file(self, tmp_path):
        """``mydb.sqlite`` itself is not an actor; nor is an empty slug."""
        (tmp_path / "mydb.sqlite").touch()
        (tmp_path / "mydb-.sqlite").touch()
        assert hosted_actor_slugs(self._template(tmp_path)) == set()

    def test_ignores_files_with_another_suffix(self, tmp_path):
        (tmp_path / "mydb-vendor.sqlite-wal").touch()
        (tmp_path / "mydb-vendor.log").touch()
        assert hosted_actor_slugs(self._template(tmp_path)) == set()

    def test_an_absent_directory_hosts_nothing(self, tmp_path):
        """Not an error: a node that never wrote a store hosts nothing."""
        missing = tmp_path / "never-created"
        assert hosted_actor_slugs(f"sqlite:///{missing / 'mydb.sqlite'}") == (
            set()
        )

    def test_an_in_memory_url_has_no_files_to_enumerate(self):
        assert hosted_actor_slugs("sqlite:///:memory:") == set()

    def test_a_url_with_no_location_yields_nothing(self):
        assert hosted_actor_slugs("sqlite://") == set()


class TestHostedActorIds:
    def test_maps_each_slug_back_to_a_canonical_uri(self, tmp_path):
        (tmp_path / "mydb-vendor.sqlite").touch()
        (tmp_path / "mydb-finder.sqlite").touch()
        assert hosted_actor_ids(
            f"sqlite:///{tmp_path / 'mydb.sqlite'}", _BASE
        ) == [
            f"{_BASE}/{ACTORS_SEGMENT}/finder",
            f"{_BASE}/{ACTORS_SEGMENT}/vendor",
        ]

    def test_uses_the_instance_registry_in_memory_mode(self):
        """An in-memory store exists only while an instance holds it open."""
        with patch(
            "vultron.adapters.driven.datalayer_sqlite"
            ".get_all_actor_datalayers",
            return_value={"b-actor": object(), "a-actor": object()},
        ):
            assert hosted_actor_ids("sqlite:///:memory:", _BASE) == [
                "a-actor",
                "b-actor",
            ]

    def test_output_is_sorted(self, tmp_path):
        for name in ("mydb-c.sqlite", "mydb-a.sqlite", "mydb-b.sqlite"):
            (tmp_path / name).touch()
        ids = hosted_actor_ids(f"sqlite:///{tmp_path / 'mydb.sqlite'}", _BASE)
        assert ids == sorted(ids)


class TestStorageReady:
    def test_in_memory_storage_is_always_ready(self):
        assert storage_ready("sqlite:///:memory:") is True

    def test_a_writable_directory_is_ready(self, tmp_path):
        assert storage_ready(f"sqlite:///{tmp_path / 'mydb.sqlite'}") is True

    def test_creates_a_missing_directory(self, tmp_path):
        target = tmp_path / "nested" / "deeper"
        assert storage_ready(f"sqlite:///{target / 'mydb.sqlite'}") is True
        assert target.is_dir()

    def test_an_uninterpretable_url_is_not_ready(self):
        assert storage_ready("sqlite://") is False

    def test_a_read_only_directory_is_not_ready(self, tmp_path):
        if os.geteuid() == 0:
            pytest.skip("root bypasses the write-permission check")
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        try:
            assert (
                storage_ready(f"sqlite:///{locked / 'sub' / 'mydb.sqlite'}")
                is False
            )
        finally:
            locked.chmod(0o700)

    def test_never_creates_a_probe_store(self, tmp_path):
        """Readiness is a property of the *location*, not of any one actor.

        A probe actor's store would then be reported by
        ``hosted_actor_slugs`` as a hosted actor.
        """
        storage_ready(f"sqlite:///{tmp_path / 'mydb.sqlite'}")
        assert list(tmp_path.glob("*.sqlite")) == []


class TestLocalActorId:
    def test_returns_none_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        assert local_actor_id(_BASE) is None

    def test_canonicalises_a_bare_configured_name(self, monkeypatch):
        monkeypatch.setenv("VULTRON_ACTOR_ID", "vendor")
        assert local_actor_id(_BASE) == f"{_BASE}/{ACTORS_SEGMENT}/vendor"

    def test_passes_an_absolute_configured_id_through(self, monkeypatch):
        monkeypatch.setenv(
            "VULTRON_ACTOR_ID", "http://vendor:7999/api/v2/actors/vendor"
        )
        assert (
            local_actor_id(_BASE) == "http://vendor:7999/api/v2/actors/vendor"
        )

    def test_reads_the_single_underscore_env_var(self, monkeypatch):
        """Every compose file sets ``VULTRON_ACTOR_ID``, not ``VULTRON_ACTOR__*``.

        Moving this onto ``AppConfig.actor`` (CFG-07-005..007, issue #2550) has
        to keep this spelling working, because a nested ``ActorConfig`` field
        would be read as ``VULTRON_ACTOR__ACTOR_ID``.
        """
        monkeypatch.delenv("VULTRON_ACTOR_ID", raising=False)
        monkeypatch.setenv("VULTRON_ACTOR__ACTOR_ID", "vendor")
        assert local_actor_id(_BASE) is None


class TestAssertHostedSlug:
    def test_validates_an_inbound_segment(self):
        assert assert_hosted_slug("vendor") == "vendor"

    def test_accepts_an_absolute_uri(self):
        assert (
            assert_hosted_slug("http://vendor:7999/api/v2/actors/v2") == "v2"
        )

    @pytest.mark.parametrize("bad", ["", "/", ".."])
    def test_rejects_a_segment_that_cannot_become_a_filename(self, bad):
        """Inbound URL segments reach the storage layer as path components."""
        with pytest.raises(ValueError):
            assert_hosted_slug(bad)

    def test_neutralises_a_traversal_attempt(self, monkeypatch):
        monkeypatch.setattr(
            actor_hosts, "get_config", lambda: _CONFIG_STUB(_BASE)
        )
        assert "/" not in assert_hosted_slug("../../etc/passwd")


class _CONFIG_STUB:
    """Minimal stand-in for ``get_config()`` exposing only ``server.base_url``."""

    def __init__(self, base_url: str) -> None:
        self.server = type("_Server", (), {"base_url": base_url})()
