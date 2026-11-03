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

OID-01-004: ``vultron.core.models._helpers.new_object_id`` is the only
minter.  Two checks pin it:

* Both layers' ``id_`` default factories *are* that function, so a model built
  without an id gets one from it whichever layer the model lives in.
* No other module under ``vultron/`` names ``uuid1`` or ``uuid4``, called or
  not, so no second minter can grow beside it.  A random UUID drawn for
  something that is not an object id is listed in
  :data:`NON_ID_RANDOM_UUID_EXEMPTIONS` with the reason.  A derived id
  (``uuid5``, ``derived_activity_id``) is not minted and is not scanned.
"""

import ast

import pytest

from test.architecture import _corpus
from vultron.core.models._helpers import new_object_id
from vultron.core.models.base import CoreRecord
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import generate_new_id

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

#: The shared minter's own module, the one place an object id is drawn.
MINTER_MODULE = "vultron/core/models/_helpers.py"

#: Modules that draw a random UUID for something other than an object id.
#: Pinned exemption set: each entry is a recorded decision, not a debt.
# permanent: OID-01-004 (each entry draws a UUID that never becomes an object id)
NON_ID_RANDOM_UUID_EXEMPTIONS: dict[str, str] = {
    "vultron/adapters/driving/fastapi/app.py": (
        "the name of an app's private in-memory SQLite database"
    ),
    "vultron/demo/determinism.py": (
        "replaces uuid4 with a seeded stand-in for a recording run, so the "
        "shared minter's ids repeat; it mints nothing itself"
    ),
}

_RANDOM_UUID_NAMES = frozenset({"uuid1", "uuid4"})


def _names_a_random_uuid(node: ast.AST) -> bool:
    """Whether *node* names ``uuid1``/``uuid4``, called or not.

    A bare reference counts as well as a call, so ``default_factory=uuid4``
    is caught, and so is ``from uuid import uuid4 as fresh``: the import names
    the function whatever the local alias is.
    """
    if isinstance(node, ast.Name):
        return node.id in _RANDOM_UUID_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _RANDOM_UUID_NAMES
    if isinstance(node, ast.ImportFrom) and node.module == "uuid":
        return any(alias.name in _RANDOM_UUID_NAMES for alias in node.names)
    return False


def _random_uuid_drawers() -> frozenset[str]:
    """Repo-relative paths of ``vultron/`` modules that name ``uuid1``/``uuid4``."""
    return frozenset(
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in _corpus.files_mentioning(
            *_RANDOM_UUID_NAMES, under=_VULTRON_ROOT
        )
        if any(_names_a_random_uuid(node) for node in ast.walk(tree))
    )


@pytest.mark.spec("OID-01-004")
@pytest.mark.parametrize(
    "source",
    [
        "import uuid\nx = uuid.uuid4()\n",
        "from uuid import uuid4\n",
        "from uuid import uuid4 as fresh\nx = fresh()\n",
        "import uuid\nf = Field(default_factory=uuid.uuid4)\n",
        "import uuid\nx = uuid.uuid1()\n",
    ],
)
def test_the_scan_sees_every_way_of_naming_a_random_uuid(source: str):
    tree = _corpus.parse_inline(source)
    assert any(_names_a_random_uuid(node) for node in ast.walk(tree))


@pytest.mark.spec("OID-01-004")
def test_the_scan_ignores_a_derived_uuid():
    tree = _corpus.parse_inline(
        "import uuid\nx = uuid.uuid5(uuid.NAMESPACE_URL, 'a')\n"
    )
    assert not any(_names_a_random_uuid(node) for node in ast.walk(tree))


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
    assert drawers - {MINTER_MODULE} == set(NON_ID_RANDOM_UUID_EXEMPTIONS), (
        "a module outside the shared minter names uuid1/uuid4: mint object "
        "ids with new_object_id (OID-01-004), or list a non-id use in "
        "NON_ID_RANDOM_UUID_EXEMPTIONS with its reason"
    )
