"""Run the demo report tool as ``python -m vultron.demo.report``."""

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

import sys

from vultron.demo.report.cli import main

#: The program name ``--help`` shows under ``python -m vultron.demo.report``.
#: ``sys.argv[0]`` is this file's path here, so argparse would print
#: ``__main__.py``; the name is the one the flat ``report.py`` module printed.
_PROG = "report.py"

if __name__ == "__main__":
    sys.exit(main(prog=_PROG))
