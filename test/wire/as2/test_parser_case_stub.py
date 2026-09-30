#!/usr/bin/env python

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

"""An enriched case stub is parsed as a stub (CM-17-002, #2624).

The parser used to recognise a ``VulnerabilityCase`` stub by a hand-kept key
allowlist that predated the CM-17-002 enrichment, so a stub carrying
``activeEmbargo`` and ``caseStatus`` was typed as a full case — and refused
for those very keys.  The allowlist is now derived from the stub class.
"""

import json

from vultron.core.models._helpers import days_from_now_utc
from vultron.wire.as2.parser import (
    _VULNERABILITY_CASE_STUB_KEYS,
    _inline_vocab_class,
    parse_activity,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)

_CASE_ID = "https://example.org/cases/case-stub"
_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"


def _enriched_stub() -> dict:
    return {
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
        "type": "VulnerabilityCase",
        "id": _CASE_ID,
        "activeEmbargo": {
            "type": "EmbargoEvent",
            "id": f"{_CASE_ID}/embargoes/e0",
            "context": _CASE_ID,
            "endTime": days_from_now_utc(30).isoformat(),
        },
        "caseStatus": {
            "type": "CaseStatus",
            "context": _CASE_ID,
            "em": "ACTIVE",
        },
    }


def test_stub_keys_are_derived_from_the_stub_class():
    """The stub's own fields, in wire spelling, plus identity — nothing else."""
    assert _VULNERABILITY_CASE_STUB_KEYS == frozenset(
        {
            "@context",
            "id",
            "type",
            "summary",
            "published",
            "updated",
            "activeEmbargo",
            "caseStatus",
        }
    )
    # Inherited AS2 fields a full case also carries are deliberately absent,
    # so a minimal full case is not mistaken for a stub.
    assert "name" not in _VULNERABILITY_CASE_STUB_KEYS


def test_minimal_stub_is_still_a_stub():
    assert (
        _inline_vocab_class({"type": "VulnerabilityCase", "id": _CASE_ID})
        is as_VulnerabilityCaseStub
    )


def test_enriched_stub_is_a_stub():
    assert _inline_vocab_class(_enriched_stub()) is as_VulnerabilityCaseStub


def test_a_full_case_is_not_a_stub():
    full = {"type": "VulnerabilityCase", "id": _CASE_ID, "name": "a case"}
    assert _inline_vocab_class(full) is not as_VulnerabilityCaseStub


def test_an_invite_with_an_enriched_stub_target_parses():
    """The invitee receives the embargo terms it is asked to consent to."""
    body = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Invite",
        "id": "urn:uuid:invite-enriched",
        "actor": _ACTOR,
        "to": [_INVITEE],
        "published": days_from_now_utc(0).isoformat(),
        "object": {"type": "Organization", "id": _INVITEE},
        "target": _enriched_stub(),
        "context": _CASE_ID,
    }
    activity = parse_activity(json.loads(json.dumps(body)))
    target = activity.target
    assert isinstance(target, as_VulnerabilityCaseStub)
    assert target.active_embargo is not None
    assert target.case_status is not None
