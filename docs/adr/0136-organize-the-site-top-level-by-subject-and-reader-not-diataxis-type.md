---
status: proposed
date: 2026-10-14
created: 2026-10-14
updated: 2026-10-15
revision: 2
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0102; notes/site-information-architecture.md; a
  proof-of-concept build of the proposed navigation (branch
  spike/site-ia-floors-poc); the PR #4681 review
informed: Vultron contributors
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0102-docs-stakeholder-types-and-invisible-prerequisite-levels.md
---

# Organize the Site's Top Level by Subject and Reader, Not Diátaxis Type

## Context and Problem Statement

ADR-0102 kept the four Diátaxis sections (Tutorials, How-to, Explanation, Reference) as the site's top level.
It added a Start Here entry layer above them and per-page `stakeholder_type` and `level` declarations.
It rejected a reader-goal top level only because nothing was known about readers and that option was the least reversible.

With ADR-0102 in place, the top level still fails readers in ways the entry layer cannot fix:

- There is no single answer to "where is the protocol?".
  The Protocol Specification, the requirement tiers, Messages, the Conformance Matrix, the Quick Reference, Formal Protocol and the notation page all present themselves as the protocol, spread across sections at the same weight.
- The protocol and CERT/CC's Python reference implementation share sections.
  The Trigger API sits beside the message reference, the Protocol requirement tier is filed with the implementation's own requirements, and demos are scattered across three sections, so a tracker developer cannot tell what binds them from what describes one codebase.
- Explanation is a single section of about 75 entries, and Reference is a junk drawer.
- Nine tabs are named for the type of page rather than for anything a reader came to do.
  A reader who recognizes their situation on a Start Here page is then sent into sections that do not mention it.

Should the top level stay organized by page type, with audience routing above it, or be reorganized by subject and reader, with page type kept as a property of each page?

## Decision Drivers

