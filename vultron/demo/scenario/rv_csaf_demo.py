#!/usr/bin/env python

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

"""rv-csaf (Reporter + Vendor): a case that starts from a CSAF report.

The Reporter calls ``submit-report`` with a CSAF 2.1 vulnerability report
attached and states no report name, no summary and no embargo end.  The
trigger checks the document against the schema and fills the report from it
(CSAF-04-009, CSAF-04-010).  The Vendor validates the report and engages the
case, and the CASE_MANAGER creates the case from the document the proposal's
Offer carries (CSAF-02-002): its name is the document's ``document.title``,
its summary the document-level ``summary`` note, and its embargo ends at the
document's ``disclosure_date`` (CSAF-03-001, CSAF-03-007).

The Vendor publishes a 30-day default embargo first, so the document's date
competes with an actor default under shortest-wins (EP-04-003).  The
document's date is the shorter term, so it is the active embargo's end and
the Vendor's default is the pending revision.  The document and its dates
are :mod:`vultron.demo.helpers.csaf_report`.

After the case starts, the story goes on the way ``rv`` does: the Reporter's
workaround question and the Vendor's answer, the Vendor's fix, the
publication and the closure, told by the same fragments
(:mod:`vultron.demo.helpers.vendor_story`, DEMOMA-17-001, DEMOMA-28-005).

Cast (DEMOCI-11-020): the Reporter (slot 0), the Vendor (slot 1, the first
Vendor, CASE_OWNER throughout) and the dedicated CaseActor, which holds the
canonical case and ledger (DEMOMA-06-005).

Spec: DEMOMA-28.
"""

import logging
from datetime import datetime, timedelta
from typing import cast

from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import REPORTER_SLOT, VENDOR_SLOT
from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.csaf_report import (
    CSAF_REPORT_CONTENT,
    CSAF_REPORT_SUMMARY,
    CSAF_REPORT_TITLE,
    VENDOR_DEFAULT_EMBARGO,
    csaf_disclosure_date,
    csaf_vulnerability_report,
)
from vultron.demo.helpers.embargo import publish_embargo_policy
from vultron.demo.helpers.embargo_outcome import (
    offered_terms,
    verify_reporter_terms_won,
)
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    choose,
    run_story,
    story,
)
from vultron.demo.helpers.story_cast import (
    CASE_ACTOR_NAME,
    CastContainer,
    story_clients,
)
from vultron.demo.helpers.vendor_story import (
    VENDOR,
    VENDOR_LABEL,
    both_close,
    both_publish,
    dump_vendor_ledgers,
    reporter_tells_the_vendor,
    required_participants_are_present,
    the_reporter_asks_about_the_workaround,
    the_vendor_reports_the_fix_ready,
    vendor_open_cast,
)
from vultron.demo.helpers.verification import verify_case_actor_holds_records
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    setup_demo_logging,
)
from vultron.demo.wall_clock import from_now
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

DEMO_NAME = "rv-csaf"

#: What this scenario calls its one Vendor on the command line, as ``rv``
#: does: the family's story labels say ``Vendor1`` whatever ``ROLES`` says.
VENDOR_ROLE_LABEL = "Vendor"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_ROLE_LABEL, has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

#: ``vultron-demo rv-csaf --help`` text.
CLI_HELP = """Run the rv-csaf demo: a case that starts from a CSAF report.

The Reporter submits a CSAF 2.1 vulnerability report and states no report
name, summary or embargo end; the case takes all three from the document.
Requires the Reporter, Vendor and case-actor containers to be running.

Use ``--reporter-url`` / ``--vendor-url`` (or the cast's env vars,
``VULTRON_ACTOR0_BASE_URL`` / ``VULTRON_ACTOR1_BASE_URL``) to point
the demo at running containers.

\b
Workflow (titles match docs/topics/scenarios/rv-csaf.md):
  Setup. Seed both containers (actor records + peer registration).
  1. The Vendor publishes a 30-day default embargo; the Reporter submits a
     CSAF vulnerability report whose disclosure date is 10 days away; the
     Vendor validates the report and engages the case (M1).
  2. The canonical case's name is the document's title and its summary the
     document's summary note (M2); its active embargo ends at the
     document's disclosure date, with the Vendor's longer default pending
     (M3).
  3. The Reporter asks about a workaround; the Vendor answers.
  4. The Vendor reports the fix ready (M4-M5).
  5. The Vendor and the Reporter publish; the embargo ends (M6).
  6. The Reporter closes the case, then the Vendor, the Case Owner (M7).
"""

#: The ``disclosure_date`` of the document the Reporter sent, as an instant.
#: Read by the M3 check, which compares the active embargo's end with it.
THE_CSAF_DISCLOSURE_DATE: StoryProp[datetime] = StoryProp(
    "CSAF report's disclosure date", datetime
)


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def the_reporter_sends_a_csaf_report(state: StoryState) -> None:
    """The Vendor sets its default embargo; the Reporter sends a CSAF report.

    The Vendor publishes its actor default first, on its own profile, so the
    document's disclosure date has a default to compete with under
    shortest-wins (EP-04-003).  The Reporter then writes the document and
    submits it with no report name, summary or embargo end, and the shared
    opening's triage, roster gate and replica wait run as for every
    vendor-first scenario (:func:`~vultron.demo.helpers.vendor_story\
    .reporter_tells_the_vendor`).

    The policy is a ``demo_gate`` with the submission nested in it: without
    the policy the document's date wins uncontested, so the M3 check would
    read a case this scenario does not describe (DEMOCI-01-011).  The
    submission is a gate of its own, so a refused submission is reported
    under its own name and not the policy's.
    """
    with demo_gate(
        f"{VENDOR_LABEL} publishes its default embargo policy"
        f" ({VENDOR_DEFAULT_EMBARGO.days} days)"
    ):
        publish_embargo_policy(
            state.client(VENDOR),
            state.actor(VENDOR).actor,
            VENDOR_DEFAULT_EMBARGO,
        )
        with demo_gate(
            f"Reporter sends {VENDOR_LABEL} a CSAF vulnerability report"
        ):
            written = from_now(timedelta())
            state.keep(THE_CSAF_DISCLOSURE_DATE, csaf_disclosure_date(written))
            reporter_tells_the_vendor(
                state,
                csaf_document=csaf_vulnerability_report(written),
                report_content=CSAF_REPORT_CONTENT,
            )


