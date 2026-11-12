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
minter, and it draws from the installed id source, whose default is the system
id source (OID-01-011, ADR-0185); nothing else draws or replaces the
``uuid`` module's random draw (OID-01-012).  Two checks pin it:

* Both layers' ``id_`` default factories *are* that function, so a model built
  without an id gets one from it whichever layer the model lives in.
* No function under ``vultron/`` but the system id source names ``uuid1`` or
  ``uuid4``, called or not, so no second minter can grow beside it.  The scan works per
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

#: The system id source: the one function that draws a random UUID for an
#: object id.  The minter, ``new_object_id``, draws through the installed id
#: source and names no ``uuid`` draw itself (OID-01-011).
MINTER_SITE = ("vultron/core/models/_helpers/ids.py", "system_id_source")

#: The one place that may name the system id source: the module-scope slot
#: that holds it as the default (``_SLOT``).  Any other caller would draw past
#: an installed source.
SYSTEM_SOURCE_SITES = frozenset(
    {("vultron/core/models/_helpers/ids.py", MODULE_SCOPE)}
)
_SYSTEM_SOURCE = frozenset({"system_id_source"})

#: Functions that draw a random UUID for something other than an object id,
#: keyed on (repo-relative path, dotted enclosing function).
#: Pinned exemption set: each entry is a recorded decision, not a debt.
# permanent: OID-01-004 (each entry draws a UUID that never mints an
# object id; OID-01-012, ADR-0185)
NON_ID_RANDOM_UUID_EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "vultron/adapters/driving/fastapi/app.py",
        "_auto_inject_isolated_datalayer",
    ): "the name of an app's private in-memory SQLite database",
}

_RANDOM_UUID_NAMES = frozenset({"uuid1", "uuid4"})
_STAR_IMPORT = "from uuid import *"

#: A dotted attribute path and nothing else, so prose that happens to mention
#: ``uuid4`` is not read as a patch target.
_DOTTED_PATH = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
)


def _names_one_of(text: str, names: frozenset[str]) -> bool:
    """Whether *text* is a dotted path whose last segment is in *names*."""
    return bool(_DOTTED_PATH.match(text)) and (
        text.rsplit(".", 1)[-1] in names
    )


class _NameSites(ast.NodeVisitor):
    """Collect the enclosing scopes in which any of *names* is named.

    A bare reference counts as well as a call, so ``default_factory=uuid4`` is
    caught.  ``from <module> import name as fresh`` makes ``fresh`` a name to
    look for, so an alias is caught where it is used.  ``from <module> import
    *`` hides which names it binds, so the import itself is a site.  A
    dotted-path string literal ending in one of *names* is a patch target, so
    it is a site too.
    """

    def __init__(self, names: frozenset[str], module: str) -> None:
        self._scope: list[str] = []
        self._targets = names
        self._module = module
        self._names = set(names)
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
        if node.module is None or not (
            node.module == self._module
            or node.module.startswith(f"{self._module}.")
        ):
            return
        for alias in node.names:
            if alias.name == "*":
                self._record()
            elif alias.name in self._targets:
                self._names.add(alias.asname or alias.name)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self._names:
            self._record()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in self._targets:
            self._record()
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """A patch target names the minter's draw as a string, not a name."""
        if isinstance(node.value, str) and _names_one_of(
            node.value, self._targets
        ):
            self._record()


def _sites_in(tree: ast.AST) -> set[str]:
    finder = _NameSites(_RANDOM_UUID_NAMES, "uuid")
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
@pytest.mark.spec("OID-01-012")
def test_no_function_but_the_system_id_source_draws_a_random_uuid():
    sites = _random_uuid_sites()
    assert MINTER_SITE in sites, (
        "the scan no longer sees the system id source draw a UUID; "
        "fix the scan before trusting it"
    )
    assert sites - {MINTER_SITE} == set(NON_ID_RANDOM_UUID_EXEMPTIONS), (
        "a function outside the system id source names uuid1/uuid4: mint "
        "object ids with new_object_id (OID-01-004), supply repeatable ids "
        "through install_id_source (OID-01-011, OID-01-012), or list a non-id use in "
        "NON_ID_RANDOM_UUID_EXEMPTIONS with its reason"
    )


def _system_source_sites() -> frozenset[tuple[str, str]]:
    """(path, enclosing function) of every ``vultron/`` use of the system source."""
    sites: set[tuple[str, str]] = set()
    for path, tree in _corpus.files_mentioning(
        *_SYSTEM_SOURCE, under=_VULTRON_ROOT
    ):
        finder = _NameSites(_SYSTEM_SOURCE, "vultron.core.models")
        finder.visit(tree)
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        sites.update((rel, site) for site in finder.sites)
    return frozenset(sites)


@pytest.mark.spec("OID-01-011")
@pytest.mark.parametrize(
    "source",
    [
        "from vultron.core.models._helpers import system_id_source\n"
        "x = system_id_source()\n",
        "from vultron.core.models._helpers.ids import system_id_source as s\n"
        "x = s()\n",
        "from vultron.core.models._helpers import ids\n"
        "x = ids.system_id_source()\n",
    ],
)
def test_the_scan_sees_every_way_of_naming_the_system_source(source: str):
    finder = _NameSites(_SYSTEM_SOURCE, "vultron.core.models")
    finder.visit(_corpus.parse_inline(source))
    assert finder.sites == {MODULE_SCOPE}


@pytest.mark.spec("OID-01-011")
def test_only_the_id_source_slot_names_the_system_source():
    assert _system_source_sites() == SYSTEM_SOURCE_SITES, (
        "code outside the id-source slot names system_id_source, so it draws "
        "past an installed id source: mint with new_object_id (OID-01-011)"
    )
