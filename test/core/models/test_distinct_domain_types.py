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

"""The seven CVD domain object types are not interchangeable (CM-05-001).

Each type's serialized form validates as itself and is refused as every
other, so a message that carries one where another is expected fails to
parse instead of being read as the wrong object.
"""

from itertools import permutations

import pytest
from pydantic import ValidationError

from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_record import VulnerabilityRecord

_CASE_ID = "https://example.org/cases/c1"
_VENDOR_ID = "https://example.org/users/vendor"


def _instances() -> dict[str, CoreObject]:
    return {
        "VulnerabilityReport": VulnerabilityReport(
            name="report",
            content="details",
            attributed_to="https://example.org/users/finder",
        ),
        "VulnerabilityCase": VulnerabilityCase(
            name="case", attributed_to=_VENDOR_ID
        ),
        "VulnerabilityRecord": VulnerabilityRecord(name="CVE-2401-0001"),
        "CaseReference": CaseReference(url="https://example.org/advisory"),
        "CaseActor": CaseActor(
            id_="https://example.org/actors/case-manager", name="CM"
        ),
        "CaseParticipant": CaseParticipant(
            attributed_to=_VENDOR_ID, context=_CASE_ID
        ),
        "ParticipantStatus": ParticipantStatus(context=_CASE_ID),
    }


_NAMES = list(_instances())


@pytest.mark.spec("CM-05-001")
@pytest.mark.parametrize("name", _NAMES)
def test_serialized_type_validates_as_itself(name: str) -> None:
    obj = _instances()[name]
    wire = obj.model_dump(mode="json", by_alias=True)
    assert type(obj).model_validate(wire).id_ == obj.id_


@pytest.mark.spec("CM-05-001")
@pytest.mark.parametrize(
    ("carried", "expected"), list(permutations(_NAMES, 2))
)
def test_serialized_type_is_refused_as_another(
    carried: str, expected: str
) -> None:
    instances = _instances()
    wire = instances[carried].model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError):
        type(instances[expected]).model_validate(wire)
