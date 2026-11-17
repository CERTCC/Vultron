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
"""The single-node guard fails a run that opens a store under two authorities.

Every test that uses the demo ``client`` runs inside
:func:`~test.support.store_sharing.no_store_shared_across_authorities`
(``test/demo/conftest.py``).  These tests pin what that guard catches: the
shape of #6085, where work resolved a ``testserver``-hosted actor in the
configured namespace (``hosted_actor_ids()`` with no base URL) and drained
its queue under the wrong id.  They use no ``client``, so the autouse guard
does not also see the warnings they provoke on purpose.
"""

import pytest

from test.support.store_sharing import no_store_shared_across_authorities
from vultron.adapters.driven import actor_hosts
from vultron.adapters.driven.datalayer_sqlite import get_datalayer

_SLUG = "store-authority-guard"
_SERVING_BASE = "http://testserver/api/v2"


def _served_actor_id() -> str:
    return actor_hosts.canonical_actor_uri(_SLUG, base_url=_SERVING_BASE)


def test_a_store_reopened_in_the_configured_namespace_fails_the_run():
    """Reopening the served actor under the configured id is the #6085 shape."""
    configured_id = actor_hosts.canonical_actor_uri(_SLUG)
    assert configured_id != _served_actor_id(), (
        "the configured base URL must differ from the serving one"
    )

    with pytest.raises(AssertionError, match="two authorities") as failure:
        with no_store_shared_across_authorities():
            get_datalayer(_served_actor_id())
            get_datalayer(configured_id)

    assert configured_id in str(failure.value)
    assert _served_actor_id() in str(failure.value)


def test_a_store_reopened_under_its_own_id_passes():
    with no_store_shared_across_authorities():
        get_datalayer(_served_actor_id())
        get_datalayer(_served_actor_id())


def test_an_error_in_the_run_is_not_masked_by_the_guard():
    with pytest.raises(RuntimeError, match="the run's own failure"):
        with no_store_shared_across_authorities():
            get_datalayer(_served_actor_id())
            get_datalayer(actor_hosts.canonical_actor_uri(_SLUG))
            raise RuntimeError("the run's own failure")
