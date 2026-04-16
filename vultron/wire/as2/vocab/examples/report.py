#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

from vultron.wire.as2.vocab.activities.report import (
    RmCloseReportActivity,
    RmCreateReportActivity,
    RmInvalidateReportActivity,
    RmReadReportActivity,
    RmSubmitReportActivity,
    RmValidateReportActivity,
)
from vultron.wire.as2.vocab.examples._base import _FINDER, _REPORT, _VENDOR


def create_report() -> RmCreateReportActivity:
    """
    In this example, a finder creates a vulnerability report.

    Example:
          >>> RmCreateReportActivity(actor=finder.id_, id_=gen_report)
    """
    activity = RmCreateReportActivity(actor=_FINDER.id_, object_=_REPORT)
    return activity


def submit_report(verbose=False) -> RmSubmitReportActivity:
    if verbose:
        activity = RmSubmitReportActivity(
            actor=_FINDER,
            object_=_REPORT,
            to=_VENDOR,
        )
    else:
        activity = RmSubmitReportActivity(
            actor=_FINDER.id_, object_=_REPORT, to=_VENDOR.id_
        )

    return activity


def read_report() -> RmReadReportActivity:
    # TODO this should probably change to Read(Offer(Report)) to match the other activities
    activity = RmReadReportActivity(
        actor=_VENDOR.id_,
        object_=_REPORT,
        content="We've read the report. We'll get back to you soon.",
    )
    return activity


def validate_report(verbose: bool = False) -> RmValidateReportActivity:
    _offer = submit_report(verbose=verbose)
    # Note: you accept the Offer activity that contains the Report, not the Report itself

    if verbose:
        activity = RmValidateReportActivity(
            actor=_VENDOR,
            object_=_offer,
            content="We've validated the report. We'll be creating a case shortly.",
        )
    else:
        activity = RmValidateReportActivity(
            actor=_VENDOR.id_,
            object_=_offer.id_,
            content="We've validated the report. We'll be creating a case shortly.",
        )
    return activity


def invalidate_report(verbose: bool = False) -> RmInvalidateReportActivity:
    _offer = submit_report(verbose=verbose)
    # Note: you tentative reject the Offer activity that contains the Report, not the Report itself

    if verbose:
        activity = RmInvalidateReportActivity(
            actor=_VENDOR,
            object_=_offer,
            content="We're declining this report as invalid. If you have a reason we should reconsider, please let us know. Otherwise we'll be closing it shortly.",
        )
    else:
        activity = RmInvalidateReportActivity(
            actor=_VENDOR.id_,
            object_=_offer.id_,
            content="We're declining this report as invalid. If you have a reason we should reconsider, please let us know. Otherwise we'll be closing it shortly.",
        )
    return activity


def close_report(verbose: bool = False) -> RmCloseReportActivity:
    # Note: you reject the Offer activity that contains the Report, not the Report itself
    _offer = submit_report(verbose=verbose)
    if verbose:
        activity = RmCloseReportActivity(
            actor=_VENDOR,
            object_=_offer,
            content="We're closing this report.",
        )
    else:
        activity = RmCloseReportActivity(
            actor=_VENDOR.id_,
            object_=_offer.id_,
            content="We're closing this report.",
        )
    return activity
