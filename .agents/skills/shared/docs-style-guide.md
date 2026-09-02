# Vultron Documentation Style Guide

Prose rules for hand-written pages under `docs/`. Consumed by `write-docs`
(when authoring) and `lint-docs` (when auditing), and referenced by
`check-docs-sync`.

Normative anchor: `specs/diataxis-requirements.yaml` **DF-09-001** requires
`docs/` prose to follow this file. Rule IDs below (`SG-nn`) are style-guide
rule identifiers, not spec IDs; each cites the spec entry it implements where
one exists.

## Scope

| In scope | Out of scope |
|---|---|
| `docs/topics/`, `docs/howto/`, `docs/tutorials/`, hand-written `docs/reference/` | `docs/adr/` — MADR template, own skill |
| `docs/developer/`, `docs/agents/` — same rules, maintainer audience | `docs/reference/code/` — mkdocstrings-generated |
| | `docs/reference/case_states/` — generated state pages |
| | `notes/`, `specs/` — own conventions (PD-01, MS) |

Generated pages are exempt. Fix the generator, not the output.

---

## 1. Terminology

**SG-01 — `glossary.md` is the arbiter.** `docs/reference/glossary.md` is the
canonical source for domain terms. Where a glossary term exists, use it.
Implements DF-09-002.

**SG-02 — Banned aliases.** The glossary's *Aliases to avoid* column is a
banned-synonym list. Do not write "responsible disclosure" for **CVD**,
"researcher" for **Reporter**, "supplier" for **Vendor**, or "stakeholder" for
**Participant**. Auto-fixable when the replacement is unambiguous.

**SG-03 — Concept names come from the taxonomy.**
`docs/reference/vultron-taxonomy.md` governs the concept names:
`vultron-core`, `vultron-wire`, `vultron-transport`, capability sets, capability
shapes, Vultron roles, Vultron-enabled applications. Write `vultron-core` for
the abstract protocol; write `vultron/core/` only when referring to the Python
package.

**SG-04 — Jargon that is not a domain term.** Field jargon absent from both the
glossary and the taxonomy must be expanded on first use, replaced with plain
language, or registered as a new glossary term. "Avoid jargon" and "use domain
language" are the same rule: the glossary decides which is which.

**SG-05 — Register new terms.** A page that introduces a durable domain term
adds it to `glossary.md` in the same change. Do not coin a term that nothing
checks. For a term that needs discussion rather than a definition, invoke
`ubiquitous-language`.

**SG-06 — One name per concept.** Within a page, and across pages covering the
same concept, use one name throughout. Synonym variation for stylistic relief
is a defect, not a flourish.

---

## 2. Acronyms

**SG-07 — Expand on first use, per page.** Write the expansion followed by the
acronym in parentheses at first use on each page: "Coordinated Vulnerability
Disclosure (CVD)". First use resets per page, because readers arrive from search
and from deep links, not by reading in nav order. Implements DF-09-003.

**SG-08 — Register in the acronyms snippet.** Every acronym used in `docs/`
must appear in `docs/_acronyms/index.md`, which `pymdownx.snippets` appends to
every page to produce hover tooltips. If an acronym is missing, add it as part
of the change. Keep the file in strict alphabetical order, case-insensitive.
Ordering is a maintainability concern only — the `abbr` extension sorts its own
list by length descending before matching, so position in the file does not
affect which abbreviation wins. Auto-fixable.

**SG-08a — One definition per acronym.** `abbr` allows a single expansion per
token site-wide. Where a token is ambiguous, define it in the sense the docs
actually use, and check what a redefinition displaces before making it.

**SG-09 — Do not expand in headings.** Use the short form in headings and the
expansion in the first body paragraph that follows.

---

## 3. Concept order

Writing is a directed acyclic graph of topics: introduce an idea before the
ideas that depend on it.

**SG-10 — Within a page, no forward references.** No section may use a concept
the page has not yet introduced, defined, or linked out for. Ordering sections
so that each depends only on what precedes it is the page's primary structural
obligation.

**SG-11 — Across pages, the edge is a hyperlink.** First use of a glossary or
taxonomy term on a page links to its canonical introduction — the glossary
entry, the taxonomy section, or the explanation page that develops it. The
glossary and the taxonomy are the concept registry; there is no separate
dependency file to maintain.

**SG-12 — Prerequisites are stated, not assumed.** A page that requires prior
reading says so in its opening paragraph and links to it. Tutorials and how-to
guides use an explicit `## Prerequisites` section (DF-04-008).

---

## 4. Sentence and paragraph shape

Simplified technical English in spirit, not ASD-STE100 compliance. The domain
vocabulary stays; the sentence complexity goes.

**SG-13 — One idea per sentence.** A sentence carrying two independent claims
becomes two sentences.

