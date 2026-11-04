---
title: >-
  A refusal reason shared by every message type has to be composed from the
  facts that differ, or it is false of some of the receivers it refuses
type: learning
timestamp: 2026-11-03T00:00:00+00:00
source: ISSUE-5041
signal: spec-contradiction
---

**Decided, in #5041 (maintainer decision 2026-11-03).** The rule now lives in
HP-01-039: the path stage composes the refusal reason in one place, from the
receiver's resolved path and the message type's declaration. ADR-0153 detail 5
was amended to match (revision 3), and ADR-0153's `create_recommendation_answer_received_tree`
migration — the first replica-only declaration — ships with it, so both arms of
the composer are pinned through a real tree. Nothing here is open.

What generalises, for the next reason shared across message types:

- **"One reason, composed in one place" and "one fixed string" are not the same
  requirement.** ADR-0153 detail 5 asked for the first and specified the second,
  which was the defect. A reason stays uniform in *shape* while varying with the
  facts that actually differ between the receivers it refuses. HP-01-005 asks for
  a reason that names what is missing, so a string that cannot vary cannot name it.
- **A claim about the receiver has to be checked against every declaration the
  record's own later details create.** Detail 5's string was true for each
  declaration detail 4 listed — all of them manager-inclusive — and false for the
  replica-only one detail 7 introduces two paragraphs later. Reading the details in
  order makes the premise look sound. When a record mandates a sentence about an
  actor, enumerate the configurations the record itself permits before pinning it
  in a test.
- **Removing the subject is not resolving the contradiction.** The first build of
  #5041 reverted its one replica-only migration, so no test pinned a false string
  and the contradiction stayed invisible to CI while remaining true of #5042 and
  #5043. Completeness-doctrine Gate 2 wants the premise settled, not the evidence
  withdrawn.
