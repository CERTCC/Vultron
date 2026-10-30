---
description: >
  Every page you look things up in, from every tab in one list: the
  specification, the requirements, the messages, the glossary, and the tables.
stakeholder_type: ALL
level: 200
page_type: routing
subject: neutral
---

# Look Something Up

This page is for a reader who has been here before and wants one page in particular.
It lists the pages you look things up in, from every tab of the site, in the order the tabs are in.
Each entry links the page and gives its own summary.
A set of related pages, such as the parts of the Protocol Specification, is one entry that links the page that opens the set.

If this is your first visit, start from the [home page](index.md) instead: it sends you to the reading path for what you came to do.

<!-- BEGIN GENERATED LOOKUP LISTING — do not edit; change the mkdocs.yml nav or a reference page's page_type: or description: frontmatter, then run `uv run docs-site --write` -->

## How Vultron Works

- [Concept Taxonomy](reference/vultron-taxonomy.md) — Reference definitions for the distinct concepts that together constitute Vultron. Use this document to understand what each named concept covers, what it excludes, and how the concepts relate to each other.
- [Glossary](reference/glossary.md) — The terms this documentation uses for the Vultron Coordinated Vulnerability Disclosure (CVD) protocol and its reference implementation, with the aliases to avoid and the ambiguities to watch for.
- [Documentation Conventions](reference/conventions.md) — The call-out boxes this documentation uses, and how to tell a normative page from an informative one.

## Coordinate Cases

- [Standards Crosswalks](reference/iso_crosswalks/index.md) — Crosswalks of the Vultron Protocol against the International Organization for Standardization (ISO) standards on vulnerability handling and disclosure, against Stakeholder-Specific Vulnerability Categorization (SSVC), and against the Common Security Advisory Framework (CSAF) 2.1 draft, each routed to the explanation that covers it and to the specification section that governs it.

## Implement the Protocol

- [Protocol Specification](reference/vultron-spec/index.md) — The Vultron Protocol specification: its messages, their encoding and transport, and the state machines participants use to track a shared case.
- [Messages](reference/messages/index.md) — How the formal message set relates to the ActivityStreams 2.0 (AS2) wire vocabulary the prototype sends and receives.
- [Protocol Quick Reference](reference/quick_reference.md) — A single-page summary of the protocol's state machines, message types, and how they interact.
- [Conformance Matrix](reference/conformance_matrix.md) — Which capability sets each Vultron role requires, which transitions each role may drive, and the named configurations a conformance claim can use, as tables checked against the specification.
- [Formal Protocol](reference/formal_protocol/index.md) — The Multi-Party Coordinated Vulnerability Disclosure (MPCVD) process defined as a communicating hierarchical state machine.
- [Vultron AS Objects](reference/activitypub/objects.md) — The Vultron ActivityStreams objects that extend the ActivityStreams vocabulary.

## Reference Implementation

- [rv Demo Protocol Trace](reference/rv-demo-protocol.md) — The message-level protocol trace of the Reporter + Vendor (rv) demo: every ActivityStreams activity exchanged, the trigger that causes it, and the case ledger entries it produces.
- [Demo Scenarios](topics/scenarios/index.md) — One narrative page for each multi-actor demo scenario, which tells the case that scenario runs from the participants' point of view.
- [Trigger API](reference/trigger-api.md) — The `POST /actors/{actor_id}/trigger/{behavior}` endpoints, each of which starts a protocol behavior on an actor's behalf.
- [Case Model Fields](reference/case_model_fields.md) — The fields of the case, participant, and status objects, as the reference implementation defines them.
- [Architecture](reference/specs/architecture.md) — The architecture requirements of the reference implementation: structure that carries over to other languages but that Vultron compliance does not require.
- [User Stories](reference/user_stories/index.md) — Requirements captured as user stories.

## Project

- [Versioning](reference/versioning.md) — The release versioning scheme for the Vultron repository.
- [What's New](about/whats_new.md) — The documentation pages added in the last 90 days.
- [License](about/license.md) — The license terms under which Vultron is distributed.
- [Acknowledgments](about/acknowledgements.md) — The prior works Vultron builds on, and the funding that supports it.

<!-- END GENERATED LOOKUP LISTING -->
