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
"""The shared opening of the vendor-first family, and its prefixes.

The Reporter tells the Vendor, the Vendor engages the case, and the
Reporter asks about a workaround: the fragments every scenario of the
family tells, and the nested prefixes :data:`REPORTER_TELLS_THE_VENDOR` ⊂
:data:`THE_VENDOR_ANSWERS_THE_REPORTER` built from them
(``notes/demo-scenario-tree.md`` § "Composition").
"""

from __future__ import annotations

import logging

from pydantic import JsonValue

from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    await_reporter_case_replica,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_QUESTION,
    reporter_asks,
    vendor_answers_workaround,
)
from vultron.demo.helpers.polling import wait_for_case_participants
from vultron.demo.helpers.story import StoryProp, StoryState, choose, story
from vultron.demo.helpers.vendor_story.cast import (
    CASE_REPLICA_TIMEOUT,
    VENDOR,
    VENDOR_LABEL,
    VENDOR_TRIAGE_TIMEOUT,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
)
from vultron.demo.utils import demo_gate
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)


#: The case whose roster the Vendor has confirmed, as its id.  Read by the
#: first fragment of each scenario's continuation — the note thread, or
#: ``rv``'s own M1 check, whichever that scenario tells next — because the
#: Reporter and the Vendor both being seated is what every later step
#: presupposes: a roster that never arrived must stop the story rather than
#: post into a case the owner cannot vouch for, or check participants that
#: were never seated (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never Wrap
#: a Causal Wait in demo_check").  A flat story cannot nest those steps inside
#: the roster's gate, so the gate keeps this and they read it.
THE_VENDORS_CASE: StoryProp[str] = StoryProp(
    "case whose roster the Vendor confirmed", str
)

#: The Reporter's workaround question, as the note the case holds.  Read by
#: ``rv``'s final case check, which asserts both notes of the thread are on
#: the case (:func:`~vultron.demo.helpers.verification\
#: .verify_receiver_case_state`).
REPORTERS_QUESTION: StoryProp[as_Note] = StoryProp(
    "Reporter's workaround question", as_Note
)

#: The Vendor's answer to it.  Read by every scenario whose joiners reply to
#: the thread the opening posted rather than opening one of their own, and by
#: ``rv``'s final case check (DEMOCI-11-017).
VENDORS_ANSWER: StoryProp[as_Note] = StoryProp(
    "Vendor's workaround answer", as_Note
)


def the_reporter_tells_the_vendor(state: StoryState) -> None:
    """The Reporter submits its report; the Vendor engages the case.

    The Vendor validates the report and engages the case (RM→ACCEPTED),
    holding CASE_OWNER; each step is gated on its own RM state.  The Reporter
    is seated when the case is created (CP-09-002), so it is never invited.

    The case is recorded as soon as the triage returns it, which arms the
    ledger dump at the first instant there is anything to dump, so every step
    below can fail without costing the ledgers (DEMOMA-23-003, ISSUE-2239).
    Then the roster wait is a ``demo_gate``: the Reporter and the Vendor both
    being seated is the precondition for every later step, so a timeout skips
    the Reporter's replica check, the re-read and :data:`THE_VENDORS_CASE`,
    and the fragment that runs next stops the story rather than acting on a
    case the owner cannot vouch for (DEMOCI-01-011).
    """
    reporter_tells_the_vendor(state)


