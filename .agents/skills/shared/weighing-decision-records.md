# Weighing a Decision Record

Apply this whenever you read a decision record (ADR) body. Routine task
context reaches records only by title and by the `adr:` edges on requirements
(`deepen-context` Step 2). The skills that read bodies in full are listed
there, and each one weighs what it reads by these rules.

A record says what was decided and why, as of when it was written. It is
history, not a description of today's code (ADR-0127). The rules below are
about how far to trust that decision. They do not cover whether to trust its
picture of the code, which is history in every case.

## Settled or challengeable

**Weigh each record by how settled it is. Not every record is equally solid
fact.** A record that is `status: accepted`, agrees with its own prose, and is
not violated by the code stops you re-arguing a settled choice. Build on it and
leave it closed. A record is **challengeable** when any of these hold. Check a
challengeable record against the current code before you rely on it:

- its `status:` is blank, `proposed`, `deprecated`, or `superseded`;
- its `status:` says `accepted` but the prose hedges (e.g. "formed in sand",
  "not concrete", "provisional", "forward-looking", "SHOULD refine this ADR");
- the section it sits under in `docs/adr/index.md` disagrees with its own
  `status:` field;
- the code you are about to touch appears to contradict what the record
  asserts.

When a relevant record is challengeable, tell the caller and check its claim
against the code before you build on it. If the record looks wrong or stale
(not just imprecise for your task), it is a landmine: name it to the caller and
route it to the `decision-audit` skill.

## A stale code reference is not a challenge

A class, function or path in a body that no longer exists does not make the
decision challengeable. A refactor never has to update a record, so an aged
reference is expected (ADR-0127). The current shape is in the specs and notes
that cite the record. Challenge the *decision* only when its premise is in
doubt.
