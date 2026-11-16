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

"""The state of one VINCE case's translation, and the helpers every row
group shares.

The row groups (:mod:`.case_rows`, :mod:`.vendor_rows`,
:mod:`.content_rows`) each read one part of the VINCE records and add acts
and untranslated facts to a :class:`CaseTranslation`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import JsonValue

from vultron.adapters.connectors.vince.acts import RM_PATH, Act, Participant
from vultron.adapters.connectors.vince.ids import CaseIds
from vultron.adapters.connectors.vince.records import (
    Record,
    VinceCase,
    parse_list,
    parse_one,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_reading import (
    UntranslatedFact,
    UntranslatedReason,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus

ADD_STATUS = MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT


@dataclass
class CaseTranslation:
    """The translation of one case, built row group by row group.

    Attributes:
        as_of: The time of reading, which the caller supplies: the time the
            embargo's end is judged against (VINCE-EM-03).  The translation
            reads no clock (CRD-02-006).
        seats: The act that seated each participant, by actor.
        orgs: The participant each organization name on a post credits.
        embargo: The embargo VINCE-EM-01 inferred, once it has.
    """

    ids: CaseIds
    reads: Mapping[str, JsonValue]
    as_of: datetime
    acts: list[Act] = field(default_factory=list)
    untranslated: list[UntranslatedFact] = field(default_factory=list)
    participants: dict[str, Participant] = field(default_factory=dict)
    seats: dict[str, Act] = field(default_factory=dict)
    orgs: dict[str, str] = field(default_factory=dict)
    embargo: EmbargoEvent | None = None

    @property
    def case(self) -> VinceCase:
        return self.ids.case

    @property
    def case_id(self) -> str:
        return self.ids.case_id

    @property
    def coordinator(self) -> Participant:
        return self.participants[self.ids.coordinator]

    @property
    def embargo_end(self) -> datetime | None:
        """VINCE-EM-03: when the embargo ended, which is ``due_date`` once
        the time of reading has reached it; ``None`` while it is in force
        or when there is none."""
        due = self.case.due_date
        if self.embargo is None or due is None or self.as_of < due:
            return None
        return due

    def em_at(self, at: datetime) -> str:
        """The embargo register's EM at *at*: none, the VINCE-EM-01
        embargo in force, or exited once VINCE-EM-03 ended it."""
        if self.embargo is None:
            return "NONE"
        end = self.embargo_end
        return "EXITED" if end is not None and at >= end else "ACTIVE"

    # -- reading the records -------------------------------------------

    def not_translated(
        self, source_record: str, fact: str, reason: UntranslatedReason
    ) -> None:
        """Return *fact* untranslated, for *reason* (CRD-02-003)."""
        self.untranslated.append(
            UntranslatedFact(
                source_record=source_record, fact=fact, reason=reason
            )
        )

    def items[R: Record](
        self, read: str, model: type[R]
    ) -> list[tuple[int, R]]:
        """The items of the list read *read* that parse, each with its
        index; each item that does not is an unknown value."""
        parsed = parse_list(read, self.reads.get(read), model)
        for index, problem in parsed.problems:
            self.not_translated(
                self.ids.record(read, index if index >= 0 else None),
                problem,
                UntranslatedReason.UNKNOWN_VALUE,
            )
        return list(parsed.items)

    def one[R: Record](self, read: str, model: type[R]) -> R | None:
        """The single-record read *read*: ``None`` when VINCE answered 404
        or it does not parse, which is an unknown value."""
        parsed = parse_one(read, self.reads.get(read), model)
        if isinstance(parsed, str):
            self.not_translated(
                self.ids.record(read), parsed, UntranslatedReason.UNKNOWN_VALUE
            )
            return None
        return parsed

    # -- writing acts --------------------------------------------------

    def act(self, act: Act) -> Act:
        self.acts.append(act)
        return act

    def status(
        self,
        participant: Participant,
        rm: str,
        at: datetime,
        label: str,
        *,
        pxa: str | None = None,
    ) -> ParticipantStatus:
        """A participant status of *participant* at RM *rm*, as of *at*,
        reporting public state *pxa* when it is set."""
        data: dict[str, object] = {
            "id": self.ids.minted(f"status:{participant.actor}:{label}"),
            "context": self.case_id,
            "attributedTo": participant.actor,
            "rmState": rm,
            "cvdRole": [role.upper() for role in participant.roles],
            "published": at,
            "updated": at,
        }
        if participant.vendor:
            # A vendor is aware from its RM Received on (crosswalk § Case
            # state), and the flag stays up on every later status.
            data["vfState"] = "Vf"
        if pxa is not None:
            data["caseStatus"] = self.case_status(
                pxa, at, f"{label}:case-status", participant.actor
            )
        return ParticipantStatus.model_validate(data)

    def case_status(
        self, pxa: str, at: datetime, label: str, actor: str
    ) -> CaseStatus:
        """A case status stating public state *pxa* as of *at*.  Its EM is
        a copy of the embargo register, which holds VINCE-EM-01's embargo
        from the case's opening on, until VINCE-EM-03 ends it."""
        return CaseStatus.model_validate(
            {
                "id": self.ids.minted(label),
                "context": self.case_id,
                "attributedTo": actor,
                "emState": self.em_at(at),
                "pxaState": pxa,
                "published": at,
                "updated": at,
            }
        )

    def add_status(
        self,
        participant: Participant,
        status: ParticipantStatus,
        at: datetime,
        source_record: str,
        label: str,
        rules: Sequence[str] = (),
    ) -> Act:
        """*participant*'s own ``Add(ParticipantStatus)`` of *status*, at
        *at*."""
        return self.act(
            Act(
                at=at,
                semantic_type=ADD_STATUS,
                activity_type="Add",
                actor=participant.actor,
                object_=status,
                source_record=source_record,
                label=label,
                rules=list(rules),
                target=self.ids.participant(participant.actor),
            )
        )

    def rm_steps(
        self,
        participant: Participant,
        to: str,
        at: datetime,
        source_record: str,
        rules: Sequence[str],
        label: str,
    ) -> None:
        """Move *participant* to RM *to* at *at*, one entry per state it
        passes through, each by the participant itself."""
        current = participant.rm_at(at)
        path = RM_PATH[to]
        start = path.index(current) + 1 if current in path else 0
        for rm in path[start:]:
            status = self.status(participant, rm, at, f"{label}:{rm}")
            participant.rm.append((at, rm))
            participant.statuses.append(status)
            self.add_status(
                participant, status, at, source_record, f"{label}:{rm}", rules
            )

    def participant_record(
        self, participant: Participant, name: str, at: datetime
    ) -> CaseParticipant:
        """*participant*'s record as of *at*, with the statuses it holds."""
        return CaseParticipant.model_validate(
            {
                "id": self.ids.participant(participant.actor),
                "name": name,
                "context": self.case_id,
                "attributedTo": participant.actor,
                "caseRoles": list(participant.roles),
                "participantStatuses": [
                    status.model_dump(by_alias=True)
                    for status in participant.statuses
                ],
                "published": at,
                "updated": at,
            }
        )

    def seat(
        self,
        participant: Participant,
        name: str,
        actor: str,
        at: datetime,
        source_record: str,
        rules: Sequence[str],
        statuses: Sequence[str],
    ) -> Act:
        """The ``Create(CaseParticipant)`` by *actor* that seats
        *participant*, carrying a status for each RM state in *statuses*."""
        self.participants[participant.actor] = participant
        for rm in statuses:
            participant.statuses.append(
                self.status(participant, rm, at, f"seat:{rm}")
            )
            participant.rm.append((at, rm))
        act = self.act(
            Act(
                at=at,
                semantic_type=MessageSemantics.CREATE_CASE_PARTICIPANT,
                activity_type="Create",
                actor=actor,
                object_=self.participant_record(participant, name, at),
                source_record=source_record,
                label=f"seat:{participant.actor}",
                rules=list(rules),
                target=self.case_id,
            )
        )
        self.seats[participant.actor] = act
        return act


__all__ = ["ADD_STATUS", "CaseTranslation"]
