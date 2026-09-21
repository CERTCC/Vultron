---
source: CONCERN-3433
timestamp: '2026-09-21T18:34:05.812153+00:00'
title: 'ChoosePreferredEmbargo is emit-only: no ActivityPattern, no MessageSemantics'
type: learning
---

## Original concern

`ChoosePreferredEmbargo` (`as:Question`) has a wire class
(`_ChoosePreferredEmbargoActivity`) and a factory
(`choose_preferred_embargo_activity`, tested in
`test/wire/as2/factories/test_embargo_factories.py`), but it has **no registered
`ActivityPattern`** in `vultron/wire/as2/extractor/_instances.py` and **no
`MessageSemantics` member**.

Consequences:

- A receiving Vultron actor cannot dispatch the activity. It extracts to
  `UNKNOWN`.
- It is absent from `ROW_SPECS` in `vultron/metadata/msm/_mapping.py`, so it never
  appears in the rendered message-mapping tables, and the MSM-06-002 ratchet does
  not notice because the ratchet is keyed on `MessageSemantics` members.
- The embargo poll it exists to express therefore cannot be answered by a peer.

Found while reducing `docs/howto/activitypub/activities/` to task guides (#3003).
The how-to guide had been instructing readers to send it and collect answers.

The issue asked: decide whether the multi-candidate embargo poll is in scope for
the protocol — build it out, or retire the class and factory.

## Outcome — retired

**Resolved**: 2026-09-21 — the poll is out of scope. ADR-0100 records the
decision; implementation tracked in #3469 and #3470.

Three facts found while measuring it, none of which were in the issue, decided it:

1. **The issue understated the breakage.** The activity does not extract to
   `UNKNOWN` — it is *refused at `parse_activity`*. `as_Question` types
   `anyOf`/`oneOf` as a single value where AS2 defines a collection, and the
   subclass declared `any_of`/`one_of` beside the inherited fields: four fields,
   two wire aliases. Serialization resolved the collision last-writer-wins;
   validation bound the inherited singular field. The class could emit and never
   parse, including its own output. Generalised lesson now in
   `notes/activitystreams-semantics.md`: **a subclass field whose wire alias
   collides with an inherited one is write-only**, because serialization and
   validation resolve the collision in opposite directions.
2. **There was no answer form.** `_EmAcceptEmbargoActivity.object_` is a required,
   inline-typed `Invite`; a candidate `EmbargoEvent` in a `oneOf` is not one. So
   the fix the issue proposed — add a pattern and a `MessageSemantics` — would
   have left the poll askable and still unanswerable. `docs/reference/messages/em.md`
   had claimed "the answer arrives as an `EA` or `ER` against whichever candidate
   is proposed"; that was not satisfiable.
3. **The protocol already answers this, sequentially.**
   `docs/topics/process_models/em/defaults.md` is normative and requires accepting
   the earliest-expiring open proposal and handling the rest as revisions — the
   *Shortest Embargo Proposed Wins* heuristic. A multi-candidate poll is the
   construct that heuristic replaces, and EMB-15-003 independently forbids
   introducing a new mechanism for competing terms.

A pattern for the poll would also have been the *first* `as_Question` pattern in
the registry — `_instances.py` has none — and would have arrived alongside the one
CBT-03-004's bootstrap-replay request still needs (#3471). That is a cost, not an
impossibility: SE-08-001 permits patterns sharing a verb given a discriminator,
and CBT-03-004 requires the replay request's `target` be the `case_actor_id`, so
`target_` with `strict=True` (SE-08-004) would separate them. A first draft of
this entry and of the ADR claimed the shape was *already occupied* and that
SE-08-001 *forbids* two patterns per activity; PR triage corrected both.

## Two findings that outlived the issue

**The stated rationale for retiring was only half true, and that mattered.** The
first justification drafted was "N `Invite`s already cover it, because
`pending_embargo_proposal_index` plus an optional `proposal_id` handles multiple
proposals." The data model does; the resolution path did not.
`find_embargo_proposal_id` returned the *first recorded* proposal, so after a
counter-proposal a default `accept` took the superseded terms — and that was
asserted as intended by an existing test. Nothing anywhere pruned the index (one
writer, no remover), and the neighbouring `proposed_embargoes` list turned out to
be pruned only on *teardown* — `reject_proposed_embargo_bt` omits the pruning
node, so a rejected proposal survives in both records. (The first draft of this
entry, the ADR and EP-08-003 all claimed `proposed_embargoes` was pruned on
rejection too; PR triage caught that it is not, which widened #3470 rather than
narrowing it.) Had that not been checked, the how-to would have been rewritten to
recommend "propose several sets of terms, each answered independently" — swapping a
true caveat for a false one. Instead the page keeps its existing advice with a new
reason, and EP-08 now states the ordering rule with a ratchet. The ordering rule
had existed only as prose in `docs/topics/`, which is exactly why nothing enforced
it: **`spec-dump` is the corpus agents read, so a normative rule absent from
`specs/` is invisible to implementation.**

**`as:Question` has no dispatch path at all, and one live activity depends on it.**
Filed as #3471. `bootstrap_replay_question_activity` (CBT-03-004, a `SHOULD`) is
emitted for real from `vultron/adapters/driving/fastapi/inbox_pending_queue.py`
when a pre-bootstrap queue expires, and no recipient can route it; the sender logs
success and waits for a reply that cannot come. `test_vocab_examples_dispatchable.py`
caught the poll but structurally cannot catch this one — its collector scans the
`vocab_examples` module (plus `submit_report_tutorial`), and there is no bootstrap
`Question` example in that corpus at all; the factory lives in
`vultron/wire/as2/factories/case.py`, outside the scanned package. **A gate scoped
to the example corpus does not cover factories only production code calls, so
"every example is dispatchable" is not "every activity we emit is dispatchable".**
Note the near-miss diagnosis: the obvious explanation is the collector's
"no *required* arguments" rule and this factory's three required arguments, but
relaxing that rule would not reach a factory the collector never walks. Whether `Question` is even the right vocabulary for a
request/response exchange, when activities here are state-change notifications, is
open in that issue.

## Artifacts

Docs PR: <https://github.com/CERTCC/Vultron/pull/3476>
ADR: `docs/adr/0100-no-multi-candidate-embargo-poll.md`
Spec: `specs/embargo-policy.yaml` EP-08 (EP-08-001, EP-08-002, EP-08-003)
Implementation: #3469 (retire the poll, fix `as_Question`), #3470 (earliest-expiration
resolution order, prune the index)
Filed separately: #3471 (`as:Question` dispatch path)
