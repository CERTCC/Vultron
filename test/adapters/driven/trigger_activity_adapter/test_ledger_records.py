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

"""Tests for the CASE_MANAGER's ledger-record activities (``ledger.py``).

Each ``record_*`` method builds the activity a ledger entry records, as the
CASE_MANAGER, and seals it; the sealed blob is the entry's
``payloadSnapshot``, verbatim (VM-08-003, CLP-07-013).  These replace the
snapshot dicts core used to assemble itself (#3743).
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from test.support.ledger_labels import registry_label
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.trigger_activity_adapter.ledger import (
    _LedgerRecordsMixin,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _validate_canonical_entry,
)
from vultron.core.models._helpers import parse_published
from vultron.core.models.actor import VultronService
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.report import VulnerabilityReport
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)

VENDOR_ID = "https://example.org/actors/vendor"
EMBARGO_ID = "https://example.org/embargoes/urn:uuid:embargo-1"


def _consent_row(state: EmbargoConsentState) -> EmbargoConsent:
    """The vendor's consent row, as a consent-row entry carries it."""
    return EmbargoConsent(
        embargo_id=EMBARGO_ID, state=state, attributed_to=VENDOR_ID
    )


CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/urn:uuid:snapshot-test"
REPORT_ID = "https://example.org/reports/urn:uuid:report-1"
OFFER_ID = "https://example.org/activities/urn:uuid:offer-1"
#: A creation-time embargo, built once so two builds of its record compare.
_EMBARGO = EmbargoEvent(
    id_=f"{CASE_ID}/embargo_events/default",
    context=CASE_ID,
    start_time=datetime(2026, 1, 1, tzinfo=UTC),
    end_time=datetime(2026, 4, 1, tzinfo=UTC),
)


@pytest.fixture
def vendor_actor(dl):
    actor = VultronService(id_=VENDOR_ID, name="Vendor Co")
    dl.create(actor)
    return actor


@pytest.fixture
def report(dl):
    r = VulnerabilityReport(id_=REPORT_ID, name="Test Report")
    dl.create(r)
    return r


@pytest.fixture
def participant(dl):
    p = CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        name="Vendor participant",
    )
    dl.create(p)
    return p


@pytest.fixture
def case(dl, vendor_actor, report, participant):
    c = VulnerabilityCase(
        id_=CASE_ID, attributed_to=VENDOR_ID, name="Snapshot Test Case"
    )
    c.vulnerability_reports.append(REPORT_ID)
    c.add_participant(participant)
    dl.save(c)
    return c


Recipe = Callable[[TriggerActivityAdapter], tuple[str, str]]


@pytest.fixture
def recipes(case, report, participant) -> dict[str, Recipe]:
    """One call per ``record_*`` method, keyed by method name."""
    status = case.case_statuses[0]
    assert isinstance(status, CaseStatus)
    return {
        "record_case_created": lambda a: a.record_case_created(
            case_id=CASE_ID, actor=CASE_ACTOR_ID
        ),
        "record_report_added_to_case": lambda a: a.record_report_added_to_case(
            report_id=REPORT_ID,
            case_id=CASE_ID,
            actor=CASE_ACTOR_ID,
            offer_id=OFFER_ID,
            offer_actor_id=VENDOR_ID,
        ),
        "record_participant_status_added": lambda a: (
            a.record_participant_status_added(
                status=participant.participant_statuses[0],
                participant=participant,
                case_id=CASE_ID,
                actor=CASE_ACTOR_ID,
            )
        ),
        "record_case_status_added": lambda a: a.record_case_status_added(
            status=status, case_id=CASE_ID, actor=CASE_ACTOR_ID
        ),
        "record_case_participant_created": lambda a: (
            a.record_case_participant_created(
                participant=participant, case_id=CASE_ID, actor=CASE_ACTOR_ID
            )
        ),
        "record_case_participant_updated": lambda a: (
            a.record_case_participant_updated(
                participant=participant,
                case_id=CASE_ID,
                actor=CASE_ACTOR_ID,
                cause_id=OFFER_ID,
            )
        ),
        "record_embargo_event_created": lambda a: (
            a.record_embargo_event_created(
                embargo=_EMBARGO, case_id=CASE_ID, actor=CASE_ACTOR_ID
            )
        ),
        "record_embargo_consent_created": lambda a: (
            a.record_embargo_consent_created(
                row=_consent_row(EmbargoConsentState.UNINVITED),
                case_id=CASE_ID,
                actor=CASE_ACTOR_ID,
            )
        ),
        "record_embargo_consent_updated": lambda a: (
            a.record_embargo_consent_updated(
                row=_consent_row(EmbargoConsentState.AGREED),
                case_id=CASE_ID,
                actor=CASE_ACTOR_ID,
                cause_id=OFFER_ID,
            )
        ),
        "record_case_owner_updated": lambda a: a.record_case_owner_updated(
            case=case, actor=CASE_ACTOR_ID, cause_id=OFFER_ID
        ),
        "record_case_announced": lambda a: a.record_case_announced(
            case_id=CASE_ID,
            actor=CASE_ACTOR_ID,
            object_id=CASE_ID,
        ),
    }


