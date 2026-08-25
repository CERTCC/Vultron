---
name: spec-audit
description: >
  Evaluate the project's YAML spec corpus against IEEE/ISO/IEC 29148:2018
  requirements quality attributes. Produces a Deficient/Marginal/Satisfactory
  finding per requirement, inline elicitation questions for attributes requiring
  human judgment, a corpus-level completeness check, suggested rewrites, and an
  interactive follow-up flow (GitHub issue, auto-fix, grill-me session).
---

# Skill: Spec Audit (IEEE 29148:2018)

## Purpose

Apply the IEEE/ISO/IEC 29148:2018 requirements quality rubric to the project's
spec corpus. Two evaluation tiers:

1. **Per-requirement** — score each requirement against the nine 29148 quality
   attributes and surface findings with before/after rewrites.
2. **Corpus-level** — check whether the spec set as a whole satisfies 29148
   document-level requirements (scope statement, defined terms, stakeholder
   identification, traceability, rationale).

## Invocation

```text
/spec-audit [filter]
```

`filter` is optional. It may be a topic ID (`ARCH`), a requirement ID prefix
(`CM-03`), or a YAML filename stem (`case-management`). When omitted, all
topics are evaluated.

## Rating Scale (29148-native)

| Rating | Meaning |
|---|---|
| **Deficient** | Attribute clearly violated; requirement needs correction before use |
| **Marginal** | Attribute partially satisfied; improvement would meaningfully reduce risk |
| **Satisfactory** | Attribute adequately met; no action required |
| **QUESTION** | Attribute cannot be assessed without human input; elicitation prompt included |

Every Deficient or Marginal finding MUST include both the current text and a
proposed replacement — never just a description of the problem.

## The Nine 29148 Attributes

### Automatable (score Deficient / Marginal / Satisfactory)

**Necessary** — The requirement defines something the system genuinely needs.
Watch for: duplicates of other requirements; gold-plating; requirements that
describe internal implementation detail rather than observable behaviour.

**Unambiguous** — Only one valid interpretation exists.
Watch for: vague adverbs (`appropriately`, `as needed`, `sufficiently`,
`adequately`, `in a timely manner`); `and/or`; `etc.`; pronouns without clear
referents; comparative adjectives without a baseline (`better`, `improved`).

**Verifiable** — A test or inspection can confirm compliance.
Watch for: non-measurable adjectives (`fast`, `reliable`, `easy`, `flexible`,
`robust`, `secure`, `user-friendly`); no testable condition; passive voice
where the actor is unstated and ambiguous.

**Complete** — No information is missing; no placeholders.
Watch for: `TBD`, `TODO`, `TBC`, `[placeholder]`; missing units on quantified
claims; undefined cross-references within the statement.

**Singular** — Exactly one requirement stated.
Watch for: multiple `SHALL`/`MUST` obligations in one statement; `and`
connecting two independent behavioural obligations; compound conditions that
could be split without loss.

**Conforming** — Follows project YAML schema and writing conventions.
Check: required fields present (`id`, `type`, `priority`, `statement`);
`priority` value is a valid keyword (`MUST`/`SHALL`/`SHOULD`/`MAY`/`MUST NOT`);
statement uses the keyword vocabulary consistently.

### Elicitation-Only (always emit QUESTION, never score)

**Feasible** — Can be implemented within current constraints.
Elicitation prompt: "Is this achievable with the current technology stack,
timeline, and team capacity? What assumptions or constraints would make it
infeasible?"

**Correct** — Accurately reflects actual stakeholder needs.
Elicitation prompt: "Has this been validated with the stakeholder(s) it
represents? Could the current wording lead to implementing something different
from what they intended?"

**Appropriate** — Right altitude for a requirements specification.
Elicitation prompt: "Is this stated at the right level of detail — neither so
abstract it provides no implementable guidance, nor so detailed it over-specifies
the implementation?"

---

## Workflow

### Phase 1 — Load Context

1. Run `PYTHONPATH= uv run spec-dump` and capture the JSON output.
   The output has three keys: `topics` (array), `requirements` (array),
   `edges` (array).
2. Read `docs/reference/glossary.md` to extract the defined term table.
3. Read all files under `docs/_acronyms/` to collect defined acronyms.
4. Build a **defined-terms set**: every term in the glossary + every acronym.
5. If a filter argument was provided, restrict `requirements` to those whose
   `topic`, `id`, or source file matches the filter. Log how many requirements
   remain after filtering.

### Phase 2 — Per-Topic Evaluation (Parallel Workflow)

Launch a Workflow with one agent per topic in the filtered requirement set.
Each agent receives:

- The list of requirements for its topic (JSON array)
- The defined-terms set
- The rubric from this skill (the nine attributes above)

Each agent returns a JSON array of findings. Schema per finding:

```json
{
  "req_id": "CM-03-001",
  "topic": "CM",
  "attribute": "unambiguous",
  "rating": "Deficient",
  "issue": "one-sentence description of the violation",
  "current_text": "exact current statement value",
  "proposed_text": "revised statement that resolves the issue"
}
```

For QUESTION findings, omit `proposed_text` and add:

```json
  "rating": "QUESTION",
  "elicitation_prompt": "specific question for the requirement author"
```

