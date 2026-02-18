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

from vultron.api.v2.datalayer.db_record import Record
from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer


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
    from vultron.as_vocab.base.base import as_Base

    return as_Base(as_id="test-id", as_type="BaseObject", name="Test Object")


@pytest.fixture
def note_object():
    from vultron.as_vocab.base.objects.object_types import as_Note

    return as_Note(content="Test Content")