- A tracker or platform developer must reach the normative protocol in one click from the home page, and must never mistake reference-implementation material for it.
- The internal audience model (ADR-0102's stakeholder types and invisible levels) stays internal: no type name and no level appears on the site.
- Diátaxis governs how a page is written.
  This decision returns it to the page rather than discarding it; it was never evidence about how readers navigate.
- A restructure must be reversible and testable before it reaches readers or costs URLs and inbound links.
- No human newcomer is available to test the site, so validation has to work without one.

## Considered Options

- **A — Tabs by subject and reader; page type as a per-page label; the new navigation gated on a usability test.**
- **B — Keep the Diátaxis top level and strengthen the entry layer** (ADR-0102 as it stands, with better Start Here pages).
- **C — The generic protocol-site template**: Learn, Build, Run, Governance, Resources.

For where the files live under option A:

- **A1 — Keep files where they are.**
- **A2 — Move the directories to match the tabs**, in the same change as the navigation or after it.

## Decision Outcome

Chosen option: **A**, with **A1**.
It is the only option that gives the protocol one home and separates it from the reference implementation without first breaking every URL on a guess.

### The top level is organized by subject and reader

The home page is the front desk.
It says what kind of thing Vultron is and sends each reader to the part of the site built for them.
It links directly to the Protocol Specification and to one cross-tab lookup page (see "Returning readers").

The navigation tabs are:

| Tab | Addressed to |
|---|---|
| Home | everyone: the front desk |
| How Vultron Works | everyone: the shared concepts every other tab assumes |
| Coordinate Cases | people who coordinate vulnerability cases |
| Implement the Protocol | people building or maintaining a tracker or platform that must speak the protocol |
| Reference Implementation | people running, adapting or contributing to CERT/CC's Python implementation |
| Research | people studying CVD as a process |
| Project | everyone: versioning, what's new, open questions about the project, how to propose a change |

That is seven tabs.
The CERT/CC link stays as the parent-site link, outside the tab set, because the Vultron site is a subsite of `certcc.github.io`.

Every tab opens on a landing page.
Each reader tab opens on its existing situation-titled page under `docs/start/`, and How Vultron Works gets a landing page of its own.
The separate Start Here tab is retired, because every tab is now an entry.
Tab names describe a subject or an activity, never an audience label, so DF-11-009 holds unchanged.
A tab is not tied one-to-one to a stakeholder type: a later `stakeholder_type` split adds a thread (below), not a tab, which keeps the types invisible as ADR-0102 requires.

### Placement follows an ordered rule

Each page goes to the first tab whose test it passes:

1. It binds every implementation, or explains or teaches what does → **Implement the Protocol**.
2. It is about how *this* implementation is built or run → **Reference Implementation**.
3. Otherwise, the tab of its declared `stakeholder_type`.
   A page declared `ALL`, or one several tabs depend on → **How Vultron Works**.
   Project process → **Project**.

So the protocol and the reference implementation never share a section.
The Trigger API and the demos are reference-implementation material, however close their subject is to the protocol.

A tutorial is placed by what it teaches.
One that teaches protocol behavior goes on Implement the Protocol, with a short note that it uses the reference implementation as a test bench.
One about running, configuring or extending the code stays on Reference Implementation.

### Inside a tab, groups are named by topic

A tab's groups are named for their subject, never for a Diátaxis type: "Run the Demos", not "Tutorials".
A large group goes behind a routing page (DF-11-006) rather than nesting deeper in the navigation.

### Each reader tab starts a thread

Each reader tab's landing page starts a **thread**: an ordered reading path that may cross tabs.
How Vultron Works has a shared thread.
The navigation is the structure; the threads give the route.
ADR-0102's level rule already guarantees that an order exists for each audience.
How a thread is presented is left open (#4750).

### The normative protocol has one home

The normative protocol is the Protocol Specification plus the **Protocol** and **Foundation** requirement tiers in `specs/*.yaml`.
All of it sits on Implement the Protocol, never on Reference Implementation.
The YAML is the source of truth: the specification presents those requirements and must not diverge from them, and any divergence is a bug.

On Implement the Protocol the two tiers are labeled **Protocol Requirements**.
On Reference Implementation the Architecture, Project and Process tiers are labeled **Implementation Requirements**: requirements for *this* implementation.
The project specifies how it builds its own implementation, not how others must build theirs.

Messages, the Conformance Matrix, the Quick Reference and Formal Protocol are companions.
They help a reader use the normative set and never add to it.
Pages on Implement the Protocol outside the normative set carry the existing `not_normative.md` banner, as `reference/conventions.md` describes.
Normative status is a separate axis from page type.

### Diátaxis becomes a property of a page

Every reader-facing page declares one `page_type` in frontmatter: `tutorial`, `how-to`, `explanation`, `reference` or `routing`.
The key is required, so a missing key is a fault, for the same reason `contents:` is required on landing pages.
`routing` is validated but not rendered; the other four render as a labeled badge.
`page_type` is independent of `contents:`: an index that mostly explains is `explanation`.
Working-record pages declare no `page_type`, because DF-11-003 already marks them.

A page that mixes types is split, or its parts are clearly separated, as DF-01-003 requires.
The Protocol Specification declares a `page_type` on each of its pages, not one for the whole specification.

Badges come only from frontmatter; a hand-written badge beside a link is not part of this decision.
Diátaxis keeps its authoring rules (DF-01-002 through DF-01-004); it stops deciding where a page sits.
The key is `page_type`, not `content_type`, which is easily mistaken for a MIME type.

### Returning readers

ADR-0102 objected that a reader-goal top level costs returning readers who know what they want.
One cross-tab lookup page answers that.
It lists the reference pages a returning reader looks up (the specification, the requirement tiers, messages, the glossary, the conformance matrix, the quick reference), is linked from the home page, and can be generated from `page_type: reference` (#4751).

### The type signal lands first, and the navigation is gated

The order is:

1. The `page_type` schema, its validator and its badge land, together with the DF-01-001 rewording.
2. The agent usability test runs against a build that shows the badges.
3. The navigation changes only after the test passes.

So the site never goes without a type signal and never contradicts its own requirements.

The proposed navigation stays on a branch or a preview build until the test passes against `main`'s navigation.
A failing navigation is revised and retested, and `main` keeps its current top level in the meantime.

### Files stay where they are

The directories stay where they are (option A1), so no URL breaks.
A page's directory is not evidence of its tab.
Moving files is reconsidered only if specific costs show up: contributors repeatedly misplacing pages, or real friction from the routing check's directory assumption (a routing page must link the reader pages in its own directory, `landing_pages.py`).
That assumption is a known coupling between directories and navigation.

The old section index pages (`tutorials/`, `topics/`, `reference/`, `howto/`, `start/index.md`) keep their URLs but describe sections that no longer exist.
Each is retargeted as a routing page or a redirect stub.

### What ADR-0102 keeps

Everything in ADR-0102 except its decision to keep the four Diátaxis sections as the top level stands.
That includes stakeholder types, invisible levels, the working-record door, generated landing pages and the coverage matrix.

### Consequences

- Good, because a platform developer reaches the normative protocol from the home page in one click, and every page on that tab binds them or explains what binds them.
- Good, because a reader arriving at a tab recognizes it as theirs without having to classify themselves by an internal label.
- Good, because page type remains checkable and visible, and its badge tells a reader arriving from search what kind of page they landed on.
- Good, because the gate keeps the change reversible: a navigation that fails the test never reaches `main`, and a wrong tab later costs a `mkdocs.yml` edit, not a set of redirects.
- Bad, because the directory names (`tutorials/`, `topics/`, `howto/`, `reference/`) no longer match where pages appear in the navigation, which can mislead contributors for as long as the files stay put.
- Bad, because declaring `page_type` on several hundred pages is a one-time pass, and some pages will turn out to mix types.
- Bad, because the usability test uses agents briefed as newcomers, not people.
  It catches navigation that cannot work; it cannot prove navigation a human finds natural.

## Validation

Mechanically: `docs-frontmatter` validates `page_type` on every reader-facing page, requires it there, and rejects it on fragments and working-record pages.
The existing checks for generated landing pages and the coverage matrix keep running against the new navigation.

The navigation change is gated by an agent-run usability test:

- The baseline is `main`'s navigation.
- The proposed navigation passes when it is no worse than the baseline on task success and no task stalls at the home page.
- Personas and tasks are committed before the proposed navigation is evaluated.
- Each pairing of persona, task and navigation is repeated enough times to absorb run-to-run variance.
- The evaluating agent is independent of the design: a different model, or a fresh context without access to the proof of concept.
- Each persona has at least one "follow your thread" task.

How to run the test (its two stages, briefing, task sources, rerun policy and cost controls) is in `notes/site-information-architecture.md` § "Validation".

A cold read by a human newcomer remains a goal, as ADR-0102 says, but it does not gate this change.

## Pros and Cons of the Options

### A — Tabs by subject and reader; page type as a label; gated navigation

- Good, because it fixes the protocol-versus-implementation mix structurally rather than by labeling.
- Good, because it keeps Diátaxis where it works, on the page.
- Neutral, because it is the reader-goal reorganization ADR-0102 rejected, made reversible and given a test that ADR-0102 lacked.
- Bad, because directory names and navigation disagree.

### B — Keep the Diátaxis top level and strengthen the entry layer

- Good, because it changes nothing structural.
- Bad, because a good Start Here page still hands the reader to sections that mix the protocol with the reference implementation.
- Bad, because the protocol keeps several candidate homes.

### C — The generic protocol-site template

- Good, because it is familiar from other protocol sites.
- Bad, because its "Run" floor assumes node operators and its "Governance" floor assumes a proposal process with voting, and Vultron has neither.
- Bad, because it gives CVD practitioners no home of their own.

### A1 — Keep files where they are

- Good, because no URL or inbound link breaks.
- Good, because a wrong placement is fixed in `mkdocs.yml` alone.
- Bad, because directory names stop describing where a page appears.

### A2 — Move the directories to match the tabs

- Good, because directory names and navigation agree.
- Bad, because it breaks inbound links, and doing it with the navigation change breaks them on an untested guess, which is exactly the irreversibility ADR-0102 refused.

## More Information

The internal model behind the tabs is in `notes/site-information-architecture.md` § "The front desk and the floors".
It maps each tab to its primary stakeholder type, records the placement of edge pages and tutorials, and keeps the metaphor off the site.

The visual components used to implement this (the page-type badge, card grids, a two-column grid, content tabs, code annotations, buttons and the home-page hero) are implementation detail and are recorded in the docs style guide, not here.

The version selector is deferred until the first published wire version (#3653).

**Spec changes (pending, #4683):** `diataxis-requirements.yaml` DF-01-001 is to be reworded from "organize the site into the four categories" to "declare one page type per page".
A new DF-11 item is to require `page_type`, and another to forbid a navigation section that holds both protocol and reference-implementation pages.

**Follow-up work:** rendering the YAML Protocol and Foundation requirements into the specification pages so the two cannot drift apart (#4749); the thread mechanism (#4750); the generated lookup page (#4751); an optional `normative:` frontmatter key, if the separation rule is ever machine-checked (#4752).
