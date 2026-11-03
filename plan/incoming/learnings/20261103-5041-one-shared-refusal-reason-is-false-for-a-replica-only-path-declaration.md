---
title: >-
  ADR-0153's single refusal reason is false of the receiver it refuses once a
  message type declares the participant-replica path alone
type: learning
timestamp: 2026-11-03T00:00:00+00:00
source: ISSUE-5041
signal: spec-contradiction
---

ADR-0153 detail 5 is unconditional: "A message whose type declares no branch for
the receiver's path is `REFUSED` with the reason 'not the CASE_MANAGER of case
…', composed by the factory and identical for every message type." #5041's AC-3
restates it, and the mechanism #5041 built composes exactly that one string.

HP-01-005 is also a MUST, and asks for something the single string cannot always
give: `REFUSED` "with a reason that names what is missing".

The two agree for every declaration that *includes* the manager path, which is
why the contradiction is invisible in #5041 as shipped:

- `{CASE_MANAGER}` refuses at the participant-replica and no-case paths, where
  the receiver really does not hold the role.
- `{CASE_MANAGER, PARTICIPANT_REPLICA}` refuses only at the no-case path, where
  the receiver holds no replica and so cannot hold the role.

They contradict each other for a declaration that *omits* it. A message type
whose work is the participant replica's alone — the recommendation answer is the
first, and ADR-0153 detail 7's replica-gated trees are the rest — refuses at the
case's actual CASE_MANAGER, and tells it "not the CASE_MANAGER of case X". The
statement is false of the receiver, and it names nothing that is missing: what
is missing is a branch, not the role.

Why a future agent will hit this and not see it coming: the one declaration the
record's own detail 4 lists (the embargo Invite and Remove, the role and
ownership offers, `Add(CaseStatus)`, `Announce`, and the case invites) are all
manager-inclusive, so reading detail 4 and detail 5 together suggests the
premise holds everywhere. It is detail 7, two paragraphs later, that turns the
participant-replica-gated factory into a declared branch — and that is the
declaration which breaks it.

Issue #5041 resolved it by removing the subject rather than acting on the
premise (completeness-doctrine Gate 2): the one replica-only migration it had
was reverted, so nothing false shipped and no test pins a false string. The
question is live for #5042 and #5043, which migrate the embargo and the case,
participant, report and status trees and will declare replica-only paths.

The shapes a decision could take, so the next reader does not re-derive them:

1. Keep the one string and accept it is a label for "this receiver's path is not
   one this message type handles" rather than a claim about the role. Cheapest,
   and the reason stops being readable as a sentence about the receiver.
2. Compose the reason from the resolved path and the declaration — still one
   function, one place, the same shape for every message type, but a different
   string per path. Satisfies HP-01-005; needs ADR-0153 detail 5 and the AC
   amended, and every test that pins the string updated.
3. Keep the one string for a manager-inclusive declaration and give a
   replica-only one its own, with the rule stated in HP-01-005's group rather
   than left to each tree. Two reasons, both factory-composed.

Option 2 is the only one that satisfies both MUSTs as written.
