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
"""``as_Link.href`` follows CS-08-001: if present, then non-empty.

A Link whose ``href`` is blank points nowhere, so the value is refused at
validation rather than carried inbound and dropped outbound (#3876 AC-3).
"""

import pytest
from pydantic import ValidationError

from test.support.blank_strings import BLANKS
from vultron.wire.as2.vocab.base.links import as_Link


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", BLANKS)
def test_link_rejects_blank_href(blank: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        as_Link(href=blank)
    assert "href" in str(exc_info.value)


@pytest.mark.spec("CS-08-001")
@pytest.mark.parametrize("blank", BLANKS)
def test_link_rejects_blank_href_from_wire(blank: str) -> None:
    with pytest.raises(ValidationError):
        as_Link.model_validate({"type": "Link", "href": blank})


def test_link_keeps_a_non_blank_href() -> None:
    link = as_Link(href="https://example.org/cases/1")
    assert link.href == "https://example.org/cases/1"


def test_link_href_stays_optional() -> None:
    """Absence is still allowed — the rule is "if present, then non-empty"."""
    assert as_Link().href is None
    assert as_Link(href=None).href is None
