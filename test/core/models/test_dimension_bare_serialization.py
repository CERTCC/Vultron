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

"""Dimension objects serialize to a bare state value (ADR-0099 detail 5).

A dimension object holds exactly one data field, ``state``; everything else on it
is behaviour, and behaviour does not serialize. Its serialized form is therefore
the bare state value rather than a one-key ``{"state": ...}`` wrapper.

The point of the change is that it costs nothing on the wire: with the wrapper
gone, the core class plus a field alias produces the same AS2 output the wire
class produced. :func:`test_core_participant_status_as2_output_matches_wire` is
the acceptance test ADR-0099 names, and it is what moves detail 5 from argued to
demonstrated.
"""

import pytest
from pydantic import ValidationError

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    DDimension,
    EmDimension,
    PecDimension,
    PxaDimension,
    RmDimension,
    VfDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import PEC
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)

#: Fields whose value is a timestamp taken at construction time, so two objects
#: built in separate statements legitimately differ.
_TIMESTAMPS = frozenset({"published", "updated"})


class TestBareSerialization:
    """Every dimension writes and reads its state without the wrapper."""

    @pytest.mark.parametrize(
        "dimension, expected",
        [
            (RmDimension(), "START"),
            (EmDimension(), "NONE"),
            (PxaDimension(), "pxa"),
            (VfDimension(), "vf"),
            (DDimension(), "d"),
            (PecDimension(), "UNBOUND"),
        ],
    )
    def test_dumps_to_a_bare_string(self, dimension, expected):
        assert dimension.model_dump(mode="json") == expected

    @pytest.mark.parametrize(
        "cls, value",
        [
            (RmDimension, "ACCEPTED"),
            (EmDimension, "EXITED"),
            (VfDimension, "VF"),
            (DDimension, "D"),
            (PecDimension, "SIGNATORY"),
        ],
    )
    def test_accepts_the_bare_form(self, cls, value):
        assert cls.model_validate(value).state.name == value

    @pytest.mark.parametrize(
        "cls, value",
        [
            (RmDimension, "ACCEPTED"),
            (EmDimension, "EXITED"),
            (PecDimension, "SIGNATORY"),
        ],
    )
    def test_still_accepts_the_mapping_form(self, cls, value):
        """Callers construct dimensions as ``{"state": ...}``; that keeps working."""
        assert cls.model_validate({"state": value}).state.name == value

    def test_round_trips(self):
        original = RmDimension(state=RM.ACCEPTED)
        assert (
            RmDimension.model_validate(original.model_dump(mode="json"))
            == original
        )

    def test_retired_pec_spelling_still_coerces(self):
        """ADR-0091 renamed ``NO_EMBARGO`` to ``UNBOUND``; the old name still reads."""
        assert PecDimension.model_validate("NO_EMBARGO").state is PEC.UNBOUND

    def test_behaviour_survives_the_serializer(self):
        """The serializer must not disturb transitions or guards."""
        dimension = RmDimension(state=RM.ACCEPTED)
        assert dimension.is_accepted()
        assert not dimension.is_closed()


#: (label, core kwargs, wire kwargs) — the same state expressed either way.
_EQUIVALENT_STATES = [
    ("default", {}, {}),
    ("rm_only", {"rm_state": RM.RECEIVED}, {"rm_state": RM.RECEIVED}),
    (
        "vendor",
        {
            "rm_state": RM.VALID,
            "vf_state": CS_vf.Vf,
            "cvd_role": [CVDRole.VENDOR],
            "tracking_id": "VU#123",
        },
        {
            "rm_state": RM.VALID,
            "vf_state": CS_vf.Vf,
            "cvd_role": [CVDRole.VENDOR],
            "tracking_id": "VU#123",
        },
    ),
    (
        "deployer",
        {
            "rm_state": RM.ACCEPTED,
            "d_state": CS_d.D,
            "cvd_role": [CVDRole.DEPLOYER],
        },
        {
            "rm_state": RM.ACCEPTED,
            "d_state": CS_d.D,
            "cvd_role": [CVDRole.DEPLOYER],
        },
    ),
    (
        "consent",
        {"em_consent_state": PEC.SIGNATORY},
        {"em_consent_state": PEC.SIGNATORY, "embargo_adherence": True},
    ),
    (
        "all_set",
        {
            "rm_state": RM.ACCEPTED,
            "vf_state": CS_vf.VF,
            "d_state": CS_d.D,
            "em_consent_state": PEC.SIGNATORY,
            "cvd_role": [CVDRole.VENDOR, CVDRole.DEPLOYER],
            "tracking_id": "VU#9",
            "case_engagement": False,
        },
        {
            "rm_state": RM.ACCEPTED,
            "vf_state": CS_vf.VF,
            "d_state": CS_d.D,
            "em_consent_state": PEC.SIGNATORY,
            "cvd_role": [CVDRole.VENDOR, CVDRole.DEPLOYER],
            "tracking_id": "VU#9",
            "case_engagement": False,
            "embargo_adherence": True,
        },
    ),
    # The nested-CaseStatus case. Kept because it is the only one of these that
    # ever actually diverged: ``ParticipantStatus._set_name`` appends
    # ``case_status.name``, so while core ``CaseStatus`` had no ``_set_name`` of
    # its own the core label was ``"VALID"`` where the wire label was
    # ``"VALID NONE pxa"`` — and ``caseStatus.name`` was absent from the core
    # payload entirely. Every other case leaves ``case_status`` unset, which is
    # exactly why the omission survived the original six.
    (
        "nested_case_status",
        {
            "rm_state": RM.VALID,
            "case_status": {
                "id": "urn:uuid:cs-nested",
                "context": "urn:case:1",
            },
        },
        {
            "rm_state": RM.VALID,
            "case_status": as_CaseStatus(
                id_="urn:uuid:cs-nested", context="urn:case:1"
            ),
        },
    ),
]