#: The ``(type, object type)`` each recipe records, and its semantic type.
_SHAPES: dict[str, tuple[str, str, str]] = {
    "record_case_created": ("Create", "VulnerabilityCase", "create_case"),
    "record_report_added_to_case": (
        "Add",
        "VulnerabilityReport",
        "add_report_to_case",
    ),
    "record_participant_status_added": (
        "Add",
        "ParticipantStatus",
        "add_participant_status_to_participant",
    ),
    "record_case_status_added": (
        "Add",
        "CaseStatus",
        "add_case_status_to_case",
    ),
    "record_case_participant_created": (
        "Create",
        "CaseParticipant",
        "create_case_participant",
    ),
    "record_case_participant_updated": (
        "Update",
        "CaseParticipant",
        "update_case_participant",
    ),
    "record_embargo_event_created": (
        "Create",
        "EmbargoEvent",
        "create_embargo_event",
    ),
    "record_embargo_consent_created": (
        "Create",
        "EmbargoConsent",
        "create_embargo_consent",
    ),
    "record_embargo_consent_updated": (
        "Update",
        "EmbargoConsent",
        "update_embargo_consent",
    ),
    "record_case_owner_updated": (
        "Update",
        "VulnerabilityCase",
        "update_case_owner",
    ),
    "record_case_announced": (
        "Announce",
        "VulnerabilityCase",
        "announce_vulnerability_case",
    ),
}


def _snapshot(recipe: Recipe, adapter: TriggerActivityAdapter) -> Any:
    activity_id, blob = recipe(adapter)
    snapshot = json.loads(blob)
    assert snapshot["id"] == activity_id
    return snapshot


def test_every_record_method_has_a_recipe(recipes):
    """Ratchet: a new ``record_*`` method is covered here."""
    exported = {
        name
        for name in vars(_LedgerRecordsMixin)
        if name.startswith("record_")
    }
    assert exported == set(recipes) == set(_SHAPES)


@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.parametrize("method", sorted(_SHAPES))
def test_the_record_is_the_case_managers_own_activity(
    adapter, recipes, method
):
    snapshot = _snapshot(recipes[method], adapter)
    activity_type, object_type, _ = _SHAPES[method]
    assert snapshot["type"] == activity_type
    assert snapshot["actor"] == CASE_ACTOR_ID
    assert snapshot["object"]["type"] == object_type
    assert snapshot["context"] == CASE_ID
    assert "to" not in snapshot, "the ledger fan-out delivers it"


@pytest.mark.spec("CLP-07")
@pytest.mark.spec("CLP-12-002")
@pytest.mark.parametrize("method", sorted(_SHAPES))
def test_the_record_passes_the_canonical_guard(adapter, recipes, method):
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_snapshot(recipes[method], adapter),
        semantic_type=_SHAPES[method][2],
    )


@pytest.mark.spec("SE-02-001")
@pytest.mark.spec("CLP-07-013")
@pytest.mark.parametrize("method", sorted(_SHAPES))
def test_the_registry_labels_the_record_with_its_entry_type(
    adapter, recipes, method
):
    """Each record's payload is labelled with the type its entry commits.

    The CASE_MANAGER's own acts are registry entries too (ADR-0140, #4724
    AC-1), so the semantic type an entry stores is the registry's label for
    the activity the record built, never a name of its own.
    """
    snapshot = _snapshot(recipes[method], adapter)
    assert registry_label(snapshot) == _SHAPES[method][2]


@pytest.mark.spec("CLP-07-011")
@pytest.mark.parametrize("method", sorted(_SHAPES))
def test_the_record_carries_a_parseable_published(adapter, recipes, method):
    """A snapshot without ``published`` is not the verbatim activity (#2824)."""
    published = _snapshot(recipes[method], adapter).get("published")
    assert published and parse_published(published) is not None


