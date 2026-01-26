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

from vultron.api.v2.datalayer.db_record import (
    Record,
    object_to_record,
    record_to_object,
)


# Fixtures for reused test objects
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


# Tests (atomic and with descriptive names)
def test_record_has_id_type_and_data_attributes(sample_record):
    assert sample_record.id_ == "123"
    assert sample_record.type_ == "TestType"
    assert sample_record.data_ == {"key": "value"}


def test_object_to_record_preserves_id_type_and_data_for_base_object(
    base_object,
):
    record = object_to_record(base_object)
    assert record.id_ == base_object.as_id
    assert record.type_ == base_object.as_type
    assert record.data_ == base_object.model_dump()


def test_object_to_record_returns_Record_for_note_object(note_object):
    record = object_to_record(note_object)
    assert isinstance(record, Record)


def test_record_to_object_reconstructs_note_and_preserves_id_type_and_data(
    note_object,
):
    record = object_to_record(note_object)
    reconstructed = record_to_object(record)
    # ensure type and class are preserved
    assert reconstructed.as_id == note_object.as_id
    assert reconstructed.as_type == note_object.as_type
    # ensure content/fields are preserved via model dump
    assert reconstructed.model_dump() == note_object.model_dump()
