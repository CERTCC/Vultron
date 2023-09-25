#  Copyright (c) 2023. Carnegie Mellon University
#
#  See LICENSE for details
"""
Provides error classes for the CVD State Model.
"""

from vultron.errors import VultronError


class CvdStateModelError(VultronError):
    pass


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