def the_case_starts_from_the_csaf_report(state: StoryState) -> None:
    """The case takes its name, summary and embargo end from the CSAF report.

    Milestones M1 to M3 of the scenario's spec group.  M1 reads the Vendor's
    replica, as ``rv``'s does.  The report the Offer carries is checked next,
    for the name the trigger gave it from the document (CSAF-04-010).  M2 and
    M3 read the canonical case in the dedicated case-actor container, which
    is where the CASE_MANAGER filled it (CSAF-02-002, DEMOMA-06-004).  The
    canonical read is a ``demo_gate``, because both milestones compare that
    case's fields.
    """
    disclosure = state.kept(THE_CSAF_DISCLOSURE_DATE)
    required_participants_are_present(
        state,
        check=(
            "M1: required participants (vendor + reporter + case-actor, ≥3),"
            " embargo active, reporter has case replica"
        ),
    )
    with demo_check(
        "The Offer's report is named from the CSAF document.title"
        " (CSAF-04-010)"
    ):
        if state.report.name != CSAF_REPORT_TITLE:
            raise AssertionError(
                f"report name {state.report.name!r}, expected the CSAF title"
                f" {CSAF_REPORT_TITLE!r}"
            )
    with demo_gate(
        "Dedicated case-actor container holds the case created from the"
        " CSAF report"
    ):
        case = verify_case_actor_holds_records(
            state.case_actor_client, state.case.id_
        )
        with demo_check(
            "M2: case name is the CSAF document.title and its summary the"
            " document-level summary note (CSAF-03-007)"
        ):
            if case.name != CSAF_REPORT_TITLE:
                raise AssertionError(
                    f"case name {case.name!r}, expected the CSAF title"
                    f" {CSAF_REPORT_TITLE!r}"
                )
            if case.summary != CSAF_REPORT_SUMMARY:
                raise AssertionError(
                    f"case summary {case.summary!r}, expected the CSAF"
                    f" summary note {CSAF_REPORT_SUMMARY!r}"
                )
        _the_embargo_ends_at_the_disclosure_date(state, case, disclosure)


def _the_embargo_ends_at_the_disclosure_date(
    state: StoryState, case: as_VulnerabilityCase, disclosure: datetime
) -> None:
    """M3: the CSAF date is the active embargo's end; the default is pending.

    The trigger stated the document's ``disclosure_date`` as the Offer's
    ``proposedEmbargo`` (CSAF-04-010), and the CASE_MANAGER activated it as
    the shorter term, registering the Vendor's 30-day default as the pending
    revision (EP-04-003, CSAF-03-001).  The Offer's terms are a gate: the
    embargo checks compare against them.
    """
    with demo_gate(
        "M3: the Offer proposes the CSAF disclosure date as the embargo end"
        " (CSAF-04-010)"
    ):
        proposal = offered_terms(state.offer, state.report.id_)
        if proposal.end_time != disclosure:
            raise AssertionError(
                f"the Offer proposes an embargo ending {proposal.end_time},"
                f" expected the CSAF disclosure date {disclosure}"
            )
        case_actor_client = state.case_actor_client
        verify_reporter_terms_won(
            case_actor_client,
            # Bound: verify_case_actor_holds_records refused an unbound client.
            cast(str, case_actor_client.actor_id),
            case,
            proposal.id_,
            disclosure,
            default=VENDOR_DEFAULT_EMBARGO,
            revision_check=(
                f"M3: the pending revision runs the {VENDOR_LABEL}'s"
                f" {VENDOR_DEFAULT_EMBARGO.days}-day default (shortest-wins)"
            ),
        )


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.
    """
    dump_vendor_ledgers(state, (REPORTER, VENDOR))


#: The rv-csaf story: the Reporter sends a CSAF report, the case starts from
#: it, and then ``rv``'s note thread and two-party ending.  It parts from every other
#: scenario at the root, so it shares no recorded prefix (DEMOCI-11-017).
STORY = story(
    choose("reporter-whom-to-tell", "vendor-csaf", by=REPORTER),
    the_reporter_sends_a_csaf_report,
    the_case_starts_from_the_csaf_report,
    the_reporter_asks_about_the_workaround,
    the_vendor_reports_the_fix_ready,
    both_publish,
    both_close,
)


def run_rv_csaf_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the rv-csaf (Reporter + Vendor) CVD workflow."""
    logger.info("=" * 80)
    logger.info("rv-csaf DEMO: a case that starts from a CSAF report")
    logger.info("=" * 80)
    open_cast = vendor_open_cast(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=_dump_ledgers,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
    )
    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success
    # (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)
    logger.info("rv-csaf DEMO COMPLETE ✓")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="rv-csaf",
    participants="Reporter + Vendor",
    feature="Case from a CSAF report",
    in_pr_set=False,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the rv-csaf (Reporter + Vendor) demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the dedicated CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    clients = story_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer(VENDOR, VENDOR_ROLE_LABEL, vendor_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rv_csaf_demo(
        reporter_client=clients[REPORTER],
        vendor_client=clients[VENDOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            vendor=(clients[VENDOR], vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
