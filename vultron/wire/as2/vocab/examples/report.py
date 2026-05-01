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

from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Offer,
    as_Read,
    as_Reject,
    as_TentativeReject,
)
from vultron.wire.as2.vocab.examples._base import _FINDER, _REPORT, _VENDOR
from vultron.wire.as2.factories import (
    rm_close_report_activity,
    rm_create_report_activity,
    rm_invalidate_report_activity,
    rm_read_report_activity,
    rm_submit_report_activity,
    rm_validate_report_activity,
)


def create_report() -> as_Create:
    """
    In this example, a finder creates a vulnerability report.

    Example:
          >>> rm_create_report_activity(_REPORT, actor=finder.id_)
    """
    activity = rm_create_report_activity(_REPORT, actor=_FINDER.id_)
    return activity


def submit_report(verbose=False) -> as_Offer:
    if verbose:
        activity = rm_submit_report_activity(
            _REPORT, actor=_FINDER, to=_VENDOR
        )
    else:
        activity = rm_submit_report_activity(
            _REPORT, actor=_FINDER.id_, to=_VENDOR.id_
        )

    return activity


def read_report() -> as_Read:
    # TODO this should probably change to Read(Offer(Report)) to match the other activities
    activity = rm_read_report_activity(
        _REPORT,
        actor=_VENDOR.id_,
        content="We've read the report. We'll get back to you soon.",
    )
    return activity


def validate_report(verbose: bool = False) -> as_Accept:
    _offer = submit_report(verbose=verbose)
    # Note: you accept the Offer activity that contains the Report, not the Report itself

    if verbose:
        activity = rm_validate_report_activity(
            _offer,
            actor=_VENDOR,
            content="We've validated the report. We'll be creating a case shortly.",
        )
    else:
        activity = rm_validate_report_activity(
            _offer,
            actor=_VENDOR.id_,
            content="We've validated the report. We'll be creating a case shortly.",
        )
    return activity


def invalidate_report(verbose: bool = False) -> as_TentativeReject:
    _offer = submit_report(verbose=verbose)
    # Note: you tentative reject the Offer activity that contains the Report, not the Report itself

    if verbose:
        activity = rm_invalidate_report_activity(
            _offer,
            actor=_VENDOR,
            content="We're declining this report as invalid. If you have a reason we should reconsider, please let us know. Otherwise we'll be closing it shortly.",
        )
    else:
        activity = rm_invalidate_report_activity(
            _offer,
            actor=_VENDOR.id_,
            content="We're declining this report as invalid. If you have a reason we should reconsider, please let us know. Otherwise we'll be closing it shortly.",
        )
    return activity


def close_report(verbose: bool = False) -> as_Reject:
    # Note: you reject the Offer activity that contains the Report, not the Report itself
    _offer = submit_report(verbose=verbose)
    if verbose:
        activity = rm_close_report_activity(
            _offer, actor=_VENDOR, content="We're closing this report."
        )
    else:
        activity = rm_close_report_activity(
            _offer, actor=_VENDOR.id_, content="We're closing this report."
        )
    return activity
