---
source: CONCERN-4389
timestamp: '2026-10-09T16:33:25.029383+00:00'
title: ADRs carry implementation detail that goes stale while the decision stands
type: learning
---

Decision records accumulated implementation detail — class names, function
names, module paths, counts — that aged the moment the code was refactored,
while the decision it illustrated stood intact. The cost was not maintenance
effort but what agents carry: routine task context loaded record bodies, so a
stale-but-once-true sentence consumed working memory on a claim that was no
longer checkable and sent agents looking for symbols not in the tree.

**Resolved**: 2026-10-09 — planned as ADR-0127 plus four implementation
issues: #4409 (reflow the ten decision details of the one-object-model record
into a requirement group and convert the detail-number citations), #4410 (close the
pointer gaps on the records invisible from specs and notes), #4411 (stop loading
record bodies in routine task context, with a written exception list; blocked by
both preconditions), and #4412 (fail a pull request that writes an unresolvable
reference into a record it edits).

Docs PR: <https://github.com/CERTCC/Vultron/pull/4408>.
Decision record: `docs/adr/0127-decision-records-leave-routine-agent-context.md`.
Notes: `notes/specs-vs-adrs.md`.

**What the planning measurement changed.** The concern's remaining-work list
included working the backlog of stale references and reporting an advisory count
of it. Classifying all 217 references in the 48 affected records by section
collapsed both items: 106 sit inside a Decision Outcome or Considered Options
section on 34 records, where the lifecycle edit tiers would make a rename cost a
dated amendment, and 54 sit in "Context and Problem Statement", which the
concern itself says stays because it is how the code looked when the decision was
made. Once nothing routinely reads a body, an aged reference in historical prose
is not a defect at all, so no issue owns the scrub and no advisory count is
reported — a count would re-describe accurate history as debt and invite the
scrub back. That conclusion is recorded in ADR-0127, in `notes/specs-vs-adrs.md`,
in the index preamble and in the root AGENTS.md pitfall cell, because it is the
consequence most likely to be re-derived as work by a later session.

**Two findings worth carrying forward.** The phantom-symbol half of the
spec-corpus check matches only backticked all-caps identifiers containing an
underscore, so it cannot see a stale class name or function name — and every
headline case in the concern was one of those shapes. Extending that check to
record bodies without widening the shape would have caught almost nothing.
Separately, the check the concern asked for is diff-scoped and the spec linter is
corpus-wide and hard-failing; the merge-base comparison it needs already exists
in the record lifecycle module, which is where #4412 puts it.

**What made the replacement hint source cheap.** The context-loading step reads
record bodies partly to find which requirements to load next. Measured on
2026-10-09, 610 requirements already carried a structured `adr:` edge reaching 86
of the 120 live records — denser than the hand-written prose citations it
replaces — so reading those edges in the record-to-requirements direction needs
no new generated artifact and no freshness check.

**Routed out, already filed.** #4390 rewrites the requirements still encoding the
direction the one-object-model record repealed. #4391 covers the custom
behavior-tree engine record, still accepted for an approach the project reversed
— a wrong record rather than a stale one, which belongs to decision auditing.
