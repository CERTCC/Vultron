#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import pytest

from vultron.adapters.driven.db_record import Record
from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
from vultron.wire.as2.vocab.base.objects.object_types import as_Note


@pytest.fixture(autouse=True)
def manage_storage_patch(request):
    """Manage the in-memory TinyDB patch around each test in this directory.

    Two roles:

    1. **Integration tests that verify file-backed storage**: temporarily
       restores ``TinyDbDataLayer.__init__`` to the real implementation so the
       test can exercise actual disk I/O, then re-applies the in-memory patch
       afterwards.

    2. **Reload recovery**: some tests call ``importlib.reload()`` on the
       datalayer module, which recreates ``TinyDbDataLayer`` as a fresh class
       object without the patch installed by ``pytest_configure``.  After every
       test this fixture checks whether the patch is still in place and
       re-applies it if not, preventing state leakage to subsequent tests.
    """
    import vultron.adapters.driven.datalayer_tinydb as _mod

    _cls = _mod.TinyDbDataLayer
    is_integration = request.node.get_closest_marker("integration") is not None

    if is_integration:
        original = getattr(_cls, "_test_original_init", None)
        if original is not None:
            # Restore real __init__ so this test can use file-backed storage.
            _cls.__init__ = original  # type: ignore[method-assign]

    yield

    # After the test, ensure the in-memory patch is active on the (possibly
    # reloaded) class.
    _cls = _mod.TinyDbDataLayer  # Re-fetch in case importlib.reload() ran.
    if getattr(_cls.__init__, "__name__", None) == "_in_memory_init":
        return  # Patch is still in place; nothing to do.

    _orig = getattr(_cls, "_test_original_init", _cls.__init__)

    def _in_memory_init(
        self: _mod.TinyDbDataLayer,
        db_path: "str | None" = None,
        actor_id: "str | None" = None,
    ) -> None:
        _orig(self, db_path=None, actor_id=actor_id)

    _cls._test_original_init = _orig  # type: ignore[attr-defined]
    _cls.__init__ = _in_memory_init  # type: ignore[method-assign]


@pytest.fixture
def tmp_db_file(tmp_path):
    db_path = tmp_path / "test_tinydb.json"
    # TinyDB will create the file when opened
    return db_path


@pytest.fixture
def dl(tmp_db_file):
    dl = TinyDbDataLayer(db_path=str(tmp_db_file))
    yield dl
    # teardown
    dl.clear_all()
    try:
        dl._db.close()
    except Exception:
        pass
    if tmp_db_file.exists():
        tmp_db_file.unlink()
    assert not tmp_db_file.exists()


@pytest.fixture
def record_factory():
    def _make(id_="12345", type_="test_table", data_=None):
        data = {"field": "value"} if data_ is None else data_
        return Record(id_=id_, type_=type_, data_=data)

    return _make


@pytest.fixture
def created_record(dl, record_factory):
    rec = record_factory()
    dl.create(rec)
    return rec


@pytest.fixture
def sample_record():
    return Record(id_="123", type_="TestType", data_={"key": "value"})


@pytest.fixture
def base_object():
    from vultron.wire.as2.vocab.base.base import as_Base

    return as_Base(id_="test-id", type_="BaseObject", name="Test Object")


@pytest.fixture
def note_object():
    return as_Note(content="Test Content")
