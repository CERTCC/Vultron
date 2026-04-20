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


from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.utils import (
    URN_UUID_PREFIX,
    generate_new_id,
    name_of,
)

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
        assert obj.id_.startswith(URN_UUID_PREFIX) or "://" in obj.id_

    def test_new_object_id_is_not_bare_uuid(self):
        obj = as_Base()
        assert not _UUID_PATTERN.fullmatch(
            obj.id_
        ), "id_ must not be a bare UUID"

    def test_two_objects_have_different_ids(self):
        obj1 = as_Base()
        obj2 = as_Base()
        assert obj1.id_ != obj2.id_

    def test_explicit_https_id_is_accepted(self):
        explicit_id = "https://example.org/objects/abc123"
        obj = as_Base(id_=explicit_id)
        assert obj.id_ == explicit_id

    def test_explicit_urn_uuid_id_is_accepted(self):
        explicit_id = f"urn:uuid:{uuid.uuid4()}"
        obj = as_Base(id_=explicit_id)
        assert obj.id_ == explicit_id


class TestNameOf:
    """Tests for the updated name_of() utility — DR-02."""

    def test_returns_string_unchanged(self):
        """name_of returns a plain string without any attribute lookup."""
        uri = "https://example.org/actors/alice"
        assert name_of(uri) == uri

    def test_returns_name_attribute_when_set(self):
        """name_of returns obj.name when it is not None."""
        from types import SimpleNamespace

        obj = SimpleNamespace(name="My Report", id_="urn:uuid:abc123")
        assert name_of(obj) == "My Report"

    def test_falls_back_to_href_when_name_is_none(self):
        """name_of returns href when name is None (AS2 Link objects)."""
        from types import SimpleNamespace

        link = SimpleNamespace(
            name=None,
            href="https://example.org/cases/1",
            id_="urn:uuid:link-id",
        )
        assert name_of(link) == "https://example.org/cases/1"

    def test_falls_back_to_id_when_name_and_href_are_none(self):
        """name_of returns id_ when name and href are both None."""
        from types import SimpleNamespace

        obj = SimpleNamespace(name=None, id_="urn:uuid:domain-obj-123")
        assert name_of(obj) == "urn:uuid:domain-obj-123"

    def test_falls_back_to_str_when_no_useful_attributes(self):
        """name_of falls back to str() when no recognizable attributes exist."""
        from types import SimpleNamespace

        obj = SimpleNamespace()
        result = name_of(obj)
        assert isinstance(result, str)

    def test_does_not_return_none_string(self):
        """name_of never returns the literal string 'None' for objects with id_."""
        from types import SimpleNamespace

        obj = SimpleNamespace(name=None, id_="urn:uuid:real-id")
        assert name_of(obj) != "None"


class TestSetNameUsesNameOf:
    """set_name() must use name_of() for target, origin, instrument — DR-02."""

    def test_set_name_target_uses_id_when_name_none(self):
        """Activity name must include target.id_, not a Pydantic repr."""
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        actor_id = "https://example.org/actors/alice"
        case_id = "https://example.org/cases/case-001"
        target_obj = as_Object(id_=case_id)  # name=None by default

        act = as_Add(actor=actor_id, target=target_obj, object_=None)
        assert act.name is not None
        assert case_id in act.name
        # Must not contain Pydantic/repr noise
        assert "type_=" not in act.name
        assert "context_=" not in act.name

    def test_set_name_target_uses_name_when_set(self):
        """Activity name includes target.name when target.name is not None."""
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        actor_id = "https://example.org/actors/alice"
        target_obj = as_Object(
            id_="https://example.org/cases/case-002", name="Demo Case"
        )

        act = as_Add(actor=actor_id, target=target_obj, object_=None)
        assert act.name is not None
        assert "Demo Case" in act.name
