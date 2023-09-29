#!/usr/bin/env python
"""file: log_item
author: adh
created_at: 11/30/22 2:59 PM
"""
#  Copyright (c) 2023 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from vultron.cvd_states.states import CS_pxa, CS_vfd

from vultron.bt.embargo_management.states import EM
from vultron.bt.experimental.case_log.errors import LogEntryError
from vultron.bt.report_management.states import RM
from vultron.bt.roles.states import CVDRoles


@dataclass
class _LogItemBase:
    ### WHAT ###
    case_id: str  # a string (guid?)

    ### WHO ###
    participant_id: str  # a string (guid?)
    participant_role: CVDRoles  # roles flags

    subject_id: str
    subject_role: CVDRoles

    ### WHEN ###
    timestamp: datetime  # a datetime

    ### WHERE ###
    q_rm: RM
    q_em: EM
    q_cs_vfd: CS_vfd
    q_cs_pxa: CS_pxa

    ### Case Details ###
    embargo_end_at: Optional[datetime]
    embargo_proposals: Optional[list[datetime]]

    def __post_init__(self):
        # set NO_ROLE if unspecified
        if self.participant_role is None:
            self.participant_role = CVDRoles.NO_ROLE
        if self.subject_role is None:
            self.subject_role = CVDRoles.NO_ROLE
        if self.subject_id is None:
            self.subject_id = self.participant_id
        if self.subject_role is None:
            self.subject_role = self.participant_role

        self._validate()

    def _validate(self):
        self._reject_nones()
        self._reject_self_ignorance()
        self._reject_vendor_self_ignorance()
        self._reject_impossible_embargo_proposals()
        self._reject_empty_proposals()
        self._reject_missing_embargo_date()
        self._reject_incompatible_embargo_states()

    def _reject_nones(self):
        for attr in ["case_id", "participant_id", "participant_role"]:
            if getattr(self, attr) is None:
                raise LogEntryError(f"{attr} should not be None")

    def _reject_self_ignorance(self):
        """If you are reporting that you don't know about the case you're reporting about, that's an error"""
        if self.q_rm == RM.S and self.subject_id == self.participant_id:
            raise LogEntryError(
                f"RM state {self.q_rm} is incompatible with self-referential entries"
            )

    def _reject_vendor_self_ignorance(self):
        """If your role is VENDOR and you're claiming to be in vfd instead of V**, something is wrong"""
        if self.participant_id != self.subject_id:
            return

        if (
            self.participant_role & CVDRoles.VENDOR
        ) and self.q_cs_vfd == CS_vfd.vfd:
            raise LogEntryError(
                f"Role {self.participant_role} cannot be in CS {self.q_cs_vfd}"
            )

    def _reject_impossible_embargo_proposals(self):
        """If your state says there aren't any proposals but the proposals list is not empty, that's an error"""
        # EM.N, EM.A, and EM.X require no proposals
        if len(self.embargo_proposals) and self.q_em in (EM.N, EM.A, EM.X):
            raise LogEntryError(
                f"Embargo state {self.q_em} is incompatible with embargo proposals {self.embargo_proposals}"
            )

    def _reject_empty_proposals(self):
        """If you claim to be in a state with embargo proposals but the proposal list is empty, that's an error"""
        # EM.P and EM.R require at least one proposal
        if not len(self.embargo_proposals) and self.q_em in (EM.P, EM.R):
            raise LogEntryError(
                f"Embargo state {self.q_em} requires non-empty embargo proposals"
            )

    def _reject_missing_embargo_date(self):
        """If your state says you're in an embargo but there's no embargo date set, that's an error"""
        if self.embargo_end_at is None and self.q_em in (EM.A, EM.R, EM.X):
            raise LogEntryError(
                f"Embargo state {self.q_em} requires embargo date to be set"
            )

    def _reject_incompatible_embargo_states(self):
        """You shouldn't be in an embargo when in anything other than pxa"""
        if self.q_cs_pxa != CS_pxa.pxa and self.q_em not in (EM.N, EM.X):
            raise LogEntryError(
                f"Embargo state {self.q_em} is incompatible with CS state {self.q_cs_pxa}"
            )


@dataclass
class _LogItemDefaults:
    participant_role: Optional[CVDRoles] = CVDRoles.NO_ROLE  # roles flag

    # log items might be submitted by participant A about participant B
    # for example, a finder might want to announce that they told a vendor
    subject_id: Optional[
        str
    ] = None  # a string identifying the participant this item is about
    subject_role: Optional[CVDRoles] = CVDRoles.NO_ROLE  # roles flag

    # timestamp defaults to now
    timestamp: datetime = datetime.now()

    ### WHERE ###
    q_rm: RM = RM.START  # rm state enum
    q_em: EM = EM.NO_EMBARGO  # em state enum
    q_cs_vfd: CS_vfd = CS_vfd.vfd  # vfd enum
    q_cs_pxa: CS_pxa = CS_pxa.pxa  # a pxa enum

    ### Case Details ###
    embargo_end_at: Optional[datetime] = None  # a datetime
    embargo_proposals: list[datetime] = field(
        default_factory=list
    )  # list of datetimes, defaults to empty


@dataclass
class LogItem(_LogItemDefaults, _LogItemBase):
    pass


def main():
    pass


if __name__ == "__main__":
    main()
