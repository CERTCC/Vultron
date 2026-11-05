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
* No function under ``vultron/`` but the minter names ``uuid1`` or ``uuid4``,
  called or not, so no second minter can grow beside it.  The scan works per
  enclosing function, not per module, so a second minter cannot hide in a
  module that already has an allowed use.  A random UUID drawn for something
  that is not an object id is listed in :data:`NON_ID_RANDOM_UUID_EXEMPTIONS`
  with the reason.  A derived id (``uuid5``, ``derived_activity_id``) is not
  minted and is not scanned.

A *replacement* of the minter's draw counts as naming it, and names it as a
string: ``patch.object(uuid, "uuid4", ...)`` installs a stand-in without any
``uuid4`` expression for an AST name scan to find.  So a dotted-path string
literal whose last segment is ``uuid1`` or ``uuid4`` is a site too — the
string-literal form of the #5535 pitfall, where a ratchet keyed on one
implementation shape loses a subject while its non-empty guard still passes.

The scan covers the ``uuid`` module's random draws only.  Random bytes from
``secrets`` or ``os.urandom`` are not object-id minters by this codebase's
convention and are not looked for.
"""

import ast
import re

import pytest

from test.architecture import _corpus
from vultron.core.models._helpers import new_object_id
from vultron.core.models.base import CoreRecord
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import generate_new_id

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

#: The scope name of code outside any function or class.
MODULE_SCOPE = "<module>"

#: The shared minter: the one function that draws an object id.
MINTER_SITE = ("vultron/core/models/_helpers/ids.py", "new_object_id")

#: Functions that draw a random UUID for something other than an object id,
#: keyed on (repo-relative path, dotted enclosing function).
#: Pinned exemption set: each entry is a recorded decision, not a debt.
# permanent: OID-01-004 (each entry draws, or replaces the draw of, a
# UUID that never mints an object id)
NON_ID_RANDOM_UUID_EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "vultron/adapters/driving/fastapi/app.py",
        "_auto_inject_isolated_datalayer",
    ): "the name of an app's private in-memory SQLite database",
    ("vultron/demo/determinism.py", "deterministic_run"): (
        "replaces uuid4 with a seeded stand-in for a recording run, so the "
        "shared minter's ids repeat; it mints nothing itself"
    ),
    (
        "vultron/wire/as2/vocab/examples/_base.py",
        "_example_scope",
    ): (
        "replaces uuid4 with a derived stand-in while the docs examples are "
        "built, so the committed corpus does not move between runs; it mints "
        "nothing itself"
    ),
}

_RANDOM_UUID_NAMES = frozenset({"uuid1", "uuid4"})
_STAR_IMPORT = "from uuid import *"

#: A dotted attribute path and nothing else, so prose that happens to mention
#: ``uuid4`` is not read as a patch target.
_DOTTED_PATH = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


def _names_a_random_uuid(text: str) -> bool:
    """Whether *text* is a dotted path whose last segment is a random draw."""
    return bool(_DOTTED_PATH.match(text)) and (
        text.rsplit(".", 1)[-1] in _RANDOM_UUID_NAMES
    )


class _RandomUuidSites(ast.NodeVisitor):
    """Collect the enclosing scopes in which ``uuid1``/``uuid4`` is named.

    A bare reference counts as well as a call, so ``default_factory=uuid4`` is
    caught.  ``from uuid import uuid4 as fresh`` makes ``fresh`` a name to
    look for, so an alias is caught where it is used.  ``from uuid import *``
    hides which names it binds, so the import itself is a site.
    """

    def __init__(self) -> None:
        self._scope: list[str] = []
        self._names = set(_RANDOM_UUID_NAMES)
        self.sites: set[str] = set()

    def _record(self) -> None:
        self.sites.add(".".join(self._scope) or MODULE_SCOPE)

    def _visit_scope(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope
    visit_ClassDef = _visit_scope

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module != "uuid":
            return
        for alias in node.names:
            if alias.name == "*":
                self._record()
            elif alias.name in _RANDOM_UUID_NAMES:
                self._names.add(alias.asname or alias.name)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self._names:
            self._record()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _RANDOM_UUID_NAMES:
            self._record()
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """A patch target names the minter's draw as a string, not a name."""
        if isinstance(node.value, str) and _names_a_random_uuid(node.value):
            self._record()


def _sites_in(tree: ast.AST) -> set[str]:
    finder = _RandomUuidSites()
    finder.visit(tree)
    return finder.sites


def _random_uuid_sites() -> frozenset[tuple[str, str]]:
    """(path, enclosing function) of every ``vultron/`` use of ``uuid1``/``uuid4``."""
    return frozenset(
        (path.relative_to(_corpus.REPO_ROOT).as_posix(), site)
        for path, tree in _corpus.files_mentioning(
            *_RANDOM_UUID_NAMES, _STAR_IMPORT, under=_VULTRON_ROOT
        )
        for site in _sites_in(tree)
    )


@pytest.mark.spec("OID-01-004")
@pytest.mark.parametrize(
    "source",
    [
        "import uuid\nx = uuid.uuid4()\n",
        "from uuid import uuid4\nf = Field(default_factory=uuid4)\n",
        "from uuid import uuid4 as fresh\nx = fresh()\n",
        "import uuid\nf = Field(default_factory=uuid.uuid4)\n",
        "import uuid\nx = uuid.uuid1()\n",
        "from uuid import *\n",
        'import uuid\npatch.object(uuid, "uuid4", stand_in)\n',
        'patch("uuid.uuid4", stand_in)\n',
    ],
)
def test_the_scan_sees_every_way_of_naming_a_random_uuid(source: str):
    assert _sites_in(_corpus.parse_inline(source)) == {MODULE_SCOPE}


@pytest.mark.spec("OID-01-004")
def test_the_scan_names_the_enclosing_function():
    tree = _corpus.parse_inline(
        "import uuid\n"
        "class Minter:\n"
        "    def mint(self):\n"
        "        return uuid.uuid4()\n"
        "def other():\n"
        "    return 1\n"
    )
    assert _sites_in(tree) == {"Minter.mint"}


@pytest.mark.spec("OID-01-004")
def test_the_scan_ignores_a_derived_uuid():
    tree = _corpus.parse_inline(
        "import uuid\nx = uuid.uuid5(uuid.NAMESPACE_URL, 'a')\n"
    )
    assert _sites_in(tree) == set()


@pytest.mark.spec("OID-01-004")
def test_core_and_wire_id_default_factories_are_the_shared_minter():
    assert CoreRecord.model_fields["id_"].default_factory is new_object_id
    assert as_Base.model_fields["id_"].default_factory is new_object_id
    assert generate_new_id is new_object_id


@pytest.mark.spec("OID-01-004")
def test_no_function_but_the_shared_minter_draws_a_random_uuid():
    sites = _random_uuid_sites()
    assert MINTER_SITE in sites, (
        "the scan no longer sees the shared minter draw a UUID; "
        "fix the scan before trusting it"
    )
    assert sites - {MINTER_SITE} == set(NON_ID_RANDOM_UUID_EXEMPTIONS), (
        "a function outside the shared minter names uuid1/uuid4: mint object "
        "ids with new_object_id (OID-01-004), or list a non-id use in "
        "NON_ID_RANDOM_UUID_EXEMPTIONS with its reason"
    )
