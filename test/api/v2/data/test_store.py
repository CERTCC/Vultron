#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.api.v2.data import store
from vultron.as_vocab.base.base import as_Base


# NOTE: the ds fixture has been moved to
# test/api/v2/data/conftest.py so tests here can reuse it.


def test_get_datalayer_returns_datastore_instance():
    ds = store.get_datalayer()
    assert isinstance(ds, store.DataStore)


def test_create_persists_object_in_datastore(ds):
    test_obj = as_Base(name="Test Name")
    ds.create(test_obj)
    assert test_obj.as_id in ds


def test_read_returns_created_object(ds):
    test_obj = as_Base(name="Test Name")
    obj_id = test_obj.as_id
    ds.create(test_obj)
    retrieved = ds.read(obj_id)
    assert retrieved.name == "Test Name"


def test_update_changes_existing_object_and_read_reflects_change(ds):
    test_obj = as_Base(name="Test Name")
    obj_id = test_obj.as_id
    ds.create(test_obj)
    test_obj.name = "Updated Name"
    ds.update(obj_id, test_obj.model_dump())
    updated = ds.read(obj_id)
    assert updated.name == "Updated Name"


def test_delete_removes_existing_object(ds):
    test_obj = as_Base(name="Test Name")
    obj_id = test_obj.as_id
    ds.create(test_obj)
    ds.delete(obj_id)
    assert ds.read(obj_id) is None


def test_create_duplicate_raises_key_error(ds):
    test_obj = as_Base(name="Test Name")
    ds.create(test_obj)
    with pytest.raises(KeyError):
        ds.create(test_obj)


def test_delete_nonexistent_raises_key_error(ds):
    with pytest.raises(KeyError):
        ds.delete("nonexistent_id")


def test_update_nonexistent_raises_key_error(ds):
    with pytest.raises(KeyError):
        ds.update("nonexistent_id", {"name": "New Name"})


def test_all_returns_all_persisted_objects(ds):
    test_obj1 = as_Base(name="Test One")
    test_obj2 = as_Base(name="Test Two")
    ds.create(test_obj1)
    ds.create(test_obj2)
    all_items = ds.all()
    # all() should include the created ids
    assert len(all_items) >= 2
    assert test_obj1.as_id in all_items
    assert test_obj2.as_id in all_items