**SG-14 — Sentence length.** Target the corpus band: median 12–15 words, and
few sentences over 28. A sentence past 28 words is usually doing two jobs.

**SG-15 — Active voice with a named subject.** "The CaseActor commits the
entry", not "the entry is committed". Passive voice is acceptable when the
actor is genuinely unknown or irrelevant.

**SG-16 — Paragraphs run two to five sentences.** A paragraph that passes five
sentences is usually two paragraphs, or a list that failed SG-25.

---

## 5. Voice by agency

Voice follows the relationship between writer and reader, not a pronoun table.
Ask who has agency.

| Quadrant | Relationship | Pronouns | Spec |
|---|---|---|---|
| Tutorial | Tutor accompanying a learner | **we** for the shared journey; **you** for the learner's actions and state | DF-03-004, DF-03-011 |
| How-to | Practitioner owns the task | **you** and the imperative; author stays out of the way | DF-04-004 |
| Reference | Description of machinery | Neither. The system is the grammatical subject | DF-05-001, DF-05-007 |
| Explanation | Author discussing a subject | **we** for the author reasoning; **you** for inviting the reader to consider | DF-06-007 |

**SG-17 — Tutorial split.** "In this tutorial, we will run the demo" for the
journey; "You should now have three containers running" for what the learner
has and does. Do not write "We need Docker installed" — the learner needs
Docker, so it is "You need Docker installed".

**SG-18 — How-to imperative.** "Set `AUTH_MODE` to `oidc`. Run the service."
Not "We will configure authentication" and not "Let's set `AUTH_MODE`". The
latter changes the relationship from *here is the procedure you need* to *come
along while I teach you*.

**SG-19 — Reference describes, never instructs.** "A value of `0` disables the
timeout", not "Set `timeout` to `0` to disable it". Crossing from describing the
machinery into instructing the reader is the characteristic reference defect.

**SG-20 — Pronoun drift is a classification signal.** Out-of-quadrant pronouns
in isolation are a wording defect. Pervasive out-of-quadrant pronouns mean the
page is probably the wrong Diátaxis type: a how-to full of "we'll now explore"
is a tutorial or an explanation in the wrong tree, and a tutorial full of "you
should understand that" is drifting into explanation. Report these as
misclassification against DF-01-002; do not paper over them by swapping
pronouns.

---

## 6. Register

Practitioner to practitioner. Explains itself without teaching down; never
performs expertise. These rules are abstracted from the corpus, with
`docs/topics/actor-knowledge-model.md`, `docs/topics/background/what-is-vultron.md`,
and `docs/developer/how-to/run-tests.md` as the closest exemplars.

**SG-21 — Open declaratively.** The first line after the H1 states what the
thing is or does: "The protocol does not…", "Any Participant can…", "This page
explains…". No hooks, no rhetorical questions, no history first.

**SG-22 — Assertion, then consequence.** State the rule flat, then say what
follows from it. Short flat sentences in series carry the emphasis:

> There is no shared memory. There is no back channel. There is no way for one
> actor to look something up in another actor's store.

**SG-23 — Define by exclusion where it sharpens.** Saying what a thing is not
is a corpus habit worth keeping: "It is not a performance preference. It is not
an optimization. It is the architectural invariant on which the protocol is
built." Reference pages for concepts carry an explicit *What is out of scope*.

**SG-24 — No filler, hedging, or enthusiasm.** Banned: `simply`, `just`,
`obviously`, `of course`, `note that`, `it should be noted`, `basically`,
`clearly`, exclamation points, and rhetorical questions outside a
`!!! question` admonition. Confidence comes from flat declaratives, not
adverbs. Auto-fixable by deletion where the sentence survives it.

**SG-25 — Cite instead of asserting.** A normative claim carries its identifier
inline: `(AKM-02-001, AKM-02-002)`, `(ADR-0048, CM-18-003)`. Unattributed
"must" in explanation prose is a finding — either it is normative and has an ID,
or it is advice and should not say "must".

**SG-26 — Emphasis discipline.** Bold marks the term being defined, sparingly.
A blockquote carries the one load-bearing invariant of the page, not general
quotation. Italics for the first mention of a work or for genuine contrast.

**SG-27 — Admonitions in proportion.** The corpus runs `note` ≫ `tip` > `info` >
`example` > `question` > `warning`. Reserve `warning` for real hazards — data
loss, embargo breach, protocol violation. Do not inflate it for emphasis.

---

## 7. Lists and tables

**SG-28 — A bulleted list requires parallel membership.** Items must be
parallel members of one set: roles, fields, options, states. Reasoning,
cause and effect, and comparison go in prose. Bullets that each carry a
sentence of argument are a paragraph that lost its connectives.

