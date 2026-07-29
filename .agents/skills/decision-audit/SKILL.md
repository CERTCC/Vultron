---
name: decision-audit
description: >
  Find and adjudicate stale or incorrect architectural decisions before they
  blow up in an implementation PR. Builds a risk-ranked inventory of both ADRs
  and spec groups that agents treat as solid fact but may encode a wrong or
  outdated premise, re-derives each suspect adversarially from current
  understanding, then runs a grill-me interview so the human decides the
  verdict and correction. Fixes confirmed landmines in a docs-only PR by
  default, or files a type:Concern when real uncertainty remains. Use when the
  user wants to audit decisions, hunt for bad assumptions in ADRs/specs, find
  stale-premise landmines, or says "audit our decisions" / "what decisions are
  we wrong about".
---

# Skill: Decision Audit

Surface architectural decisions that read as **settled fact** to coding agents
but actually encode a stale or incorrect premise — the class of problem that
stalls PRs when an implementer builds on a bad assumption and a maintainer has
to interject to unwind it.

This skill is modeled on `plan-issue`, **not** `build`: the goal is **shared
understanding through a `grill-me` interview** before anything is written. The
agent surfaces candidates and evidence and argues the counter-case; the **human
adjudicates** what is actually wrong and what the correction is. No spec, note,
or ADR is edited until the interview reaches a verdict.

The scoring rubric, all the shell/git commands, and the adversarial
re-derivation prompt template live in `REFERENCE.md` — load it in Phase 1.

## Constants

See `.agents/skills/shared/README.md` for project IDs and issue type IDs.

---

## Workflow

### Phase 0 — Sync & Orient

Move the worktree HEAD to `origin/main` so the audit reflects current specs,
notes, and ADRs. Do **not** `git checkout main` — that branch may be checked
out in another worktree.

```bash
git fetch origin main && git reset --hard origin/main
```

If this fails, stop and investigate. Then invoke the `orient-agent` skill to
load baseline context (glossary, specs, AGENTS.md, completeness doctrine,
ADR index).

### Phase 1 — Build the Risk-Ranked Candidate Inventory (read-only)

Landmines live in two artifact types: **ADRs** (decisions) and **spec groups**
(requirements). Both are treated as ground truth by implementers; both can
encode a stale or wrong premise. Score both. Run:

```bash
uv run python -m vultron.metadata.adr.decision_audit_inventory
```

This emits the risk-ranked inventory (ADRs and spec groups together) computed
from the signals below. `REFERENCE.md` documents the rubric and the manual
fallback commands if the helper is unavailable.

**Every candidate** is scored as **blast radius × confidence deficit** — a
shaky decision many things build on is the real danger; a shaky isolated one is
cheap to fix later.

**ADR signals:**

- **Blast radius** — dependent count from the `adr:` spec edges + prose
  citations (`grep -rioE 'ADR-[0-9]{4}' specs/ notes/`).
- **Confidence deficit**: non-`accepted` status; `status: accepted` while prose
  carries provisional markers (`formed in sand`, `not concrete`, `provisional`,
  `forward-looking`, `will converge`, `SHOULD refine`, `status will advance`);
  index-vs-frontmatter drift; amended-after-acceptance (`git log --follow`);
  layer-boundary friction (prose describing a construct without pinning its
  layer, e.g. "shape base class" against `BT-16-001`); named as wrong/stale in
  `plan/history/*/learning/` or `plan/incoming/learnings/`.

**Spec-group signals** (validated to discriminate — see `REFERENCE.md` for the
ones deliberately rejected as non-discriminating, e.g. pytest-coverage):

- **Blast radius** — inbound `relationships` edges (how many other specs
  depend on the group) + implementing-code references.
- **Confidence deficit**:
  - **Derives from a non-accepted ADR** — a requirement in the group has an
    `adr:` edge to an ADR whose status is not plain `accepted`
    (`proposed` / `accepted-provisional` / `superseded`). *Highest-value
    signal: it independently rediscovers CM-15, the ISSUE-1272 landmine.*
  - **Cites a superseded/archived ADR or note** in its rationale.
  - **`testable: false` cluster** — two or more non-testable requirements with
    no behavioral steps (an untested assertion agents take on faith).
  - **Purely prototype-scoped** group that production code now depends on.
  - **Named near a problem word** (`wrong`, `stale`, `contradict`, `supersede`,
    `ambiguous`, `mislead`, `rework`, …) in learnings/history.

Present the ranked list to the user via `ask_user`: highest-risk first,
**interleaving ADRs and spec groups**, each row tagged with its type and the
signals that fired. Let the user pick which candidate(s) to work, with a
"triage the whole list in order" option. **Nothing is written in this phase.**

### Phase 2 — Deepen Context (per selected candidate)

Invoke `deepen-context` with domain hints derived from the candidate's title.

- **ADR candidate**: read the full ADR, every spec whose `rationale` or `adr:`
  edge cites it, the dependent notes files, and representative implementing
  code.
- **Spec-group candidate**: read the whole group, its `relationships` targets
  and inbound references, the ADR(s) it derives from, and the code + tests that
  implement it. Pay special attention to whether the code actually does what
  the requirement says, and whether two requirements (or a requirement and its
  source ADR) contradict each other.

