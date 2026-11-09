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
"""Ratchet: a response activity built without ``inReplyTo`` still names what it answers.

RF-08-002 puts the ``inReplyTo`` rule in a ``model_validator`` on every response
class, and RF-08-003 says no response may be built with that field missing.  A
test that builds two classes cannot show that: a new response class without the
validator would pass it.  This ratchet finds every ``as_Accept``, ``as_Reject``,
``as_TentativeAccept`` and ``as_TentativeReject`` subclass in
``vultron/wire/as2/vocab/activities/``, and the responses listed in
``_RESPONSES_BY_MEANING`` whose verb is not an answer.  It builds each one
again from its vocab example with ``inReplyTo`` removed, and checks the
result.  A class that refuses the body because ``inReplyTo`` is missing also
meets RF-08-003.

The classes that do not meet the rule yet are listed by name in
``_KNOWN_GAP``, owned by #5641.  The ratchet fails when a listed class starts to
meet the rule, so that the record does not go stale, and when a class that is
not listed does not meet it.
"""

import importlib
import inspect
import pkgutil
from typing import Any

import pytest
from pydantic import ValidationError

import vultron.wire.as2.vocab.activities as activities_pkg
from test.architecture._vocab_example_corpus import activity_examples
from vultron.wire.as2.vocab.activities.case.rm import (
    _RmCloseCaseActivity,
    _RmRejectCloseCaseActivity,
)
from vultron.wire.as2.vocab.activities.embargo import (
    _ActivateEmbargoActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Reject,
    as_TentativeAccept,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.examples.case import case, vendor

_RESPONSE_BASES = (
    as_Accept,
    as_Reject,
    as_TentativeAccept,
    as_TentativeReject,
)

#: Responses whose verb is not an answer.  The case owner's activation is an
#: ``Add`` of the embargo to the case (ADR-0180), yet it decides the proposal
#: an ``Invite(EmbargoEvent)`` made, and names that Invite in ``inReplyTo``.
_RESPONSES_BY_MEANING: tuple[type[Any], ...] = (_ActivateEmbargoActivity,)

# Response classes that build with no ``inReplyTo`` today.
# owner: #5641
_KNOWN_GAP = frozenset(
    {
        "_AcceptActorRecommendationActivity",
        "_RejectActorRecommendationActivity",
        "_AcceptCaseParticipantOfferActivity",
        "_RejectCaseParticipantOfferActivity",
        "_RmValidateReportActivity",
        "_RmInvalidateReportActivity",
        "_RmCloseReportActivity",
        "_AcceptCaseParticipantRoleActivity",
        "_RejectCaseParticipantRoleActivity",
        "_AcceptCaseOwnershipTransferActivity",
        "_RejectCaseOwnershipTransferActivity",
        "_EmAcceptEmbargoActivity",
        "_EmRejectEmbargoActivity",
        "_RejectLogEntryActivity",
    }
)


def _response_classes() -> dict[str, type[Any]]:
    found: dict[str, type[Any]] = {}
    # Recursive: a split module is a subpackage whose classes live in its
    # submodules, which a flat scan would silently drop.
    for info in pkgutil.walk_packages(
        activities_pkg.__path__, f"{activities_pkg.__name__}."
    ):
        module = importlib.import_module(info.name)
        for name, value in vars(module).items():
            if (
                inspect.isclass(value)
                and value.__module__ == module.__name__
                and (
                    issubclass(value, _RESPONSE_BASES)
                    or value in _RESPONSES_BY_MEANING
                )
            ):
                found[name] = value
    return found


def _samples() -> dict[str, Any]:
    """One built instance per response class, from the vocab examples."""
    samples: dict[str, Any] = {}
    for activity in activity_examples().values():
        samples.setdefault(type(activity).__name__, activity)
    # The decline of an owner's close has no vocab example.
    close = _RmCloseCaseActivity(actor=vendor().id_, object_=case())
    samples.setdefault(
        _RmRejectCloseCaseActivity.__name__,
        _RmRejectCloseCaseActivity(
            actor="https://example.org/case-actor", object_=close
        ),
    )
    return samples


_CLASSES = _response_classes()
_SAMPLES = _samples()


def _names_what_it_answers(cls: type[Any], sample: Any) -> bool:
    """Whether *cls*, built from *sample* without ``inReplyTo``, still has one."""
    body = sample.model_dump(by_alias=True, mode="json", exclude_none=True)
    body.pop("inReplyTo", None)
    try:
        rebuilt = cls.model_validate(body)
    except ValidationError as exc:
        return any(error["loc"] == ("inReplyTo",) for error in exc.errors())
    return rebuilt.in_reply_to is not None


def test_the_scan_finds_the_response_classes() -> None:
    """Non-vacuity: the scan sees the classes the rule is about."""
    assert "_RmAcceptInviteToCaseActivity" in _CLASSES
    assert "_EmAcceptEmbargoActivity" in _CLASSES
    assert "_ActivateEmbargoActivity" in _CLASSES
    assert set(_CLASSES) >= _KNOWN_GAP, sorted(_KNOWN_GAP - set(_CLASSES))


def test_every_response_class_has_a_sample() -> None:
    missing = sorted(set(_CLASSES) - set(_SAMPLES))
    assert missing == [], f"no vocab example builds {missing}"


@pytest.mark.spec("RF-08-002")
@pytest.mark.spec("RF-08-003")
@pytest.mark.spec("VAM-05-008")
@pytest.mark.spec("VAM-05-009")
@pytest.mark.parametrize("name", sorted(set(_CLASSES) - _KNOWN_GAP))
def test_a_response_built_without_in_reply_to_names_what_it_answers(
    name: str,
) -> None:
    assert _names_what_it_answers(_CLASSES[name], _SAMPLES[name]), (
        f"{name} builds with no inReplyTo (RF-08-002, RF-08-003)"
    )


@pytest.mark.parametrize("name", sorted(_KNOWN_GAP))
def test_a_known_gap_class_still_builds_without_in_reply_to(name: str) -> None:
    """The record stays current: a fixed class leaves ``_KNOWN_GAP`` (#5641)."""
    assert not _names_what_it_answers(_CLASSES[name], _SAMPLES[name]), (
        f"{name} now sets inReplyTo; remove it from _KNOWN_GAP (#5641)"
    )
