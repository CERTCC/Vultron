#!/usr/bin/env python
"""file: case_log
author: adh
created_at: 11/2/22 1:35 PM
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
#
#  See LICENSE for details

import uuid
from datetime import datetime, timedelta

from vultron.cvd_states.states import CS_pxa, CS_vfd

from vultron.bt.embargo_management.states import EM
from vultron.bt.experimental.case_log import LogItem
from vultron.bt.experimental.case_log.log_ledger import LogLedger
from vultron.bt.report_management.states import RM
from vultron.bt.roles.states import CVDRoles


def main():
    log = LogLedger()

    now = datetime.now()
    reporter = str(uuid.uuid4())
    vendor = str(uuid.uuid4())
    case = str(uuid.uuid4())

    x = LogItem(
        timestamp=now,
        case_id=case,
        participant_id=reporter,
        participant_role=CVDRoles.FINDER_REPORTER,
        subject_id=reporter,
        q_rm=RM.A,
        q_em=EM.P,
        q_cs_vfd=CS_vfd.vfd,
        q_cs_pxa=CS_pxa.pxa,
        embargo_end_at=None,
        embargo_proposals=[now + timedelta(days=45)],
    )
    log.append(x)

    x = LogItem(
        timestamp=now,
        case_id=case,
        participant_id=reporter,
        participant_role=CVDRoles.FINDER_REPORTER,
        subject_id=vendor,
        q_rm=RM.S,
        q_em=EM.P,
        q_cs_vfd=CS_vfd.vfd,
        q_cs_pxa=CS_pxa.pxa,
        embargo_end_at=None,
        embargo_proposals=[now + timedelta(days=45)],
    )
    log.append(x)

    x = LogItem(
        timestamp=now,
        case_id=case,
        participant_id=reporter,
        participant_role=CVDRoles.FINDER_REPORTER,
        subject_id=vendor,
        q_rm=RM.R,
        q_em=EM.P,
        q_cs_vfd=CS_vfd.Vfd,
        q_cs_pxa=CS_pxa.pxa,
        embargo_end_at=None,
        embargo_proposals=[now + timedelta(days=45)],
    )
    log.append(x)

    x = LogItem(
        timestamp=now + timedelta(minutes=15),
        case_id=case,
        participant_id=vendor,
        participant_role=CVDRoles.VENDOR,
        subject_id=vendor,
        q_rm=RM.R,
        q_em=EM.P,
        q_cs_vfd=CS_vfd.Vfd,
        q_cs_pxa=CS_pxa.pxa,
        embargo_end_at=None,
        embargo_proposals=x.embargo_proposals,
    )
    log.append(x)

    x = LogItem(
        timestamp=now + timedelta(minutes=15),
        case_id=case,
        participant_id=vendor,
        participant_role=CVDRoles.VENDOR,
        subject_id=vendor,
        q_rm=RM.R,
        q_em=EM.A,
        q_cs_vfd=CS_vfd.Vfd,
        q_cs_pxa=CS_pxa.pxa,
        embargo_end_at=x.embargo_proposals.pop(),
        embargo_proposals=x.embargo_proposals,
    )
    log.append(x)

    print(log.df)


if __name__ == "__main__":
    main()
