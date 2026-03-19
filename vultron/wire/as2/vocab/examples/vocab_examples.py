#!/usr/bin/env python
"""
Provides tools for generating examples of Vultron ActivityStreams objects.

Used within the Vultron documentation to provide examples of Vultron ActivityStreams objects.

When run as a script, this module will generate a set of example objects and write them to the docs/reference/examples
directory.
"""

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

from vultron.wire.as2.vocab.examples._base import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.actor import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.case import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.embargo import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.note import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.participant import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.report import *  # noqa: F401, F403
from vultron.wire.as2.vocab.examples.status import *  # noqa: F401, F403

from vultron.wire.as2.vocab.examples._base import (  # noqa: F401
    ACTOR_FUNCS,
    _COORDINATOR,
    case,
    coordinator,
    finder,
    gen_report,
    obj_to_file,
    vendor,
)
from vultron.wire.as2.vocab.examples.actor import (  # noqa: F401
    accept_actor_recommendation,
    recommend_actor,
    reject_actor_recommendation,
)
from vultron.wire.as2.vocab.examples.case import (  # noqa: F401
    accept_case_ownership_transfer,
    add_report_to_case,
    close_case,
    create_case,
    defer_case,
    engage_case,
    offer_case_ownership_transfer,
    reengage_case,
    reject_case_ownership_transfer,
    update_case,
)
from vultron.wire.as2.vocab.examples.embargo import (  # noqa: F401
    accept_embargo,
    activate_embargo,
    add_embargo_to_case,
    announce_embargo,
    choose_preferred_embargo,
    embargo_event,
    propose_embargo,
    reject_embargo,
    remove_embargo,
)
from vultron.wire.as2.vocab.examples.note import (  # noqa: F401
    add_note_to_case,
    create_note,
    note,
)
from vultron.wire.as2.vocab.examples.participant import (  # noqa: F401
    accept_invite_to_case,
    add_coordinator_participant_to_case,
    add_finder_participant_to_case,
    add_vendor_participant_to_case,
    case_participant,
    coordinator_participant,
    create_participant,
    invite_to_case,
    reject_invite_to_case,
    remove_participant_from_case,
    rm_invite_to_case,
)
from vultron.wire.as2.vocab.examples.report import (  # noqa: F401
    close_report,
    create_report,
    invalidate_report,
    read_report,
    submit_report,
    validate_report,
)
from vultron.wire.as2.vocab.examples.status import (  # noqa: F401
    add_status_to_case,
    add_status_to_participant,
    case_status,
    create_case_status,
    create_participant_status,
    participant_status,
)


