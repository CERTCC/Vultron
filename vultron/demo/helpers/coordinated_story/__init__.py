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
"""Story fragments of the Reporter → Coordinator → Vendor family.

The opening every scenario of this family tells is written here **once**: the
Reporter tells the Coordinator, the Coordinator engages the case, the
Coordinator invites the Vendor, the Vendor accepts and the replicas converge.
Each scenario then assembles its own story from the longest prefix it shares
with its siblings plus its continuation
(:mod:`vultron.demo.helpers.story`), so no two of them place the opening by
hand (DEMOMA-17-001, DEMOCI-11-018).

The prefixes nest, one per shared stretch, so a sibling cannot slip a step in
before a branch point (``notes/demo-scenario-tree.md`` § "Composition"):

* :data:`REPORTER_TELLS_THE_COORDINATOR` stops where the Coordinator's
  decision falls: the Reporter has told it and it has engaged the case, and it
  has invited nobody yet.  The two-coordinator pair parts here
  (``coordinator-invite-whom:coordinator``,
  :mod:`vultron.demo.helpers.two_coordinator_story`).
* :data:`COORDINATOR_INVITES_VENDOR` stops where the Vendor's decision falls.
  The Invite has been delivered, so the CASE_MANAGER has seated the Vendor's
  inert participant with the role the Invite offers and the harness can read
  it (CM-17-003, DEMOCI-11-013, DEMOCI-11-047), and the Vendor has not answered yet.
  ``rcv-reject`` parts here.
* :data:`VENDOR_JOINS_THE_CASE` continues through the Vendor's acceptance and
  the replica convergence, and stops where the Reporter's decision falls.
  The embargo pair parts here (``reporter-after-join:propose-embargo``,
  :mod:`vultron.demo.helpers.coordinated_embargo_story`).
* :data:`REPORTER_ASKS_THE_VENDOR` continues through the note thread the
  ``ask-vendor`` choice posts, and stops where the Coordinator's decision
  falls.  ``rcv`` and ``rcvcv`` part here.

The family's three fixed-role members are seated under :data:`REPORTER`,
:data:`COORDINATOR` and :data:`VENDOR` whatever its own ``ROLES`` calls them,
so one copy of each fragment serves every scenario: ``rcvcv`` names its first
Coordinator ``c1`` on the command line and in its devlogs, and the story still
reaches it as the Coordinator it is.  A scenario's **character actors** are
seeded and seated by the fragment that brings each into the case
(:meth:`~vultron.demo.helpers.story.StoryState.seat`), never by the shared
opening: what the opening writes before the case exists is part of the bytes
its siblings must match (DEMOCI-11-018).

The package is split by concern (CS-18-005): :mod:`.cast` holds the cast
names, labels, budgets and the cast opening; :mod:`.opening` the shared
opening and its named prefixes; :mod:`.joining` the join helpers both of
those use; and :mod:`.continuations` the continuations more than one
scenario tells.  Every public name is re-exported here (CS-18-003).
"""

from vultron.demo.helpers.coordinated_story.cast import (
    COORDINATOR,
    COORDINATOR_LABEL,
    CROSS_CONTAINER_TIMEOUT,
    OWNER_TRIAGE_TIMEOUT,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    VENDOR_LABEL,
    coordinated_cast_members,
    coordinated_open_cast,
    coordinated_seats,
    open_coordinated_cast,
    seat_character_actors,
)
from vultron.demo.helpers.coordinated_story.continuations import (
    close_the_case,
    coordinator_and_reporter_publish,
    everyone_closes,
    everyone_publishes,
    report_fix_ready,
    reporter_asks_about_the_rejection,
    reporter_replica_converges,
    reporter_then_coordinator_close,
    reports_published,
    the_coordinator_publishes_and_the_embargo_ends,
    vendor_notifies_fix_ready,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.coordinated_story.joining import (
    await_reporter_case_replica,
    invitee_joins_the_case,
    invitee_triages_after_joining,
)
from vultron.demo.helpers.coordinated_story.opening import (
    COORDINATOR_INVITES_VENDOR,
    ENGAGED_CASE,
    REPORTER_ASKS_THE_VENDOR,
    REPORTER_TELLS_THE_COORDINATOR,
    TIMELINE_ANSWER,
    VENDOR_JOINS_THE_CASE,
    coordinator_invites_vendor,
    replicas_converge_with_vendor,
    reporter_asks_about_the_timeline,
    reporter_tells_coordinator,
    vendor_accepts_and_joins,
    vendor_rejects_invite,
)

__all__ = [
    "ENGAGED_CASE",
    "COORDINATOR",
    "COORDINATOR_INVITES_VENDOR",
    "COORDINATOR_LABEL",
    "CROSS_CONTAINER_TIMEOUT",
    "OWNER_TRIAGE_TIMEOUT",
    "REPORTER",
    "REPORTER_ASKS_THE_VENDOR",
    "REPORTER_LABEL",
    "REPORTER_TELLS_THE_COORDINATOR",
    "TIMELINE_ANSWER",
    "VENDOR",
    "VENDOR_JOINS_THE_CASE",
    "VENDOR_LABEL",
    "await_reporter_case_replica",
    "close_the_case",
    "coordinated_cast_members",
    "coordinated_seats",
    "coordinated_open_cast",
    "coordinator_and_reporter_publish",
    "coordinator_invites_vendor",
    "everyone_closes",
    "everyone_publishes",
    "invitee_joins_the_case",
    "invitee_triages_after_joining",
    "open_coordinated_cast",
    "report_fix_ready",
    "vendor_notifies_fix_ready",
    "reporter_asks_about_the_rejection",
    "reports_published",
    "the_coordinator_publishes_and_the_embargo_ends",
    "reporter_asks_about_the_timeline",
    "reporter_replica_converges",
    "reporter_tells_coordinator",
    "reporter_then_coordinator_close",
    "replicas_converge_with_vendor",
    "seat_character_actors",
    "vendor_accepts_and_joins",
    "vendor_rejects_invite",
    "vendor_reports_the_fix_ready",
]
