# Diátaxis documentation requirements

## Overview
Brief requirements for organizing project documentation according to the
Diátaxis framework.

**Source**: wip_notes/diataxis requirements.md  
**Note**: Conforms to specs/meta-specifications.md

---

## General architecture (SHOULD)
- `DIAT-GEN_01-001` Organize the main documentation into the four Diátaxis
  categories: Tutorials, How-to guides, Reference, and Explanation.
  - Preserve folders where practical: `docs/tutorials`, `docs/howto`,
    `docs/reference`, `docs/topics`.
  - If repository constraints prevent a strict four-way top-level layout,
    document the deviation and map each page to the nearest quadrant.
- `DIAT-GEN_01-002` Ensure each documentation page maps to exactly one of
  the four user needs (Learning, Goals, Information, or Understanding).
  - Use front-matter or a classification tag to record the assigned quadrant.
- `DIAT-GEN_01-003` Avoid combining multiple Diátaxis content types within a
  single page or section; where a combined view is temporarily unavoidable,
  clearly separate the parts and link to full pages of the appropriate type.
- `DIAT-GEN_01-004` Use hyperlinks to connect related but distinct content
  types instead of embedding cross-type content.
- `DIAT-GEN_01-005` Write documentation in Markdown and prepare it for the
  MkDocs site defined by `mkdocs.yml`.

## Documentation maintenance (SHOULD)
- `DIAT-GEN_02-001` Build the documentation architecture iteratively from the
  inside-out by improving pages until their Diátaxis category is clear.
- `DIAT-GEN_02-002` Maintain navigation structure to avoid link breakage when
  moving or renaming files.
  - Use `mkdocs-redirects` and run a link checker after moves.

## Tutorials (MUST)
- `DIAT-TUT_03-001` Author tutorials as practical lessons that help learners
  acquire new skills through guided, hands-on experience.
- `DIAT-TUT_03-002` Require that each tutorial is an activity where the learner
  learns by doing.
- `DIAT-TUT_03-003` Ensure tutorials produce visible results early and often
  to maintain learner confidence.
- `DIAT-TUT_03-004` Use first-person plural ("we") in the tutorial narrative to
  establish tutor/learner rapport.
- `DIAT-TUT_03-005` Forbid alternative learning paths within a single
  tutorial's primary flow; present a single prescribed learning path.
- `DIAT-TUT_03-006` Exclude in-depth explanations and theoretical discussions
  from the body of tutorials; link to explanatory pages for background.
- `DIAT-TUT_03-007` Require every tutorial step to produce a comprehensible
  result that gives immediate feedback.
- `DIAT-TUT_03-008` State at the start of each tutorial exactly what the learner
  will have accomplished.
- `DIAT-TUT_03-009` Point out specific signs or changes the learner should
  notice during the tutorial.
- `DIAT-TUT_03-010` SHOULD provide explicit links to the related Reference and
  Explanation pages (prerequisites, background, deeper rationale). Keep these
  resources out of the tutorial body.

## How-to guides (MUST)
- `DIAT-HT_04-001` Present how-to guides as goal-oriented directions that
  resolve a specific real-world task or problem.
- `DIAT-HT_04-002` Assume the reader is a competent user with required basic
  skills; surface prerequisites explicitly rather than embedding lessons.
- `DIAT-HT_04-003` Require how-to titles to state exactly what the guide shows
  the user how to do (e.g., start with "How to ...").
- `DIAT-HT_04-004` Use conditional imperatives (e.g., "If you want X, do Y")
  when appropriate.
- `DIAT-HT_04-005` Exclude pedagogical teaching, background history, and
  extended lessons from how-to bodies.
- `DIAT-HT_04-006` Prefer concise branching ("if this, then that") to prepare
  users for real-world complexity.
- `DIAT-HT_04-007` Omit unnecessary steps that do not contribute directly to
  the specified goal.
- `DIAT-HT_04-008` SHOULD provide a short "Prerequisites" or "Starting points"
  section (or link to one) that handles different starting states and messy
  real-world setups instead of embedding multiple alternative flows.

## Reference (MUST)
- `DIAT-REF_05-001` Produce reference material that is neutral, objective, and
  technical in tone.
- `DIAT-REF_05-002` Structure reference content to mirror the physical or
  logical architecture of the system or code being described.
- `DIAT-REF_05-003` Keep reference content dry and free from instruction,
  discussion, or opinion.
- `DIAT-REF_05-004` State facts about behaviors, commands, parameters, versions,
  and limitations.
- `DIAT-REF_05-005` Use consistent, standard patterns and formatting in
  reference documents to make information easy to find.
- `DIAT-REF_05-006` Allow brief code examples in reference material only to
  illustrate usage, not to provide step-by-step instruction.

## Explanation (MUST)
- `DIAT-EXP_06-001` Provide explanatory material that focuses on understanding
  and context for a topic.
- `DIAT-EXP_06-002` Address "Why?" questions by discussing history, design
  decisions, or technical constraints.
- `DIAT-EXP_06-003` Permit opinion, perspective, and weighing of approaches in
  explanatory documents.
- `DIAT-EXP_06-004` Exclude practical instructions and dry technical descriptions
  that belong in Tutorials, How-to, or Reference.
- `DIAT-EXP_06-005` Prefer titles that can be read as "About X" for explanatory
  topics.
- `DIAT-EXP_06-006` Weave connections to related topics to build a web of
  understanding.

## Verification and checks (SHOULD)
- `DIAT-VER_07-001` Verify the top-level navigation contains the four
  Diátaxis categories where practical; if the site does not expose four
  primary sections, require a documented rationale and a mapping of pages to
  quadrants.
- `DIAT-VER_07-002` Use a classification check (e.g., the "Diátaxis Compass")
  to confirm each page maps to a single category. The Compass MUST be used in
  periodic reviews.
- `DIAT-VER_07-003` Confirm tutorials use first-person plural ("we") and do
  not contain alternative paths or optional branches within the primary flow.
- `DIAT-VER_07-004` Confirm how-to guide titles start with "How to" and contain
  no lessons in their bodies; check for an explicit "Prerequisites" link when
  multiple starting points exist.
- `DIAT-VER_07-005` Validate reference sections by comparing the documentation
  tree to the source tree where appropriate.
- `DIAT-VER_07-006` Validate explanatory pages by confirming they remain useful
  when read away from the running product.

## File metadata (SHOULD)
- `DIAT-META_08-001` Name Diátaxis specification files using snake_case and
  concise topic descriptors.
- `DIAT-META_08-002` Place cross-reference sources only in the header metadata
  and use inline links for cross-spec references.
