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

"""
Tests for vultron.wire.as2.vocab.base.utils — OID-01-001 through OID-01-004.
"""

import re
import uuid

import pytest

from vultron.wire.as2.vocab.base import utils
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import URN_UUID_PREFIX, generate_new_id

_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


class TestGenerateNewId:
    """Tests for generate_new_id() — OID-01-001."""

    def test_default_returns_urn_uuid_prefix(self):
        id_ = generate_new_id()
        assert id_.startswith(URN_UUID_PREFIX)

    def test_default_id_is_valid_urn_uuid(self):
        id_ = generate_new_id()
        uuid_part = id_.removeprefix(URN_UUID_PREFIX)
        assert _UUID_PATTERN.fullmatch(uuid_part) is not None

    def test_default_id_is_not_bare_uuid(self):
        id_ = generate_new_id()
        assert not _UUID_PATTERN.fullmatch(
            id_
        ), "generate_new_id() must not return a bare UUID"

    def test_prefix_appends_uuid(self):
        prefix = "https://example.org/objects"
        id_ = generate_new_id(prefix=prefix)
        assert id_.startswith(prefix + "/")
        uuid_part = id_.split("/")[-1]
        assert _UUID_PATTERN.fullmatch(uuid_part) is not None

    def test_each_call_returns_unique_id(self):
        ids = {generate_new_id() for _ in range(100)}
        assert len(ids) == 100


class TestAsBaseDefaultId:
    """Tests that as_Base objects receive URI-form IDs by default — OID-01-001."""

    def test_new_object_has_uri_form_id(self):
        obj = as_Base()
        assert obj.as_id.startswith(URN_UUID_PREFIX) or "://" in obj.as_id

    def test_new_object_id_is_not_bare_uuid(self):
        obj = as_Base()
        assert not _UUID_PATTERN.fullmatch(
            obj.as_id
        ), "as_id must not be a bare UUID"

    def test_two_objects_have_different_ids(self):
        obj1 = as_Base()
        obj2 = as_Base()
        assert obj1.as_id != obj2.as_id

    def test_explicit_https_id_is_accepted(self):
        explicit_id = "https://example.org/objects/abc123"
        obj = as_Base(as_id=explicit_id)
        assert obj.as_id == explicit_id

    def test_explicit_urn_uuid_id_is_accepted(self):
        explicit_id = f"urn:uuid:{uuid.uuid4()}"
        obj = as_Base(as_id=explicit_id)
        assert obj.as_id == explicit_id
