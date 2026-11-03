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
"""The two continuations of the ``owner-keep-case`` decision.

A Case Owner that has just taken a second participant on decides whether to
keep the case: keep it and approve the newcomer the joiner suggests
(``owner-keep-case:keep``, ADR-0026), or hand the case over and let the new
owner invite the newcomer itself (``owner-keep-case:offer-ownership``,
TRIG-11-001/002).  The decision appears in **both** halves of the tree — the
two-coordinator pair decides it with a Coordinator as owner and a second
Coordinator as the joiner, the vendor-first pair with a Vendor as owner and a
Coordinator as the joiner (``notes/demo-scenario-tree.md``
§ "Composition") — so each continuation is written here once and reads its
cast off the running story rather than naming either pair's actors
(DEMOMA-17-001).

A continuation therefore takes :class:`Part`\\ s, not clients: a part is the
name the story seats a cast member under plus what the scenario calls it in
its step and gate labels.  Everything else — the sessions, the case, the
case-actor client — comes from the :class:`~vultron.demo.helpers.story\
.StoryState`.

The handover's two halves are separated by a prop
(:data:`HANDED_OVER_CASE`): only the Case Owner may invite, so a transfer the
CASE_MANAGER never committed must stop the story rather than let the
would-be owner invite into a case it does not own (DEMOCI-01-011).

The package groups the decision by concern (CS-18-001), and every name a
submodule makes public is re-exported here, so an importer names the package
and not the submodule (CS-18-003):

* :mod:`~.parts` — :class:`Part`, the Reporter's part, the shared timeout and
  the CaseActor lookup both continuations make.
* :mod:`~.keep` — ``owner-keep-case:keep``.
* :mod:`~.handover` — ``owner-keep-case:offer-ownership``: the handover and
  the new owner's invite.

A test that patches a name a continuation looks up patches it on the
submodule that resolves it, never on this package: the package holds only the
re-exports, so a patch here reaches no continuation
(``test/demo_unit/test_story_patch_targets.py``).
"""

from vultron.demo.helpers.owner_decision_story.handover import (
    HANDED_OVER_CASE,
    the_new_owner_invites,
    the_owner_hands_the_case_over,
)
from vultron.demo.helpers.owner_decision_story.keep import (
    the_owner_approves_a_suggested_actor,
)
from vultron.demo.helpers.owner_decision_story.parts import (
    OWNER_DECISION_TIMEOUT,
    REPORTER_PART,
    Part,
    case_actor_participant,
)

__all__ = [
    "HANDED_OVER_CASE",
    "OWNER_DECISION_TIMEOUT",
    "REPORTER_PART",
    "Part",
    "case_actor_participant",
    "the_new_owner_invites",
    "the_owner_approves_a_suggested_actor",
    "the_owner_hands_the_case_over",
]
