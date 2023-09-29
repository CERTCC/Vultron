#!/usr/bin/env python
"""file: log_ledger
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

import pandas as pd

from vultron.bt.experimental.case_log.errors import LogEntryError, LogError
from vultron.bt.experimental.case_log.log_item import LogItem


@dataclass
class LogLedger:
    history: list[LogItem] = field(default_factory=list)

    def append(self, entry: LogItem):
        try:
            entry._validate()
        except LogEntryError as e:
            raise LogError(f"Cannot append invalid log entry: {e}")

        self.history.append(entry)

    @property
    def df(self):
        df = pd.DataFrame(self.history)
        return df


def main():
    pass


if __name__ == "__main__":
    main()
