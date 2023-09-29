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

"""
`vultron.case_states.errors` provides error classes for the CVD State Model.
"""

from vultron.errors import VultronError


class CvdStateModelError(VultronError):
    """Base class for errors in the `vultron.case_states` module."""


class CVDmodelError(CvdStateModelError):
    pass


class ScoringError(CvdStateModelError):
    pass


class ValidationError(CvdStateModelError):
    pass


class PatternValidationError(ValidationError):
    pass


class StateValidationError(ValidationError):
    pass


class HistoryValidationError(ValidationError):
    pass


class TransitionValidationError(ValidationError):
    pass
