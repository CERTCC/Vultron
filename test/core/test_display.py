"""Unit tests for vultron.core.display.friendly_name (AC-5, SE-07-001)."""

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

from vultron.core.display import friendly_name
from vultron.core.models.base import VultronBase


class _NamedObj(VultronBase):
    """Minimal VultronBase subclass used in tests."""


# ---------------------------------------------------------------------------
# None input
# ---------------------------------------------------------------------------


def test_friendly_name_none_returns_dash():
    assert friendly_name(None) == "—"


# ---------------------------------------------------------------------------
# VultronBase with name field set
# ---------------------------------------------------------------------------


def test_friendly_name_object_with_name_returns_name():
    obj = _NamedObj.model_validate({"name": "Vendor"})
    assert friendly_name(obj) == "Vendor"


def test_friendly_name_object_with_name_ignores_id():
    obj = _NamedObj.model_validate(
        {"id": "http://vendor:7999/api/v2/actors/finder", "name": "Vendor"}
    )
    assert friendly_name(obj) == "Vendor"


# ---------------------------------------------------------------------------
# URI path-segment heuristic (string input)
# ---------------------------------------------------------------------------


def test_friendly_name_string_extracts_last_segment():
    assert friendly_name("http://vendor:7999/api/v2/actors/vendor") == "Vendor"


def test_friendly_name_string_drops_uuid_tokens():
    assert (
        friendly_name("http://actor:7999/actors/case-actor-a1b2c3d4e5f6")
        == "Case Actor"
    )


def test_friendly_name_string_handles_trailing_slash():
    assert (
        friendly_name("http://vendor:7999/api/v2/actors/finder/") == "Finder"
    )


def test_friendly_name_string_multi_word_segment():
    assert friendly_name("http://host/actors/case-manager") == "Case Manager"


def test_friendly_name_empty_string_returns_dash():
    assert friendly_name("") == "—"


# ---------------------------------------------------------------------------
# VultronBase without name — falls back to id_ heuristic
# ---------------------------------------------------------------------------


def test_friendly_name_object_without_name_uses_id_segment():
    obj = _NamedObj.model_validate(
        {"id": "http://vendor:7999/api/v2/actors/coordinator"}
    )
    assert friendly_name(obj) == "Coordinator"
