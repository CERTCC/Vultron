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
"""The termination cause a ``Remove(EmbargoEvent)`` carries (Idea #4609).

ADR-0122 revision 7: the ``Remove`` carries the termination's why beside its
what, as ``terminationCause``, checked at the parse edge, so a replica copies
it from the ledger rather than recording the what alone (EMB-13-005).
"""

import pytest
from pydantic import ValidationError

from vultron.core.models._helpers import now_utc
from vultron.core.models.embargo_termination import EmbargoTermination
from vultron.core.states.embargo_register import TerminationReason
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import remove_embargo_from_case_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

OWNER = "https://example.org/users/owner"
VENDOR = "https://example.org/users/vendor"
CASE = "https://example.org/cases/tc-wire"

_NEW_CAUSES = [
    {"kind": "FIX_READY", "vendors": [VENDOR]},
    {"kind": "FIX_DEPLOYED"},
    {"kind": "OTHER"},
]


@pytest.mark.xfail(
    strict=True,
    raises=ValidationError,
    reason=(
        "EMB-13-004: only the THREAT_SIGNAL cause is defined yet."
        " Tracked by #4857."
    ),
)
@pytest.mark.spec("EMB-13-004")
@pytest.mark.parametrize("cause", _NEW_CAUSES, ids=lambda c: c["kind"])
def test_an_early_termination_records_each_new_cause_kind(
    cause: dict[str, object],
) -> None:
    recorded = EmbargoTermination.model_validate(
        {"reason": TerminationReason.EARLY, "cause": cause}
    )

    assert recorded.model_dump(mode="json")["cause"] == cause
    with pytest.raises(ValidationError):
        EmbargoTermination.model_validate(
            {"reason": TerminationReason.END_TIME_REACHED, "cause": cause}
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EMB-13-005: the termination Remove does not carry terminationCause"
        " yet. Tracked by #4857."
    ),
)
@pytest.mark.spec("EMB-13-005")
def test_parse_edge_promotes_a_carried_cause_onto_the_event() -> None:
    embargo = as_EmbargoEvent(context=CASE, end_time=now_utc())
    activity = remove_embargo_from_case_activity(
        embargo, origin=CASE, actor=OWNER, reason=TerminationReason.EARLY
    )
    body = activity.model_dump(mode="json", by_alias=True, exclude_none=True)
    body["terminationCause"] = {"kind": "FIX_DEPLOYED"}

    event = extract_event(parse_activity(body))

    cause = event.model_dump(mode="json").get("termination_cause")
    assert cause is not None and cause["kind"] == "FIX_DEPLOYED"
