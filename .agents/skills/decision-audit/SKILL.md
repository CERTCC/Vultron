---
name: decision-audit
description: >
  Find and adjudicate stale or incorrect architectural decisions before they
  blow up in an implementation PR. Builds a risk-ranked inventory of ADRs (and
  high-fan-in spec groups) that agents treat as solid fact but may encode a
  wrong or outdated premise, re-derives each suspect adversarially from current
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

Load `REFERENCE.md` and run the scoring commands there. For every ADR (and,
optionally, high-fan-in spec groups) compute a **landmine risk score** from:

- **Blast radius** — how many specs/notes depend on the decision
  (`grep -rioE 'ADR-00[0-9]{2}' specs/ notes/` reference count). A wrong
  decision with many dependents is a bigger landmine than an isolated one.
- **Confidence deficit** — signals that the decision is not as settled as its
  presentation implies:
  - `status:` frontmatter blank, `proposed`, or anything other than `accepted`.
  - **Frontmatter-vs-prose contradiction**: `status: accepted` while the prose
    carries provisional markers (`formed in sand`, `not concrete`,
    `provisional`, `forward-looking`, `will converge`, `SHOULD refine`,
    `status will advance`).
  - **Index-vs-frontmatter drift**: the section the ADR sits under in
    `docs/adr/index.md` disagrees with its own `status:`.
  - **Amended-after-acceptance**: `git log --follow` shows edits after the
    accept date (a taxonomy or design that already needed correction once).
  - **Layer-boundary friction**: prose that describes a construct without
    pinning it to its actual layer (e.g. "shape base class" language when the
    classes live in `vultron/demo/fuzzer/`, against `BT-16-001`).
  - **Correction history**: `plan/history/*/learning/` or
    `plan/incoming/learnings/` entries that name the decision as wrong/stale.

Present the ranked list to the user via `ask_user`: highest-risk first, each
row showing the score inputs (blast radius + which deficit signals fired). Let
the user pick which candidate(s) to work, with a "triage the whole list in
order" option. **Nothing is written in this phase.**

### Phase 2 — Deepen Context (per selected candidate)

Invoke `deepen-context` with domain hints derived from the candidate's title.
Read the full ADR, every spec whose `rationale` (or ADR edge) cites it, the
dependent notes files, and representative implementing code. The point is to
know what the decision *actually* claims and what the code *actually* does.

### Phase 3 — Adversarial Re-Derivation (the core check)

Do **not** ask "is this still true?" in the abstract — that invites
confirmation. Instead, re-derive the decision from *current* understanding:
**given what we now know, would we make this same choice?**

Spawn an `Explore` or `Plan` agent with the counter-case prompt in
`REFERENCE.md`: its job is to argue why the decision may be **wrong or stale**
given today's code and specs, and to collect concrete contradiction evidence:

- spec text that conflicts with the code or with another spec,
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
2. Edit `docs/adr/NNNN-*.md`: reconcile `status:` per the decision tree in
   `notes/specs-vs-adrs.md`, correct the prose, and — if the decision is
   retired — set `status: superseded by <link>` and move the file to
   `docs/adr/archived/` (see the ADR archive convention below).
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
- set the file's `status: superseded by <link-to-replacement>` (or
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