The point is to know what the decision/requirement *actually* claims and what
the code *actually* does.

### Phase 3 — Adversarial Re-Derivation (the core check)

Do **not** ask "is this still true?" in the abstract — that invites
confirmation. Instead, re-derive the decision from *current* understanding:
**given what we now know, would we make this same choice?**

Spawn an `Explore` or `Plan` agent with the counter-case prompt in
`REFERENCE.md` (it has an ADR variant and a spec-group variant): its job is to
argue why the decision/requirement may be **wrong or stale** given today's code
and specs, and to collect concrete contradiction evidence:

- spec text that conflicts with the code or with another spec,
- a requirement whose source ADR is no longer accepted (the premise moved),
- taxonomy/enumeration entries that don't match the implementation,
- layer or invariant statements that the code violates,
- dependents that would break or mislead if the premise is wrong.

Bring that evidence into the interview so it starts from a genuinely skeptical
position.

### Phase 4 — Grill-Me Adjudication (human decides)

Invoke `grill-me`. Ask one question at a time via `ask_user`, each with a
recommended answer grounded in the Phase 3 evidence. Resolve, per candidate:

1. **Verdict** — Is the decision:
   - **(a) still correct** — the premise holds; presentation may just need a
     status/confidence tidy;
   - **(b) correct but imprecisely stated** — the decision is right but the
     prose misleads (e.g. layer not pinned);
   - **(c) stale / superseded** — was right, no longer is;
   - **(d) wrong from the start** — the premise never held.
2. **The correction** — What is the accurate statement of the decision now?
   Draft it with the user.
3. **Blast radius confirmation** — Which dependent specs / notes / code
   inherited the bad premise and must change with it? Drive this off the
   reference grep and the spec edges graph.
4. **Disposition** — *ask this here, late, after understanding — not upfront.*
   - **Default recommendation: fix now.** Amend the ADR (status + prose) and
     the dependent specs/notes in a docs-only PR this session.
   - **Fall back to filing a `type:Concern`** *only* when real unresolved
     uncertainty remains that cannot be settled on sight. Recommend deferring
     only when genuinely blocked — not as the easy default.

Do **not** write anything until the interview reaches a verdict and the user
approves the correction and disposition.

### Phase 5 — Execute the Chosen Disposition

**Fix now (default):**

1. Create a task branch (`git checkout -b docs/decision-audit-<slug>`).
2. Apply the correction to the candidate:
   - **ADR**: edit `docs/adr/NNNN-*.md` — reconcile `status:` per the decision
     tree in `notes/specs-vs-adrs.md`, correct the prose, and if retired set
     `status: superseded` with a `superseded_by:` field and move the file to
     `docs/adr/archived/` (see the ADR archive convention below); regenerate
     the index (`uv run python -m vultron.metadata.adr.index_gen --write`).
   - **Spec group**: edit the requirement(s) in `specs/*.yaml` — fix the
     statement/rationale, correct or remove a contradicting requirement (per
     `MS-09-001`, remove superseded requirements rather than deprecate), and
     update its `adr:` edge if the source decision changed.
3. Amend dependent `specs/*.yaml` and `notes/*.md` so no dependent still
   asserts the bad premise.
4. Validate: run `format-markdown`, `build-docs` (strict), and the spec linter
   (`uv run spec-lint`).
5. Open a docs-only PR via `create-pr` with the `specs-notes` label.

**Defer (only on real uncertainty):**

1. Create a `type:Concern` issue capturing the wrong premise, the evidence, and
   the open question, via the `manage-github-issue` / `new-item` idiom.
2. Add it to Project #24 with a Schedule tier the user chooses
   (`.agents/skills/shared/add-to-project.sh <N> <tier>`).

**Always — archive a history entry** per resolved landmine via
`archive-history`:

```text
TYPE   = learning
TITLE  = <short decision title> — <verdict>
SOURCE = ADR-NNNN  (or the spec group ID)
BODY   = What the decision claimed, what current understanding shows,
         the agreed correction, and the disposition (docs PR URL or
         Concern issue #N).
```

### ADR archive convention

Retired ADRs live in `docs/adr/archived/` so agents do not meet outdated
decisions in the default `docs/adr/` sweep (`orient-agent` reads
`docs/adr/index.md`; `deepen-context` reads the live `docs/adr/` set only).
When archiving:

- keep the original filename, move it under `docs/adr/archived/`;
- set the file's `status: superseded` with a `superseded_by:` field (or
  `deprecated` with a rationale);
- update `docs/adr/index.md`: remove it from the active list and add it under
  the **Superseded / Archived** section with a forward link to the replacement.

## Notes

- This skill both **detects** and (by default) **fixes** — but detection is
  driven by evidence and fixes are gated on the human verdict. If a candidate
  turns out to be correct (verdict a), the "fix" may be nothing more than a
  status tidy, and that is a valid, valuable outcome — record it so the
  candidate does not resurface every audit.
- Re-runnable: the risk inventory in Phase 1 is cheap. Run this periodically
  (e.g. after a burst of PRs, or when implementation friction spikes) as part
  of the development cycle, the way `requirements-retrospective` is run.
- Related skills: `plan-issue` (the interview idiom), `learn` (promoting
  lessons into specs/notes), `requirements-retrospective` (what the code taught
  us about requirements).