@pytest.mark.spec("ID-04-004")
@pytest.mark.parametrize("method", sorted(_SHAPES))
def test_a_rerun_hands_back_the_body_first_sealed(adapter, recipes, method):
    """The id is derived from what changed, so a retry commits one entry."""
    assert recipes[method](adapter) == recipes[method](adapter)


@pytest.mark.parametrize(
    "method",
    [
        "record_case_created",
        "record_report_added_to_case",
        "record_participant_status_added",
        "record_case_status_added",
        "record_case_participant_updated",
        "record_case_owner_updated",
        "record_embargo_event_created",
        "record_embargo_consent_created",
        "record_embargo_consent_updated",
    ],
)
def test_the_object_revalidates_through_its_wire_class(
    adapter, recipes, method
):
    """Every carried object is wire-reconstitutable (AC-7 of #1777)."""
    from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

    obj = _snapshot(recipes[method], adapter)["object"]
    find_in_vocabulary(obj["type"]).model_validate(obj)


@pytest.mark.spec("CP-01-007")
def test_the_report_record_carries_its_offer_provenance(adapter, recipes):
    snapshot = _snapshot(recipes["record_report_added_to_case"], adapter)
    assert snapshot["offerId"] == OFFER_ID
    assert snapshot["offerActorId"] == VENDOR_ID


def test_the_report_record_omits_absent_offer_provenance(adapter, case):
    _, blob = adapter.record_report_added_to_case(
        report_id=REPORT_ID, case_id=CASE_ID, actor=CASE_ACTOR_ID
    )
    assert not {"offerId", "offerActorId"} & set(json.loads(blob))


def test_participant_status_carries_no_consent_keys(adapter, recipes):
    """Consent lives on the participant rows (ADR-0122)."""
    snapshot = _snapshot(recipes["record_participant_status_added"], adapter)
    assert not {"consent", "emConsentState", "embargoAdherence"} & set(
        snapshot["object"]
    )


@pytest.mark.spec("AKM-02-004")
@pytest.mark.spec("CBT-01-007")
def test_an_announced_case_carries_its_participants_and_reports(
    adapter, recipes
):
    obj = _snapshot(recipes["record_case_announced"], adapter)["object"]
    assert all(isinstance(p, dict) for p in obj["caseParticipants"])
    assert all(isinstance(r, dict) for r in obj["vulnerabilityReports"])


@pytest.mark.spec("CLP-07-013")
def test_the_genesis_record_carries_the_case_as_stored(adapter, case):
    """Each participant and report has an entry of its own (ADR-0124)."""
    _, blob = adapter.record_case_created(case_id=CASE_ID, actor=CASE_ACTOR_ID)
    obj = json.loads(blob)["object"]
    assert VulnerabilityCase.model_validate(obj) == case


# Allow-listed camelCase-looking dict-literal keys in vultron/core/: the
# case-state pattern strings, which contain capitals but are not wire keys.
#
# The general form of this narrow scan lives in
# ``test/architecture/test_core_no_as2_spellings.py``, which covers every string
# literal rather than only dict keys, and tells an alias declaration from a use.
_AC8_ALLOW_LISTED: frozenset[str] = frozenset(
    {
        "v..P..",
        "v..pX.",
        "vF....",
        "vfdP..",
        "vfd..A",
        "vfd.X.",
    }
)


def test_no_camel_case_dict_keys_in_core():
    """AC-8: no vultron/core/ module constructs dicts with camelCase keys."""
    import ast
    import pathlib

    import vultron.core

    core_dir = pathlib.Path(vultron.core.__file__).parent
    violations: list[tuple[str, str]] = []
    for py in sorted(core_dir.rglob("*.py")):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key in node.keys:
                if not isinstance(key, ast.Constant):
                    continue
                v = key.value
                if (
                    isinstance(v, str)
                    and len(v) > 1
                    and v[0].islower()
                    and any(c.isupper() for c in v[1:])
                    and v not in _AC8_ALLOW_LISTED
                ):
                    violations.append((str(py.relative_to(core_dir)), v))
    assert violations == [], (
        "Unexpected camelCase dict-literal keys in vultron/core/ "
        f"(add to _AC8_ALLOW_LISTED if intentional): {violations}"
    )
