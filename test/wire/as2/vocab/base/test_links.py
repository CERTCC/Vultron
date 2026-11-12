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
"""``as_Link.href`` is required and non-empty (MV-04-005, CS-08-001).

A Link whose ``href`` is blank or absent points nowhere, so the value is
refused at validation rather than carried inbound and dropped outbound
(#3876 AC-3, #5715).
"""

import pytest
from pydantic import ValidationError

from test.support.blank_strings import BLANKS
from test.support.objects import with_times
from vultron.wire.as2.vocab.base.links import as_Link, as_Mention


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
        as_Link.model_validate(
            with_times(as_Link, {"type": "Link", "href": blank})
        )


def test_link_keeps_a_non_blank_href() -> None:
    link = as_Link(href="https://example.org/cases/1")
    assert link.href == "https://example.org/cases/1"


@pytest.mark.spec("MV-04-005")
@pytest.mark.parametrize("link_cls", [as_Link, as_Mention])
@pytest.mark.parametrize(
    "data", [{}, {"id": "https://example.org/alice"}, {"href": None}]
)
def test_a_link_without_an_href_is_refused(
    link_cls: type[as_Link], data: dict
) -> None:
    """A Link names its resource by ``href`` (AS2 § 3.2); one without names none.

    Refused when built here as well as when received, so an untyped dict in an
    object-or-link slot that fails its object class cannot fall through the
    union to an empty Link (#5715).
    """
    with pytest.raises(ValidationError, match="href"):
        link_cls.model_validate(data)
    with pytest.raises(ValidationError, match="href"):
        link_cls(**data)
