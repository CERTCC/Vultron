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
"""Story fragments of the vendor-first half of the tree: the Reporter tells a Vendor.

``rv``, ``rvv``, ``rvcv-extension`` and ``rvcv-handoff`` all open the same
way — the Reporter submits its report to a Vendor, the Vendor validates it and
engages the case as CASE_OWNER, and the Reporter then asks whether a
workaround exists and the Vendor answers.  That opening is written here
**once** and each scenario assembles its story from the longest prefix it
shares with its siblings (:mod:`vultron.demo.helpers.story`), so no two of
them place it by hand (DEMOMA-17-001, DEMOCI-11-018).

The prefixes nest, one per shared stretch, so a sibling cannot slip an act in
before a branch point (``notes/demo-scenario-tree.md`` § "Composition"):

* :data:`REPORTER_TELLS_THE_VENDOR` stops once the Vendor holds the case and
  its roster.  All four scenarios start with it.
* :data:`THE_VENDOR_ANSWERS_THE_REPORTER` continues through the note thread
  and stops where the Vendor's ``vendor-after-answer`` decision falls, which
  follows its own answer in that thread.  ``rvv`` and the ``rvcv`` pair part
  here — ``rv`` tells the same two steps with two replica checks of its own in
  between, which write nothing and so move no byte of its recording
  (``vultron/demo/scenario/rv_demo.py``).
* :data:`~vultron.demo.helpers.vendor_coordinator_story\
  .THE_VENDOR_INVITES_A_COORDINATOR` continues through the Coordinator's join
  and stops where the owner's ``owner-keep-case`` decision falls.  The
  ``rvcv`` pair parts there.

The family seats its Reporter under :data:`REPORTER` and its first Vendor
under :data:`VENDOR`, whatever each scenario's ``ROLES`` calls them: the
Reporter's cast name is the one the continuations both halves of the tree
share read it under (:mod:`vultron.demo.helpers.owner_decision_story`), and
one copy of each fragment here then serves every scenario.  A scenario's
further containers — the second Vendor, and the Coordinator in the ``rvcv``
pair — are reset with the rest and seeded by the fragment that brings each
into the case, never by the shared opening: what the opening writes before the
case exists is part of the bytes its siblings must match (DEMOCI-11-018,
#5532).

The package groups the family by concern (CS-18-001), and every name a
submodule makes public is re-exported here, so an importer names the family
and not the submodule (CS-18-003).  :data:`REPORTER` and
:data:`REPORTER_LABEL` are the coordinator-first family's, re-exported too
because this family seats its Reporter under the same name:

* :mod:`~.cast` — the cast names, labels, timeouts and parts, and the
  reset/seed/seat opening of the family's containers.
* :mod:`~.opening` — the shared opening's fragments and its two nested
  prefixes.
* :mod:`~.continuations` — what more than one scenario tells after the
  opening: the milestones, the fix ready, the joiners' notes, the
  disclosure, and the two-party ending ``rv`` and ``rv-csaf`` share.

A test that patches a name a fragment looks up patches it on the submodule
that resolves it, never on this package: the package holds only the re-exports,
so a patch here reaches no fragment
(``test/demo_unit/test_story_patch_targets.py``).
"""

from vultron.demo.helpers.coordinated_story import REPORTER, REPORTER_LABEL
from vultron.demo.helpers.vendor_story.cast import (
    CASE_REPLICA_TIMEOUT,
    JOIN_TIMEOUT,
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR2_PART,
    VENDOR_LABEL,
    VENDOR_PART,
    VENDOR_TRIAGE_TIMEOUT,
    dump_vendor_ledgers,
    open_vendor_cast,
    vendor_open_cast,
    vendor_seats,
)
from vultron.demo.helpers.vendor_story.continuations import (
    both_close,
    both_publish,
    both_vendors_report_the_fix_ready,
    required_participants_are_present,
    the_disclosure_reached_every_replica,
    the_embargo_ends_for,
    the_fix_ready_milestones,
    the_fix_ready_reached_the_reporter,
    the_joiners_add_their_notes,
    the_vendor_reports_the_fix_ready,
    the_vendors_stopped_at_vfd,
)
from vultron.demo.helpers.vendor_story.opening import (
    REPORTER_TELLS_THE_VENDOR,
    REPORTERS_QUESTION,
    THE_VENDOR_ANSWERS_THE_REPORTER,
    THE_VENDORS_CASE,
    VENDORS_ANSWER,
    reporter_tells_the_vendor,
    the_reporter_asks_about_the_workaround,
    the_reporter_tells_the_vendor,
)

__all__ = [
    "CASE_REPLICA_TIMEOUT",
    "JOIN_TIMEOUT",
    "REPORTER",
    "REPORTERS_QUESTION",
    "REPORTER_LABEL",
    "REPORTER_TELLS_THE_VENDOR",
    "THE_VENDORS_CASE",
    "THE_VENDOR_ANSWERS_THE_REPORTER",
    "VENDOR",
    "VENDOR2",
    "VENDOR2_LABEL",
    "VENDOR2_PART",
    "VENDORS_ANSWER",
    "VENDOR_LABEL",
    "VENDOR_PART",
    "VENDOR_TRIAGE_TIMEOUT",
    "both_close",
    "both_publish",
    "both_vendors_report_the_fix_ready",
    "dump_vendor_ledgers",
    "open_vendor_cast",
    "required_participants_are_present",
    "the_disclosure_reached_every_replica",
    "the_embargo_ends_for",
    "the_fix_ready_milestones",
    "the_fix_ready_reached_the_reporter",
    "reporter_tells_the_vendor",
    "the_joiners_add_their_notes",
    "the_vendor_reports_the_fix_ready",
    "the_vendors_stopped_at_vfd",
    "the_reporter_asks_about_the_workaround",
    "the_reporter_tells_the_vendor",
    "vendor_open_cast",
    "vendor_seats",
]
