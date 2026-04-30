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
"""
Unit tests for vultron.wire.as2.factories.report.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-03-001: Factory function names are snake_case equivalents of the class.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions are re-exported from factories/__init__.py.
"""

import pytest

from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    rm_close_report_activity,
    rm_create_report_activity,
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Person
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)

_ACTOR_URI = "https://example.org/actors/alice"
_RECIPIENT_URI = "https://example.org/actors/vendor"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_report() -> VulnerabilityReport:
    return VulnerabilityReport(name="Test CVE report")


@pytest.fixture
def sample_actor() -> as_Person:
    return as_Person(name="Alice", id_=_ACTOR_URI)


@pytest.fixture
def sample_offer(sample_report, sample_actor) -> as_Offer:
    """Offer produced by the factory — used as input to validate/invalidate/close."""
    return rm_submit_report_activity(
        report=sample_report, to=_RECIPIENT_URI, actor=sample_actor
    )


# ---------------------------------------------------------------------------
# rm_create_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_create_report_returns_create(sample_report, sample_actor):
    result = rm_create_report_activity(
        report=sample_report, actor=sample_actor
    )
    assert isinstance(result, as_Create)


@pytest.mark.spec("AF-01-002")
def test_rm_create_report_object_is_report(sample_report, sample_actor):
    result = rm_create_report_activity(
        report=sample_report, actor=sample_actor
    )
    assert result.object_ == sample_report


def test_rm_create_report_kwargs_actor_forwarded(sample_report, sample_actor):
    """``actor`` kwarg is passed through to the constructor."""
    result = rm_create_report_activity(
        report=sample_report, actor=sample_actor
    )
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_create_report_invalid_report_raises(sample_actor):
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_create_report_activity(
            report="not-a-report",  # type: ignore[arg-type]
            actor=sample_actor,
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_submit_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_submit_report_returns_offer(sample_report, sample_actor):
    result = rm_submit_report_activity(
        report=sample_report, to=_RECIPIENT_URI, actor=sample_actor
    )
    assert isinstance(result, as_Offer)


@pytest.mark.spec("AF-01-002")
def test_rm_submit_report_object_is_report(sample_report, sample_actor):
    result = rm_submit_report_activity(
        report=sample_report, to=_RECIPIENT_URI, actor=sample_actor
    )
    assert result.object_ == sample_report


def test_rm_submit_report_to_is_normalized_list(sample_report, sample_actor):
    """The factory normalizes ``to`` to a single-element list."""
    result = rm_submit_report_activity(
        report=sample_report, to=_RECIPIENT_URI, actor=sample_actor
    )
    assert result.to == [_RECIPIENT_URI]


def test_rm_submit_report_to_accepts_actor_object(sample_report, sample_actor):
    """``to`` can be an actor object as well as a string."""
    recipient = as_Person(name="Vendor", id_=_RECIPIENT_URI)
    result = rm_submit_report_activity(
        report=sample_report, to=recipient, actor=sample_actor
    )
    assert result.to == [recipient]


def test_rm_submit_report_kwargs_actor_forwarded(sample_report, sample_actor):
    result = rm_submit_report_activity(
        report=sample_report, to=_RECIPIENT_URI, actor=sample_actor
    )
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_submit_report_invalid_report_raises(sample_actor):
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_submit_report_activity(
            report="not-a-report",  # type: ignore[arg-type]
            to=_RECIPIENT_URI,
            actor=sample_actor,
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_read_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_read_report_returns_read(sample_report, sample_actor):
    result = rm_read_report_activity(report=sample_report, actor=sample_actor)
    assert isinstance(result, as_Read)


@pytest.mark.spec("AF-01-002")
def test_rm_read_report_object_is_report(sample_report, sample_actor):
    result = rm_read_report_activity(report=sample_report, actor=sample_actor)
    assert result.object_ == sample_report


def test_rm_read_report_kwargs_actor_forwarded(sample_report, sample_actor):
    result = rm_read_report_activity(report=sample_report, actor=sample_actor)
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_read_report_invalid_report_raises(sample_actor):
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_read_report_activity(
            report="not-a-report",  # type: ignore[arg-type]
            actor=sample_actor,
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_validate_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_validate_report_returns_accept(sample_offer, sample_actor):
    result = rm_validate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert isinstance(result, as_Accept)


@pytest.mark.spec("AF-01-002")
def test_rm_validate_report_object_is_offer(sample_offer, sample_actor):
    result = rm_validate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert result.object_ == sample_offer


def test_rm_validate_report_kwargs_actor_forwarded(sample_offer, sample_actor):
    result = rm_validate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_validate_report_plain_offer_raises(sample_report, sample_actor):
    """A plain as_Offer (not from rm_submit_report_activity) must fail."""
    plain_offer = as_Offer(
        actor=None, object_=sample_report  # wrong inner object type
    )
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_validate_report_activity(offer=plain_offer, actor=sample_actor)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_invalidate_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_invalidate_report_returns_tentative_reject(
    sample_offer, sample_actor
):
    result = rm_invalidate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert isinstance(result, as_TentativeReject)


@pytest.mark.spec("AF-01-002")
def test_rm_invalidate_report_object_is_offer(sample_offer, sample_actor):
    result = rm_invalidate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert result.object_ == sample_offer


def test_rm_invalidate_report_kwargs_actor_forwarded(
    sample_offer, sample_actor
):
    result = rm_invalidate_report_activity(
        offer=sample_offer, actor=sample_actor
    )
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_invalidate_report_plain_offer_raises(sample_report, sample_actor):
    plain_offer = as_Offer(
        actor=None, object_=sample_report  # wrong inner object type
    )
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_invalidate_report_activity(offer=plain_offer, actor=sample_actor)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_close_report_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_close_report_returns_reject(sample_offer, sample_actor):
    result = rm_close_report_activity(offer=sample_offer, actor=sample_actor)
    assert isinstance(result, as_Reject)


@pytest.mark.spec("AF-01-002")
def test_rm_close_report_object_is_offer(sample_offer, sample_actor):
    result = rm_close_report_activity(offer=sample_offer, actor=sample_actor)
    assert result.object_ == sample_offer


def test_rm_close_report_kwargs_actor_forwarded(sample_offer, sample_actor):
    result = rm_close_report_activity(offer=sample_offer, actor=sample_actor)
    assert result.actor == sample_actor


@pytest.mark.spec("AF-04-001")
def test_rm_close_report_plain_offer_raises(sample_report, sample_actor):
    plain_offer = as_Offer(
        actor=None, object_=sample_report  # wrong inner object type
    )
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_close_report_activity(offer=plain_offer, actor=sample_actor)
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_report_factories_importable_from_package():
    """All report factory functions must be importable from the factories package."""
    from vultron.wire.as2.factories import (  # noqa: F401
        rm_close_report_activity,
        rm_create_report_activity,
        rm_invalidate_report_activity,
        rm_read_report_activity,
        rm_submit_report_activity,
        rm_validate_report_activity,
    )