For Satisfactory findings with no issues, omit the finding entirely — only
emit findings for Deficient, Marginal, and QUESTION.

**Term check (within each agent):** For each requirement, scan `statement` for
technical terms not in the defined-terms set. If any are found, emit a
`conforming` finding (Marginal) listing the undefined terms and suggesting
additions to the glossary.

### Phase 3 — Corpus-Level Analysis

After the parallel phase completes, run a single synthesis agent that:

1. Receives all per-requirement findings from Phase 2.
2. Evaluates the corpus as a whole against these 29148 document-level checks:

| Check | What to look for |
|---|---|
| **Scope statement** | Is there at least one requirement that defines the purpose/boundary of the system being specified? |
| **Stakeholder identification** | Are the roles or actors who impose requirements named in the spec set? (Check topics like AKM, actor-knowledge-model, CM for role definitions.) |
| **Traceability hooks** | Do requirements reference higher-level needs, design decisions, or parent topics? Are `edges` in the spec-dump graph used to establish traceability? |
| **Rationale coverage** | Do requirements carry rationale/justification fields where expected? Are the "why" fields populated? |
| **Term coverage** | Are all technical terms used in requirement statements covered by the glossary or acronym list? (Aggregate undefined terms from Phase 2 findings.) |
| **Completeness of set** | Are there obvious thematic gaps — domains mentioned in scope but with no requirements? Cross-check against topic list. |

Emit corpus-level findings in the same Deficient/Marginal/Satisfactory/QUESTION
schema, with `req_id: "corpus"` and `topic: "corpus"`.

### Phase 4 — Report

Assemble the full report in this structure:

```markdown
# Spec Audit Report — IEEE/ISO/IEC 29148:2018
**Date:** YYYY-MM-DD HH:MM
**Scope:** all topics | filtered to [X]
**Requirements evaluated:** N across T topics

## Summary

| Rating | Count |
|---|---|
| Deficient | N |
| Marginal | N |
| QUESTION | N |
| Satisfactory (no findings) | N |

## Per-Requirement Findings

### [TOPIC-ID] — Topic Title

#### [REQ-ID] — [Deficient/Marginal] — [attribute]
**Current:** `requirement statement text`
**Issue:** one-sentence explanation
**Proposed:** `revised statement text`

#### [REQ-ID] — QUESTION — [attribute]
**Current:** `requirement statement text`
**Elicitation prompt:** specific question

## Corpus-Level Analysis

### [Check name] — [Deficient/Marginal/Satisfactory]
[explanation and any proposed action]

## Recommended Actions

[Priority-ordered list of the top actionable findings]
```

1. Write the full report to `wip_outputs/spec-audit-YYYYMMDD-HHMMSS.md`.
   Create the `wip_outputs/` directory if it does not exist.
2. Print the **Summary** table and **Recommended Actions** section to the
   terminal. Do not print the full per-requirement findings to the terminal
   (the file is the authoritative record).
3. Tell the user the report path.

### Phase 5 — Post-Report Flow

Work through the following steps in order. **Do not skip any step** — each
offers a distinct action the user may want.

#### Step A — GitHub Issue

Ask the user: "Create a GitHub issue tracking the Deficient findings (N
found)?" If yes:

- Create a GH issue titled `spec-audit: IEEE 29148 quality findings
  YYYY-MM-DD` with a body summarising the Deficient findings by topic,
  linking to the report file.
- Record the issue URL.

#### Step B — Auto-Fix Offer

If there are any Deficient or Marginal findings with `proposed_text`, offer
to apply them:

"I can apply N suggested rewrites to the YAML spec files. Each fix updates
the `statement` field in place. Want to review them?"

If the user agrees, present each fix as a before/after diff and ask for
confirmation before writing. Format:

```text
[REQ-ID] — [attribute]
BEFORE: "current statement"
AFTER:  "proposed statement"
Apply? [yes/no/skip]
```

Apply confirmed fixes by editing the YAML source files. After all fixes are
applied, run `git diff specs/` and show the diff summary. Do **not** commit
automatically — tell the user to review and commit when ready.

#### Step C — Grill-Me Session

If there are any QUESTION findings, offer to work through them interactively:

"There are N elicitation questions from the QUESTION findings. Want to work
through them now? I'll ask them one at a time and record your answers."

If the user agrees, use `ask_user` to ask each elicitation prompt, one at a
time. After all answers are collected:

1. Propose YAML edits that incorporate the answers (same before/after format
   as Step B).
2. Ask which to apply.
3. Apply confirmed edits.

---

## Notes

- Never edit spec YAML files without showing a before/after diff and receiving
  explicit confirmation for each file.
- `wip_outputs/` is the output directory for all generated reports. Do not
  write reports to the project root or `docs/`.
- The spec-dump JSON is the authoritative source; do not read raw `specs/*.yaml`
  files for requirement content.
- Corpus-level findings are advisory — they describe structural gaps in the spec
  set, not violations in individual requirements.
- For the elicitation-only attributes (feasible, correct, appropriate), always
  emit QUESTION regardless of how obvious the answer might seem. These require
  the requirement author's intent and cannot be inferred from the text alone.
