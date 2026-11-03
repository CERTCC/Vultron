#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
import re

from vultron.adapters import utils
from vultron.core.models._helpers import URN_UUID_PREFIX, new_object_id

_UUID_PATTERN = re.compile(
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def test_parse_id_extracts_components_correctly():
    base_url = "https://test.vultron.local/"
    for object_type in ["Actor", "Activity", "Collection"]:
        object_id = new_object_id(prefix=f"{base_url}{object_type}")
        parsed = utils.parse_id(object_id)
        assert parsed["base_url"] == base_url
        assert parsed["object_type"] == object_type
        assert _UUID_PATTERN.fullmatch(parsed["object_id"]) is not None


def test_parse_id_splits_a_urn_uuid_id():
    object_id = new_object_id()
    parsed = utils.parse_id(object_id)
    assert parsed["base_url"] == URN_UUID_PREFIX
    assert parsed["object_type"] is None
    assert object_id == f"{URN_UUID_PREFIX}{parsed['object_id']}"
