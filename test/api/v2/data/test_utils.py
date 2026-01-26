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
import re

from vultron.api.v2.data import utils

_UUID_PATTERN = re.compile(
    "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def test_id_prefix_returns_expected_prefix_for_object_types(test_base_url):
    for object_type in ["Actor", "Activity", "Collection"]:
        expected_prefix = f"{test_base_url}{object_type}/"
        assert utils.id_prefix(object_type) == expected_prefix


def test_make_id_generates_id_with_uuid_suffix_and_expected_segments(
    test_base_url,
):
    for object_type in ["Actor", "Activity", "Collection"]:
        object_id = utils.make_id(object_type)
        assert object_id.startswith(f"{test_base_url}{object_type}/")
        # expect base_url + object_type + uuid (split may include empty segments if base_url has trailing slash)
        assert len(object_id.split("/")) >= 3
        uuid_part = object_id.split("/")[-1]
        assert _UUID_PATTERN.fullmatch(uuid_part) is not None


def test_parse_id_extracts_components_correctly(test_base_url):
    for object_type in ["Actor", "Activity", "Collection"]:
        object_id = utils.make_id(object_type)
        parsed = utils.parse_id(object_id)
        assert parsed["base_url"] == test_base_url
        assert parsed["object_type"] == object_type
        assert _UUID_PATTERN.fullmatch(parsed["object_id"]) is not None


def test_id_prefix_handles_base_url_without_trailing_slash(
    monkeypatch, test_base_url
):
    object_type = "Actor"
    monkeypatch.setattr(
        utils, "BASE_URL", "https://test.vultron.local"
    )  # no trailing slash
    expected_prefix = f"{test_base_url}{object_type}/"
    assert utils.id_prefix(object_type) == expected_prefix
