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
"""Tests for the shared object-id minter — OID-01-001, OID-01-004."""

import re

from vultron.core.models._helpers import URN_UUID_PREFIX, new_object_id

_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
)


class TestNewObjectId:
    def test_default_is_urn_uuid_with_a_version_4_uuid(self):
        id_ = new_object_id()
        assert id_.startswith(URN_UUID_PREFIX)
        assert _UUID_PATTERN.fullmatch(id_.removeprefix(URN_UUID_PREFIX))

    def test_default_is_not_a_bare_uuid(self):
        assert not _UUID_PATTERN.fullmatch(new_object_id())

    def test_prefix_form_appends_the_uuid_after_a_slash(self):
        prefix = "https://example.org/objects"
        id_ = new_object_id(prefix=prefix)
        head, _, tail = id_.rpartition("/")
        assert head == prefix
        assert _UUID_PATTERN.fullmatch(tail)
