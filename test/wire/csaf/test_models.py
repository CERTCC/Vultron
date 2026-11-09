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
"""The generated CSAF models check a document against the pinned schema."""

import pytest
from pydantic import ValidationError

from test.wire.csaf._documents import minimal_csaf_document, section
from vultron.wire.csaf.models import CommonSecurityAdvisoryFramework


def test_the_models_accept_a_schema_valid_document() -> None:
    document = CommonSecurityAdvisoryFramework.model_validate(
        minimal_csaf_document()
    )

    assert document.document.title == "Example advisory"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("document", "csaf_version"), "2.0"),
        (("document", "distribution", "tlp", "label"), "PURPLE"),
        (("document", "unknown_property"), "x"),
    ],
    ids=["wrong-version", "unknown-tlp-label", "additional-property"],
)
def test_the_models_reject_a_schema_invalid_document(
    path: tuple[str, ...], value: str
) -> None:
    data = minimal_csaf_document()
    section(data, *path[:-1])[path[-1]] = value

    with pytest.raises(ValidationError):
        CommonSecurityAdvisoryFramework.model_validate(data)


def test_the_models_reject_a_document_without_its_document_section() -> None:
    data = minimal_csaf_document()
    del data["document"]

    with pytest.raises(ValidationError):
        CommonSecurityAdvisoryFramework.model_validate(data)