@pytest.mark.parametrize(
    "label, core_kwargs, wire_kwargs",
    _EQUIVALENT_STATES,
    ids=[case[0] for case in _EQUIVALENT_STATES],
)
def test_core_participant_status_as2_output_matches_wire(
    label, core_kwargs, wire_kwargs
):
    """The acceptance test ADR-0099 names for detail 5.

    Core ``ParticipantStatus`` must serialize to the same AS2 payload the wire
    class produces. ``@context`` is excluded because the core object
    deliberately does not carry it — ``CoreObject.context_`` is ``exclude=True``
    since the JSON-LD namespace is supplied at delivery — and timestamps are
    excluded because the two objects are constructed in separate statements.
    """
    object_id = f"urn:uuid:ps-{label}"
    core = ParticipantStatus(
        id_=object_id, context="urn:case:1", **core_kwargs
    )
    wire = as_ParticipantStatus(
        id_=object_id, context="urn:case:1", **wire_kwargs
    )

    def strip(value):
        """Drop timestamps and ``@context`` at every depth, not just the top.

        Nested objects have to be stripped too, or a nested ``caseStatus``
        compares unequal on its own construction timestamps and the case is
        vacuously skipped rather than checked.
        """
        if isinstance(value, dict):
            return {
                k: strip(v)
                for k, v in value.items()
                if k not in _TIMESTAMPS and k != "@context"
            }
        if isinstance(value, list):
            return [strip(item) for item in value]
        return value

    def payload(obj):
        return strip(
            obj.model_dump(
                mode="json",
                by_alias=True,
                exclude_none=True,
                serialize_as_any=True,
            )
        )

    assert payload(core) == payload(wire)


class TestStatePersistsThroughTheNormalisationRoundTrip:
    """Regression for the silent state loss the spike uncovered.

    The since-deleted ``_NORMALIZE_WIRE_TO_CORE`` (#2940) contained
    ``VulnerabilityCase`` and ``CaseStatus``, so a persistence write
    reconstituted the object through the wire vocabulary. When the wire
    class's before-validator recognised only the mapping form of a
    dimension, the bare form left the key unconsumed, the flat field was never set, and the state fell back to its
    initial value with no error — the #2262 pattern.
    """

    @staticmethod
    def _normalised(obj):
        """Return *obj* after the round trip a persistence write performs."""
        from vultron.adapters.driven.datalayer_sqlite.crud import (
            _storable_to_record,
        )
        from vultron.adapters.driven.db_record import object_to_record

        return _storable_to_record(object_to_record(obj)).data_

    def test_em_state_survives_the_normalisation_round_trip(self):
        status = CaseStatus(context="urn:case:1")
        status.em.state = EM.EXITED

        data = self._normalised(status)

        assert data["em"] == "EXITED", (
            "EM.EXITED was dropped on the way to storage and fell back to the"
            f" initial state; got {data.get('em')!r}"
        )
        assert CaseStatus.model_validate(data).em.state is EM.EXITED

    def test_rm_state_survives_the_normalisation_round_trip(self):
        # Built through ``model_validate`` rather than keyword arguments: the
        # legacy flat ``rm_state`` spelling is accepted via ``AliasChoices``,
        # which is a validation-time alias and not a declared parameter name.
        status = ParticipantStatus.model_validate(
            {"context": "urn:case:1", "rm_state": RM.ACCEPTED}
        )

        data = self._normalised(status)

        assert data["rm"] == "ACCEPTED", (
            "RM.ACCEPTED was dropped on the way to storage and fell back to"
            f" RM.START; got {data.get('rm')!r}"
        )
        assert ParticipantStatus.model_validate(data).rm.state is RM.ACCEPTED


class TestExplicitNullIsRefused:
    """An explicit ``null`` for a dimension raises; absence gets the default.

    The removed ``_migrate_flat_fields`` before-validator guarded on
    ``raw is not None`` and fell back to the field default, so
    ``{"rmState": None}`` quietly produced ``RM.START``. ADR-0099 detail 7's
    fail-loudly rule refuses it instead: naming a dimension and supplying no
    state is a statement the caller cannot back, and it is a different input from
    not naming it at all.
    """

    @pytest.mark.parametrize(
        "cls, payload",
        [
            (CaseStatus, {"context": "urn:case:1", "emState": None}),
            (CaseStatus, {"context": "urn:case:1", "pxaState": None}),
            (ParticipantStatus, {"context": "urn:case:1", "rmState": None}),
        ],
    )
    def test_explicit_null_dimension_raises(self, cls, payload):
        with pytest.raises(ValidationError):
            cls.model_validate(payload)

    @pytest.mark.parametrize(
        "cls, expected_field, expected_state",
        [
            (CaseStatus, "em", EM.NONE),
            (ParticipantStatus, "rm", RM.START),
        ],
    )
    def test_absence_still_gets_the_default(
        self, cls, expected_field, expected_state
    ):
        obj = cls.model_validate({"context": "urn:case:1"})
        assert getattr(obj, expected_field).state is expected_state
