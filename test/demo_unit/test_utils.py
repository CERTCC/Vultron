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

"""Unit tests for ``vultron.demo.utils`` — the parts that need no running node.

``DataLayerClient.dl_path`` and ``_is_same_node`` are pure, and both encode
ADR-0072 decisions whose failure mode is a *wrong answer* rather than an error:
``dl_path`` deciding which actor's replica a demo assertion reads, and
``_is_same_node`` deciding whether ``POST /actors/`` reaches the container that
would host the actor. A demo that reads the wrong replica reports a protocol
failure that did not happen, or worse passes an ADR-0058 causal gate on another
actor's committed state.

Kept out of ``test/demo/`` deliberately — see this package's docstring.
"""

import pytest

from vultron.demo.utils import DataLayerClient, _is_same_node

_NODE = "http://vendor:7999"
_VENDOR = "http://vendor:7999/api/v2/actors/vendorco"
_CASE_ACTOR = "http://vendor:7999/api/v2/actors/case-actor-abc123"


class TestDlPath:
    """``dl_path`` builds the actor-scoped inspection path."""

    def test_builds_a_collection_path_for_the_clients_own_actor(self):
        client = DataLayerClient(base_url=_NODE, actor_id=_VENDOR)
        assert (
            client.dl_path("VulnerabilityCases/")
            == "/actors/vendorco/datalayer/VulnerabilityCases/"
        )

    def test_an_empty_key_addresses_the_whole_store(self):
        client = DataLayerClient(base_url=_NODE, actor_id=_VENDOR)
        assert client.dl_path() == "/actors/vendorco/datalayer/"

    def test_sends_the_short_segment_not_the_canonical_uri(self):
        """The server recomputes the canonical URI from its own base URL.

        Sending the full URI would embed the *client's* idea of the authority in
        the path, which is exactly the coupling ADR-0072 removed — and it matches
        the convention inbox and trigger paths already use.
        """
        path = DataLayerClient(base_url=_NODE, actor_id=_VENDOR).dl_path()
        assert "http" not in path
        assert path.startswith("/actors/vendorco/")

    def test_an_explicit_actor_id_overrides_the_clients_own(self):
        """A container hosts its actor plus the CaseActors it self-hosts
        (CP-08-003), so a read about a non-primary one has to say so."""
        client = DataLayerClient(base_url=_NODE, actor_id=_VENDOR)
        assert (
            client.dl_path("cases/", actor_id=_CASE_ACTOR)
            == "/actors/case-actor-abc123/datalayer/cases/"
        )

    def test_the_override_does_not_rebind_the_client(self):
        """A one-off cross-actor read must not change later reads."""
        client = DataLayerClient(base_url=_NODE, actor_id=_VENDOR)
        client.dl_path(actor_id=_CASE_ACTOR)
        assert client.dl_path() == "/actors/vendorco/datalayer/"

    def test_raises_when_no_actor_is_available(self):
        """The documented ValueError, and the reason it is not a default.

        Defaulting to *some* actor would silently report another replica's state.
        In a causally gated demo (ADR-0058) that is worse than a crash: the gate
        passes on the wrong actor's committed state and the scenario proceeds on a
        false premise.
        """
        client = DataLayerClient(base_url=_NODE)
        with pytest.raises(ValueError, match="requires an actor_id"):
            client.dl_path("VulnerabilityCases/")

    def test_an_empty_actor_id_is_refused_at_construction(self):
        """``NonEmptyString``, so ``actor_id=""`` never reaches ``dl_path``.

        Otherwise it would surface there as "no actor id", pointing the reader at
        the read instead of at the client that was built wrong.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DataLayerClient(base_url=_NODE, actor_id="")

    def test_an_explicit_actor_id_works_on_an_unbound_client(self):
        """A client used only for inbox/health endpoints stays usable."""
        client = DataLayerClient(base_url=_NODE)
        assert (
            client.dl_path(actor_id=_VENDOR) == "/actors/vendorco/datalayer/"
        )


class TestIsSameNode:
    """Whether a ``POST /actors/`` would reach the container hosting the actor."""

    def test_the_same_scheme_host_and_port_is_the_same_node(self):
        assert _is_same_node(_NODE, _VENDOR) is True

    def test_a_differing_path_prefix_does_not_change_the_node(self):
        """``/api/v2`` varies without changing which process answers."""
        assert _is_same_node(f"{_NODE}/api/v2", _VENDOR) is True

    def test_a_different_host_is_a_different_node(self):
        assert (
            _is_same_node(_NODE, "http://finder:7999/api/v2/actors/finndervul")
            is False
        )

    def test_a_different_port_is_a_different_node(self):
        """Two containers on one host are two nodes, each with its own stores."""
        assert _is_same_node("http://vendor:8000", _VENDOR) is False

    def test_a_different_scheme_is_a_different_node(self):
        assert _is_same_node("https://vendor:7999", _VENDOR) is False

    def test_a_bare_actor_name_is_not_matched_to_a_node(self):
        """A seeding helper must not conclude a bare name is hosted here."""
        assert _is_same_node(_NODE, "vendorco") is False


class TestExchangeActorRoster:
    """``seed_exchange_actors`` seeds by slug and binds reads to the vendor.

    The seeding itself needs a node, so it is exercised in ``test/demo/``. What is
    asserted here is the part that has no HTTP in it and that a demo silently
    depends on: the roster is slugs, not absolute URIs.
    """

    def test_the_roster_names_actors_by_slug(self):
        """A slug is expanded against the serving node's base URL (ADR-0072).

        An absolute URI here would seed actors under whatever authority the demo
        author typed, and the node would adopt it verbatim (#2549) — so the demo
        would create actors it cannot address.
        """
        from vultron.demo.utils import _EXCHANGE_ACTORS

        for slug, name, actor_type in _EXCHANGE_ACTORS:
            assert (
                "/" not in slug and ":" not in slug
            ), f"{slug!r} must be a bare slug for the node to expand"
            assert name and actor_type

    def test_the_roster_covers_the_three_exchange_roles(self):
        """``discover_actors`` matches on these names, so a node seeded this way
        stays introspectable by role."""
        from vultron.demo.utils import _EXCHANGE_ACTORS

        assert len(_EXCHANGE_ACTORS) == 3
        assert [t for _, _, t in _EXCHANGE_ACTORS] == [
            "Person",
            "Organization",
            "Organization",
        ]