**SG-29 — Ordered lists mean ordered.** Numbered lists are for steps executed
in sequence, or for enumerated items referenced by number elsewhere on the
page. Do not number an unordered set.

**SG-30 — Tables beat bullets for pairs.** Term and definition, property and
value, state and meaning: use a table. The corpus does this consistently and
the result is scannable.

**SG-31 — Quadrant exemption.** How-to and tutorial bodies are exempt from the
sparing rule. Their steps are inherently sequences and their prerequisites are
inherently sets.

---

## 8. Diagrams

**SG-32 — A diagram earns its place.** Add one when it shows a relationship
that prose would need three or more cross-references to convey: a state
machine, an inter-actor sequence, containment or composition, a lifecycle. No
page is owed a diagram, and no cap applies — a process-model page legitimately
carries eight.

**SG-33 — Prose must stand alone.** Every diagram has an adjacent sentence
stating what it shows, before or immediately after it. The page must remain
comprehensible when the render fails, in print output, and to a screen reader.

**SG-34 — Mermaid, with a title.** Diagrams use fenced `mermaid` blocks with a
`---` / `title:` header, which supplies the rendered caption.

**SG-35 — Sanctioned diagram types.** `stateDiagram-v2`, `sequenceDiagram`,
`flowchart`, `classDiagram`, `erDiagram`. Legacy `graph` is `flowchart` and is
auto-fixable. Anything outside this list needs a reason.

**SG-36 — Prefer Mermaid to ASCII art.** New structural diagrams use Mermaid.
Existing ASCII diagrams in `text` fences are grandfathered and reported as
low-priority findings; do not auto-convert them.

---

## 9. Mechanics

**SG-37 — American spelling.** `organize`, `behavior`, `normalize`,
`serialize`. Auto-fixable in prose. Existing filenames and ADR titles are
grandfathered — do not rename `adr/0062-normalise-wire-to-core-*`.

**SG-38 — One sentence per line.** On pages that `write-docs` creates or
rewrites, each sentence starts on its own line with no mid-sentence hard wrap.
Prose diffs then show which sentence changed. Pages not touched by a change are
left as they are; the corpus is mixed by design, and no line-length rule
applies.

**SG-39 — Headings.** One H1 matching the nav label in substance. H2 and below
in sentence case. Sections separated by `---` where the page has more than
three of them, following the corpus.

**SG-40 — No frontmatter requirement.** YAML frontmatter is optional on `docs/`
pages. Where present, keep `title` and `description` accurate. Do not add
frontmatter to a page that lacks it just to carry metadata nothing reads.

**SG-41 — Page furniture.** H1, then a two-to-four sentence orientation
paragraph saying what the page covers and who it is for, then the body. Where a
page closes with a recap, use a `## Summary` table of principle and statement,
a `## Further reading` link list with em-dash annotations, or both.

**SG-42 — No page length rule.** Pages are split by quadrant and topic, never
by length. A long reference page is correct; a three-paragraph explanation page
is correct.

---

## 10. Rule index

`Fix` marks rules `lint-docs` applies automatically. The rest are reported with
a recommendation.

| Rule | Subject | Fix |
|---|---|:---:|
| SG-01, SG-03 | Glossary and taxonomy are canonical | |
| SG-02 | Banned aliases | yes |
| SG-04, SG-05, SG-06 | Jargon, term registration, one name per concept | |
| SG-07, SG-09 | Acronym expansion on first use | yes |
| SG-08, SG-08a | Acronym registered in `_acronyms/index.md`; one definition per token | yes |
| SG-10, SG-12 | Concept order, stated prerequisites | |
| SG-11 | First use links to canonical introduction | |
| SG-13, SG-14, SG-15, SG-16 | Sentence and paragraph shape | |
| SG-17, SG-18, SG-19 | Voice by quadrant — isolated cases | yes |
| SG-20 | Pervasive drift as misclassification | |
| SG-21, SG-22, SG-23 | Opening, assertion order, exclusion | |
| SG-24 | Filler and hedging | yes |
| SG-25, SG-26, SG-27 | Citation, emphasis, admonitions | |
| SG-28, SG-29, SG-30, SG-31 | Lists and tables | |
| SG-32, SG-33 | Diagram warrant and prose-standalone | |
| SG-34, SG-35 | Mermaid title, `graph` → `flowchart` | yes |
| SG-36 | ASCII art grandfathered | |
| SG-37 | American spelling | yes |
| SG-38, SG-39, SG-40, SG-41, SG-42 | Line breaks, headings, furniture | |

---

## Escalation

Both skills fix mechanical findings silently and escalate judgment calls with a
recommendation, never as an open question. State the finding, state what you
would do about it and why, and ask for confirmation. This applies to quadrant
misclassification (SG-20), cross-quadrant page splits (DF-01-003), and nav
placement alike.
