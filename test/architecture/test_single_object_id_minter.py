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
"""Every new object id is minted by one helper the core and wire layers share.

OID-01-004: ``vultron.core.models.object_ids.new_object_id`` is the only
minter.  Two checks pin it:

* Both layers' ``id_`` default factories *are* that function, so a model built
  without an id gets one from it whichever layer the model lives in.
* No other module under ``vultron/`` draws a random UUID, so no second minter
  can grow beside it.  A random UUID drawn for something that is not an object
  id is listed in :data:`NON_ID_RANDOM_UUIDS` with the reason.  A derived id
  (``uuid5``, ``derived_activity_id``) is not minted and is not scanned.
"""

import ast

import pytest

from test.architecture import _corpus
from vultron.core.models.base import CoreRecord
from vultron.core.models.object_ids import new_object_id
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import generate_new_id

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

#: The shared minter's own module, the one place an object id is drawn.
MINTER_MODULE = "vultron/core/models/object_ids.py"

#: Modules that draw a random UUID for something other than an object id.
NON_ID_RANDOM_UUIDS: dict[str, str] = {
    "vultron/adapters/driving/fastapi/routers/actors/_routes.py": (
        "a hosted actor's default slug, which canonical_actor_uri turns into "
        "the base-URL actor id the actor is served at (OID-01-003)"
    ),
    "vultron/adapters/driving/fastapi/app.py": (
        "the name of an app's private in-memory SQLite database"
    ),
}

_RANDOM_UUID_CALLS = frozenset({"uuid1", "uuid4"})


def _random_uuid_drawers() -> frozenset[str]:
    """Repo-relative paths of ``vultron/`` modules that call ``uuid1``/``uuid4``."""
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning(
        *_RANDOM_UUID_CALLS, under=_VULTRON_ROOT
    ):
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and _corpus.callee_name(node.func) in _RANDOM_UUID_CALLS
            ):
                found.add(path.relative_to(_corpus.REPO_ROOT).as_posix())
                break
    return frozenset(found)


@pytest.mark.spec("OID-01-004")
def test_core_and_wire_id_default_factories_are_the_shared_minter():
    assert CoreRecord.model_fields["id_"].default_factory is new_object_id
    assert as_Base.model_fields["id_"].default_factory is new_object_id
    assert generate_new_id is new_object_id


@pytest.mark.spec("OID-01-004")
def test_no_module_but_the_shared_minter_draws_a_random_uuid():
    drawers = _random_uuid_drawers()
    assert MINTER_MODULE in drawers, (
        "the scan no longer sees the shared minter draw a UUID; "
        "fix the scan before trusting it"
    )
    assert drawers - {MINTER_MODULE} == set(NON_ID_RANDOM_UUIDS), (
        "a module outside the shared minter draws a random UUID: mint object "
        "ids with new_object_id (OID-01-004), or list a non-id use in "
        "NON_ID_RANDOM_UUIDS with its reason"
    )