def reporter_tells_the_vendor(
    state: StoryState,
    *,
    csaf_document: dict[str, JsonValue] | None = None,
) -> None:
    """Run the opening's acts, attaching *csaf_document* to the report if given.

    The body of :func:`the_reporter_tells_the_vendor`, which every
    vendor-first scenario tells, and of the ``rv-csaf`` scenario's opening,
    which differs only in what the Reporter submits: a CSAF 2.1 vulnerability
    report and no report name, so the trigger names the report from the
    document (CSAF-04-010).  One copy of the triage, the roster gate and the
    replica wait serves both (DEMOMA-17-001).

    Args:
        state: The running story's state.
        csaf_document: The CSAF vulnerability report the Reporter attaches,
            as a JSON object; ``None`` submits the family's plain report.
    """
    reporter = state.actor(REPORTER).actor
    vendor = state.actor(VENDOR).actor
    owner_client = state.client(VENDOR)
    report, offer = (
        reporter_submits_report(
            receiver_client=owner_client,
            reporter=reporter,
            receiver=vendor,
            reporter_client=state.client(REPORTER),
        )
        if csaf_document is None
        else reporter_submits_report(
            receiver_client=owner_client,
            reporter=reporter,
            receiver=vendor,
            reporter_client=state.client(REPORTER),
            report_name=None,
            csaf_document=csaf_document,
        )
    )
    case = run_direct_path_rm_triage(
        receiver_client=owner_client,
        receiver=vendor,
        offer=offer,
        timeout_seconds=VENDOR_TRIAGE_TIMEOUT,
    )
    # Recorded here, at the first instant there is anything to dump, so every
    # step below can fail without costing the ledgers (DEMOMA-23-003,
    # ISSUE-2239) — including the gate that follows.
    state.open_case(case=case, report=report, offer=offer)

    with demo_gate(
        f"{VENDOR_LABEL} case reflects Reporter + {VENDOR_LABEL} participants"
    ):
        wait_for_case_participants(
            vendor_client=owner_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        # CLP-08-005: the Reporter needs the case before any later step
        # broadcasts Announce(CaseLedgerEntry) to it (Bug #2135).
        await_reporter_case_replica(state, CASE_REPLICA_TIMEOUT)

        # Re-read the case as the Vendor now stores it: the triage and the
        # participant seating have moved on since the trigger returned it.
        state.restate_case(
            as_VulnerabilityCase.model_validate(
                owner_client.get(owner_client.dl_path(case.id_))
            )
        )
        state.keep(THE_VENDORS_CASE, str(case.id_))


#: The opening every vendor-first scenario shares: the Reporter tells the
#: Vendor, and the Vendor engages the case and holds its roster.  Named rather
#: than assembled from the fragment at each call site, because assembling
#: siblings from fragments alone lets one of them slip a step in before the
#: branch point (``notes/demo-scenario-tree.md`` § "Composition").
REPORTER_TELLS_THE_VENDOR = story(
    choose("reporter-whom-to-tell", "vendor", by=REPORTER),
    the_reporter_tells_the_vendor,
)


def the_reporter_asks_about_the_workaround(state: StoryState) -> None:
    """The Reporter asks whether a workaround exists; the Vendor answers.

    The thread every vendor-first scenario posts before the Vendor's
    ``vendor-after-answer`` decision, which follows the Vendor's own answer in
    it (``notes/demo-scenario-registry.md``).  Both notes are kept: a
    continuation replies to the answer rather than opening a thread of its own
    (:data:`VENDORS_ANSWER`), and ``rv``'s final case check names both
    (:data:`REPORTERS_QUESTION`).

    Reads :data:`THE_VENDORS_CASE` first: the Reporter posts from its own
    replica of a case whose roster the owner has confirmed, so a roster that
    never arrived stops the story here (DEMOCI-01-011).
    """
    state.kept(THE_VENDORS_CASE)
    posted = reporter_asks(
        state.actor(REPORTER),
        state.client(VENDOR),
        state.case,
        WORKAROUND_QUESTION,
        [vendor_answers_workaround(state.actor(VENDOR))],
    )
    # strict=False, because a failed gate posts nothing at all and a failed
    # post reads back as None: fewer notes than props is the recorded-failure
    # case, which must keep nothing and let the fragments that read a prop
    # stop the story, not raise a shape error of its own (:func:`run_story`).
    props: tuple[StoryProp[as_Note], ...] = (
        REPORTERS_QUESTION,
        VENDORS_ANSWER,
    )
    for prop, note in zip(props, posted, strict=False):
        if note is not None:
            state.keep(prop, note)
    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


#: The opening through the note thread the Reporter opens, which stops where
#: the Vendor's ``vendor-after-answer`` decision falls.  ``rvv`` and the
#: ``rvcv`` pair start with it; ``rv`` tells the same two steps with two
#: replica checks of its own in between (the package docstring).
THE_VENDOR_ANSWERS_THE_REPORTER = story(
    REPORTER_TELLS_THE_VENDOR,
    the_reporter_asks_about_the_workaround,
)


__all__ = [
    "REPORTERS_QUESTION",
    "REPORTER_TELLS_THE_VENDOR",
    "THE_VENDORS_CASE",
    "THE_VENDOR_ANSWERS_THE_REPORTER",
    "VENDORS_ANSWER",
    "reporter_tells_the_vendor",
    "the_reporter_asks_about_the_workaround",
    "the_reporter_tells_the_vendor",
]
