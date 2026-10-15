---
status: proposed
date: 2026-10-14
created: 2026-10-14
updated: 2026-10-14
revision: 1
deciders: Allen D. Householder
consulted: >-
  Claude Opus 5.5; ADR-0102; notes/site-information-architecture.md; a
  proof-of-concept build of the proposed navigation (branch
  spike/site-ia-floors-poc)
informed: Vultron contributors
stakeholder_type: [project-contributor]
partially_supersedes:
  - 0102-docs-stakeholder-types-and-invisible-prerequisite-levels.md
---

# Organize the Site's Top Level by Reader, Not by Diátaxis Type

## Context and Problem Statement

ADR-0102 kept the four Diátaxis sections (Tutorials, How-to, Explanation, Reference) as the site's top level.
It added a Start Here entry layer above them and per-page `stakeholder_type` and `level` declarations.
It rejected a reader-goal top level only because nothing was known about readers and that option was the least reversible.

With ADR-0102 in place, the top level still fails readers in ways the entry layer cannot fix:

- There is no single answer to "where is the protocol?".
  The Protocol Specification, Messages, the Conformance Matrix, the Quick Reference, Formal Protocol and the notation page all present themselves as the protocol, spread across sections at the same weight.
- The protocol and CERT/CC's Python reference implementation share sections.
  The Trigger API sits beside the message reference, and demos are scattered across three sections, so a tracker developer cannot tell what binds them from what describes one codebase.
- Explanation is a single section of about 75 entries, and Reference is a junk drawer.
- Nine tabs are named for the type of page rather than for anything a reader came to do.
  A reader who recognizes their situation on a Start Here page is then sent into sections that do not mention it.

Should the top level stay organized by page type, with audience routing above it, or be reorganized by reader, with page type kept as a property of each page?

## Decision Drivers

