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
"""Planned behavior for the CASE_MANAGER's seating entry, ``Add(CaseParticipant)``.

Strict-``xfail`` probes for the requirements #6518 amended before the code that
satisfies them exists; see ``notes/spec-authoring-rules.md`` § "Use a Strict
``xfail`` for Not-Yet-Implemented Specs", and ``notes/as2-vocabulary-alignment.md``
§ "The CASE_MANAGER Adds a New Participant Record to the Case".

The amended IDs already carry markers on tests of today's
``Create(CaseParticipant)`` entry, so each probe checks the behavior: it passes
once #6295 makes the seating entry an ``Add`` and drops the ``Create``. The probe
for the stub Invite's entry sequence (CM-11-023 to CM-11-025, CLP-07-021) sits in
``test/core/use_cases/received/test_stub_invite_replay.py``, beside the helpers it
drives. When a probe XPASSes, ``strict=True`` fails the build and the builder
deletes the probe.
"""

import pytest

from test.support.objects import make
from vultron.core.models.events import MessageSemantics
from vultron.semantic_registry import find_matching_semantics, lookup_entry
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Create,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant

_SEAT = "Tracked by #6295 (the CASE_MANAGER seats a participant with Add)."

_CASE = "https://example.org/cases/1"
_MANAGER = "https://example.org/case-manager"


def _participant() -> as_CaseParticipant:
    return make(
        as_CaseParticipant,
        attributed_to="https://example.org/vendor",
        context=_CASE,
    )


@pytest.mark.spec("VAM-01-017")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "VAM-01-017: a received Create(CaseParticipant) is still recognized "
        f"as CREATE_CASE_PARTICIPANT. {_SEAT}"
    ),
)
def test_a_create_of_a_case_participant_is_unrecognized() -> None:
    create = make(
        as_Create, actor=_MANAGER, object_=_participant(), context=_CASE
    )

    assert find_matching_semantics(create) is MessageSemantics.UNKNOWN


@pytest.mark.spec("VAM-01-018", "VAM-06-004")
@pytest.mark.xfail(
    strict=True,
    reason=(
        "VAM-01-018, VAM-06-004: no semantic recognizes the CASE_MANAGER's "
        "Add(CaseParticipant) now that the Owner's reinstatement names the "
        f"actor instead. {_SEAT}"
    ),
)
def test_the_seating_add_is_recognized_and_unhandled() -> None:
    add = make(
        as_Add,
        actor=_MANAGER,
        object_=_participant(),
        target=_CASE,
        context=_CASE,
    )

    semantics = find_matching_semantics(add)
    # The name the seating entry reuses (#6295); not yet a member.
    assert semantics.value == "add_case_participant_to_case"
    assert not lookup_entry(semantics).handled
