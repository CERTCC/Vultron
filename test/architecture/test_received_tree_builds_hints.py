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
"""``_resolved_hints`` reads a received-tree factory's annotations the same
way whether or not they are quoted (PEP 649, #6054)."""

from typing import TYPE_CHECKING

from test.architecture._received_tree_builds import _resolved_hints
from vultron.core.models.case import VulnerabilityCase

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort


def _factory(
    case: VulnerabilityCase,
    port: TriggerActivityPort | None = None,
    ports: list[TriggerActivityPort] | None = None,
    quoted: "TriggerActivityPort | None" = None,  # noqa: UP037 - under test
) -> None:
    return None


def test_a_resolvable_annotation_is_the_real_type() -> None:
    assert _resolved_hints(_factory)["case"] is VulnerabilityCase


def test_a_type_checking_name_stays_its_source_text() -> None:
    hints = _resolved_hints(_factory)

    assert hints["port"] == "TriggerActivityPort | None"
    assert hints["quoted"] == "TriggerActivityPort | None"


def test_a_nested_type_checking_name_stays_its_source_text() -> None:
    assert _resolved_hints(_factory)["ports"] == (
        "list[TriggerActivityPort] | None"
    )