- A tracker or platform developer must reach the normative protocol in one click from the home page, and must never mistake reference-implementation material for it.
- The internal audience model (ADR-0102's stakeholder types and invisible levels) stays internal: no type name and no level appears on the site.
- Diátaxis is a sound discipline for writing a page; it was never evidence about how readers navigate.
- A restructure must be reversible and testable before it costs URLs and inbound links.
- No human newcomer is available to test the site, so validation has to work without one.

## Considered Options

- **A — Floors by reader; page type as a per-page label; navigation first, files later behind a usability test.**
- **B — Keep the Diátaxis top level and strengthen the entry layer** (ADR-0102 as it stands, with better Start Here pages).
- **C — The generic protocol-site template**: Learn, Build, Run, Governance, Resources.
- **D — Floors by reader, with directories moved in the same change as the navigation.**

## Decision Outcome

Chosen option: **A**.
It is the only option that gives the protocol one home and separates it from the reference implementation without first breaking every URL on a guess.

### The top level is organized by reader

The home page is the front desk.
It says what kind of thing Vultron is and sends each reader to the part of the site built for them.
It links directly to the Protocol Specification.

The navigation tabs are:

| Tab | Addressed to |
|---|---|
| Home | everyone: the front desk |
| How Vultron Works | everyone: the shared concepts every other tab assumes |
| Coordinate Cases | people who coordinate vulnerability cases |
| Implement the Protocol | people building or maintaining a tracker or platform that must speak the protocol |
| Reference Implementation | people running, adapting or contributing to CERT/CC's Python implementation |
| Research | people studying CVD as a process |
| Project | everyone: versioning, what's new, open questions, how to propose a change, governance-like material |

Each reader tab opens on its existing situation-titled page under `docs/start/`.
The separate Start Here tab is retired, because every tab is now an entry.
Tab names describe an activity, never an audience label, so DF-11-009 holds unchanged.

### The protocol and the reference implementation never share a section

A page that describes CERT/CC's codebase rather than what every implementation must do goes under Reference Implementation, however close its subject is to the protocol.
The Trigger API and the demos are reference-implementation material.

### The Protocol Specification is the protocol's one home

Under Implement the Protocol, the Protocol Specification is canonical.
Messages, the Conformance Matrix, the Quick Reference and Formal Protocol are labelled as companions that defer to it.

### Diátaxis becomes a property of a page

Every reader-facing page declares one `page_type` in frontmatter: `tutorial`, `how-to`, `explanation` or `reference`.
Routing pages and the home page are exempt, because they give directions rather than content.
The site renders the declared type as a labelled badge.
The badge is a reusable style, so authors can also write it by hand beside a link.
Diátaxis keeps its authoring rules (DF-01-002 through DF-01-004); it stops deciding where a page sits.

The key is `page_type`, not `content_type`, which is easily mistaken for a MIME type.

### Navigation first, files later

The navigation changes first and the directories stay where they are, so no URL breaks.
Moving the files to match the new top level waits for a usability test that compares the current and proposed navigation and shows the new one is better.

### What ADR-0102 keeps

Everything in ADR-0102 except its decision to keep the four Diátaxis sections as the top level stands.
That includes stakeholder types, invisible levels, the working-record door, generated landing pages and the coverage matrix.

### Consequences

- Good, because a platform developer reaches the normative protocol from the home page in one click, and every page a section holds binds them or explains what binds them.
- Good, because a reader arriving at a tab recognizes it as theirs without having to classify themselves by an internal label.
- Good, because page type remains checkable and visible, and its badge tells a reader arriving from search what kind of page they landed on.
- Good, because navigation-first keeps the change reversible: a wrong tab costs a `mkdocs.yml` edit, not a set of redirects.
- Bad, because for a while the directory names (`tutorials/`, `topics/`, `howto/`, `reference/`) no longer match where pages appear in the navigation, which misleads contributors until the files move.
- Bad, because declaring `page_type` on several hundred pages is a one-time pass, and some pages will turn out to mix types.
- Bad, because the usability test uses agents briefed as newcomers, not people. It catches navigation that cannot work; it cannot prove navigation a human finds natural.

## Validation

Mechanically: `docs-frontmatter` validates `page_type` on every reader-facing page and rejects it on routing pages and fragments.
The existing checks for generated landing pages and the coverage matrix keep running against the new navigation.

The file move is gated by an agent-run usability test in two stages:

1. **Tree test.** Agents get only the navigation labels, current and proposed, and say where they would look for each task.
2. **Walkthrough.** Agents get the built site as HTML only, with no repository and no site search.
   They have a click budget and are allowed to give up.

The test uses about five personas, each told explicitly what they do not know.
Its tasks come from the user stories, the FAQ and real questions from the maintainer, and are fixed before anyone sees the proposed navigation.
The proposed navigation passes when it beats the current one on task success and no task stalls at the front desk.

A cold read by a human newcomer remains a goal, as ADR-0102 says, but it does not gate this change.

## Pros and Cons of the Options

### A — Floors by reader; page type as a label; navigation first

- Good, because it fixes the protocol-versus-implementation mix structurally rather than by labelling.
- Good, because it keeps Diátaxis where it works, on the page.
- Neutral, because it is the reader-goal reorganization ADR-0102 rejected, made reversible and given a test that ADR-0102 lacked.
- Bad, because directory names and navigation disagree until the gated move.

### B — Keep the Diátaxis top level and strengthen the entry layer

- Good, because it changes nothing structural.
- Bad, because a good Start Here page still hands the reader to sections that mix the protocol with the reference implementation.
- Bad, because the protocol keeps six candidate homes.

### C — The generic protocol-site template

- Good, because it is familiar from other protocol sites.
- Bad, because its "Run" floor assumes node operators and its "Governance" floor assumes a proposal process with voting, and Vultron has neither.
- Bad, because it gives CVD practitioners, Vultron's largest audience, no home of their own.

### D — Floors by reader, with directories moved at once

- Good, because directory names and navigation agree from day one.
- Bad, because it breaks every inbound link on an untested guess, which is exactly the irreversibility ADR-0102 refused.

## More Information

The internal model behind the tabs is in `notes/site-information-architecture.md` § "The front desk and the floors".
It maps each tab to a stakeholder type and keeps the metaphor off the site.

The visual components used to implement this (the page-type badge, card grids, a two-column grid, content tabs, code annotations, buttons and the home-page hero) are implementation detail and are recorded in the docs style guide, not here.

The version selector is deferred until the first published wire version (#3653).

**Generated spec requirements (pending):** `diataxis-requirements.yaml` DF-01-001 is to be reworded from "organize the site into the four categories" to "declare one page type per page".
A new DF-11 item is to require `page_type`, and another to forbid a navigation section that holds both protocol and reference-implementation pages.
