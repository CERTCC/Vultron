# Diátaxis documentation requirements

## Overview

Brief requirements for organizing project documentation according to the
Diátaxis framework.

**Source**: wip_notes/diataxis requirements.md  
**Note**: Conforms to specs/meta-specifications.md

---

## General architecture

- `DF-01-001` (SHOULD) Organize the main documentation into the four Diátaxis
  categories: Tutorials, How-to guides, Reference, and Explanation.
  - Preserve folders where practical: `docs/tutorials`, `docs/howto`,
    `docs/reference`, `docs/topics`.
  - If repository constraints prevent a strict four-way top-level layout,
    document the deviation and map each page to the nearest quadrant.
- `DF-01-002` (MUST) Ensure each documentation page maps to exactly one of
  the four user needs (Learning, Goals, Information, or Understanding).
  - Use front-matter or a classification tag to record the assigned quadrant.
- `DF-01-003` (SHOULD NOT) Combine multiple Diátaxis content types within a
  single page or section; where a combined view is temporarily unavoidable,
  clearly separate the parts and link to full pages of the appropriate type.
- `DF-01-004` (SHOULD) Use hyperlinks to connect related but distinct content
  types instead of embedding cross-type content.
- `DF-01-005` (SHOULD) Write documentation in Markdown and prepare it for the
  MkDocs site defined by `mkdocs.yml`.

## Documentation maintenance

- `DF-02-001` (SHOULD) Build the documentation architecture iteratively from the
  inside-out by improving pages until their Diátaxis category is clear.
- `DF-02-002` (SHOULD) Maintain navigation structure to avoid link breakage when
  moving or renaming files.
  - Use `mkdocs-redirects` and run a link checker after moves.

## Tutorials

- `DF-03-001` (MUST) Author tutorials as practical lessons that help learners
  acquire new skills through guided, hands-on experience.
- `DF-03-002` (MUST) Require that each tutorial is an activity where the learner
  learns by doing.
- `DF-03-003` (MUST) Ensure tutorials produce visible results early and often
  to maintain learner confidence.
- `DF-03-004` (MUST) Use first-person plural ("we") in the tutorial narrative to
  establish tutor/learner rapport.
- `DF-03-005` (MUST NOT) Forbid alternative learning paths within a single
  tutorial's primary flow; present a single prescribed learning path.
- `DF-03-006` (MUST NOT) Exclude in-depth explanations and theoretical discussions
  from the body of tutorials; link to explanatory pages for background.
- `DF-03-007` (MUST) Require every tutorial step to produce a comprehensible
  result that gives immediate feedback.
- `DF-03-008` (MUST) State at the start of each tutorial exactly what the learner
  will have accomplished.
- `DF-03-009` (MUST) Point out specific signs or changes the learner should
  notice during the tutorial.
- `DF-03-010` (SHOULD) provide explicit links to the related Reference and
  Explanation pages (prerequisites, background, deeper rationale). Keep these
  resources out of the tutorial body.

## How-to guides

- `DF-04-001` (MUST) Present how-to guides as goal-oriented directions that
  resolve a specific real-world task or problem.
- `DF-04-002` (MUST) Assume the reader is a competent user with required basic
  skills; surface prerequisites explicitly rather than embedding lessons.
- `DF-04-003` (MUST) Require how-to titles to state exactly what the guide shows
  the user how to do (e.g., start with "How to ...").
- `DF-04-004` (MUST) Use conditional imperatives (e.g., "If you want X, do Y")
  when appropriate.
- `DF-04-005` (MUST NOT) Exclude pedagogical teaching, background history, and
  extended lessons from how-to bodies.
- `DF-04-006` (SHOULD) Prefer concise branching ("if this, then that") to prepare
  users for real-world complexity.
- `DF-04-007` (MUST) Omit unnecessary steps that do not contribute directly to
  the specified goal.
- `DF-04-008` (SHOULD) provide a short "Prerequisites" or "Starting points"
  section (or link to one) that handles different starting states and messy
  real-world setups instead of embedding multiple alternative flows.

## Reference

- `DF-05-001` (MUST) Produce reference material that is neutral, objective, and
  technical in tone.
- `DF-05-002` (MUST) Structure reference content to mirror the physical or
  logical architecture of the system or code being described.
- `DF-05-003` (MUST) Keep reference content dry and free from instruction,
  discussion, or opinion.
- `DF-05-004` (MUST) State facts about behaviors, commands, parameters, versions,
  and limitations.
- `DF-05-005` (MUST) Use consistent, standard patterns and formatting in
  reference documents to make information easy to find.
- `DF-05-006` (MAY) Allow brief code examples in reference material only to
  illustrate usage, not to provide step-by-step instruction.

## Explanation

- `DF-06-001` (MUST) Provide explanatory material that focuses on understanding
  and context for a topic.
- `DF-06-002` (MUST) Address "Why?" questions by discussing history, design
  decisions, or technical constraints.
- `DF-06-003` (MAY) Permit opinion, perspective, and weighing of approaches in
  explanatory documents.
- `DF-06-004` (MUST NOT) Exclude practical instructions and dry technical descriptions
  that belong in Tutorials, How-to, or Reference.
- `DF-06-005` (SHOULD) Prefer titles that can be read as "About X" for explanatory
  topics.
- `DF-06-006` (MUST) Weave connections to related topics to build a web of
  understanding.

## Verification and checks

- `DF-07-001` (SHOULD) Verify the top-level navigation contains the four
  Diátaxis categories where practical; if the site does not expose four
  primary sections, require a documented rationale and a mapping of pages to
  quadrants.
- `DF-07-002` (MUST) Use a classification check (e.g., the "Diátaxis Compass")
  to confirm each page maps to a single category. The Compass MUST be used in
  periodic reviews.
- `DF-07-003` (SHOULD) Confirm tutorials use first-person plural ("we") and do
  not contain alternative paths or optional branches within the primary flow.
- `DF-07-004` (SHOULD) Confirm how-to guide titles start with "How to" and contain
  no lessons in their bodies; check for an explicit "Prerequisites" link when
  multiple starting points exist.
- `DF-07-005` (SHOULD) Validate reference sections by comparing the documentation
  tree to the source tree where appropriate.
- `DF-07-006` (SHOULD) Validate explanatory pages by confirming they remain useful
  when read away from the running product.

## File metadata

- `DF-08-001` (SHOULD) Name Diátaxis specification files using snake_case and
  concise topic descriptors.
- `DF-08-002` (SHOULD) Place cross-reference sources only in the header metadata
  and use inline links for cross-spec references.