def main():
    outdir = "../../docs/reference/examples"
    print(f"Generating examples to: {outdir}")

    # ensure the output directory exists
    from pathlib import Path

    Path(outdir).mkdir(parents=True, exist_ok=True)

    # create a finder (Person) object
    _finder = finder()
    obj_to_file(_finder, f"{outdir}/finder.json")

    # create a vendor (Organization) object
    _vendor = vendor()
    obj_to_file(_vendor, f"{outdir}/vendor.json")

    # create a vulnerability _report
    _report = gen_report()
    obj_to_file(_report, f"{outdir}/vulnerability_report.json")

    # activity: finder creates _report
    activity = create_report()
    obj_to_file(activity, f"{outdir}/create_report.json")

    # activity: finder submits _report to vendor
    activity = submit_report()
    obj_to_file(activity, f"{outdir}/submit_report.json")

    # activity: vendor reads _report
    activity = read_report()
    obj_to_file(activity, f"{outdir}/read_report.json")

    # activity: vendor validates _report
    activity = validate_report()
    obj_to_file(activity, f"{outdir}/validate_report.json")

    # activity: vendor invalidates _report
    activity = invalidate_report()
    obj_to_file(activity, f"{outdir}/invalidate_report.json")

    # activity: vendor closes _report
    activity = close_report()
    obj_to_file(activity, f"{outdir}/close_report.json")

    # case object
    _case = case()
    obj_to_file(_case, f"{outdir}/vulnerability_case.json")

    # activity: vendor creates case from _report
    activity = create_case()
    obj_to_file(activity, f"{outdir}/create_case.json")

    # activity: vendor adds _report to case
    activity = add_report_to_case()
    obj_to_file(activity, f"{outdir}/add_report_to_case.json")

    # activity: vendor adds self as participant to case
    activity = add_vendor_participant_to_case()

    participant = activity.as_object
    obj_to_file(participant, f"{outdir}/vendor_participant.json")
    obj_to_file(activity, f"{outdir}/add_vendor_participant_to_case.json")

    # activity: vendor adds finder as participant to case
    activity = add_finder_participant_to_case()
    participant = activity.as_object
    obj_to_file(participant, f"{outdir}/finder_participant.json")
    obj_to_file(activity, f"{outdir}/add_finder_participant_to_case.json")

    # activity: vendor engages case
    activity = engage_case()
    obj_to_file(activity, f"{outdir}/engage_case.json")

    # activity: vendor closes case
    activity = close_case()
    obj_to_file(activity, f"{outdir}/close_case.json")

    # activity: vendor defers case
    activity = defer_case()
    obj_to_file(activity, f"{outdir}/defer_case.json")

    # activity: vendor reengages case
    activity = reengage_case()
    obj_to_file(activity, f"{outdir}/reengage_case.json")

    # activity: add note to case
    activity = add_note_to_case()
    obj_to_file(activity, f"{outdir}/add_note_to_case.json")

    _coordinator = _COORDINATOR
    obj_to_file(_coordinator, f"{outdir}/coordinator.json")

    # activity: offer case ownership transfer
    activity = offer_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/offer_case_ownership_transfer.json")

    # activity: accept case ownership transfer
    activity = accept_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/accept_case_ownership_transfer.json")

    # activity: reject case ownership transfer
    activity = reject_case_ownership_transfer()
    obj_to_file(activity, f"{outdir}/reject_case_ownership_transfer.json")

    # activity: update case
    activity = update_case()
    obj_to_file(activity, f"{outdir}/update_case.json")

    # recommend actor
    activity = recommend_actor()
    obj_to_file(activity, f"{outdir}/recommend_actor.json")

    # accept actor recommendation
    activity = accept_actor_recommendation()
    obj_to_file(activity, f"{outdir}/accept_actor_recommendation.json")

    # reject actor recommendation
    activity = reject_actor_recommendation()
    obj_to_file(activity, f"{outdir}/reject_actor_recommendation.json")

    # rm_invite_to_case
    activity = rm_invite_to_case()
    obj_to_file(activity, f"{outdir}/invite_to_case.json")

    # rm_accept_invite_to_case
    activity = accept_invite_to_case()
    obj_to_file(activity, f"{outdir}/accept_invite_to_case.json")

    # rm_reject_invite_to_case
    activity = reject_invite_to_case()
    obj_to_file(activity, f"{outdir}/reject_invite_to_case.json")

    # create participant
    activity = create_participant()
    obj_to_file(activity, f"{outdir}/create_participant.json")

    _case_status = case_status()
    obj_to_file(_case_status, f"{outdir}/case_status.json")

    _create_case_status = create_case_status()
    obj_to_file(_create_case_status, f"{outdir}/create_case_status.json")

    _add_status_to_case = add_status_to_case()
    obj_to_file(_add_status_to_case, f"{outdir}/add_status_to_case.json")

    _participant_status = participant_status()
    obj_to_file(_participant_status, f"{outdir}/participant_status.json")

    _case_participant = case_participant()
    obj_to_file(_case_participant, f"{outdir}/case_participant.json")

    _embargo_event = embargo_event()
    obj_to_file(_embargo_event, f"{outdir}/embargo_event.json")

    _invite_to_case = invite_to_case()
    obj_to_file(_invite_to_case, f"{outdir}/invite_to_case.json")

    _create_participant_status = create_participant_status()
    obj_to_file(
        _create_participant_status, f"{outdir}/create_participant_status.json"
    )

    _add_status_to_participant = add_status_to_participant()
    obj_to_file(
        _add_status_to_participant, f"{outdir}/add_status_to_participant.json"
    )

    _remove_participant_from_case = remove_participant_from_case()
    obj_to_file(
        _remove_participant_from_case,
        f"{outdir}/remove_participant_from_case.json",
    )

    _propose_embargo = propose_embargo()
    obj_to_file(_propose_embargo, f"{outdir}/propose_embargo.json")

    _choose_preferred_embargo = choose_preferred_embargo()
    obj_to_file(
        _choose_preferred_embargo, f"{outdir}/choose_preferred_embargo.json"
    )

    _accept_embargo = accept_embargo()
    obj_to_file(_accept_embargo, f"{outdir}/accept_embargo.json")

    _reject_embargo = reject_embargo()
    obj_to_file(_reject_embargo, f"{outdir}/reject_embargo.json")

    _add_embargo_to_case = add_embargo_to_case()
    obj_to_file(_add_embargo_to_case, f"{outdir}/add_embargo_to_case.json")

    _activate_embargo = activate_embargo()
    obj_to_file(_activate_embargo, f"{outdir}/activate_embargo.json")

    _announce_embargo = announce_embargo()
    obj_to_file(_announce_embargo, f"{outdir}/announce_embargo.json")

    _remove_embargo = remove_embargo()
    obj_to_file(_remove_embargo, f"{outdir}/remove_embargo.json")

    _create_note = create_note()
    obj_to_file(_create_note, f"{outdir}/create_note.json")


if __name__ == "__main__":
    main()
