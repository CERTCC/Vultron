# Record Architecture Decisions

* Status: accepted
* Deciders: adh
* Date: 2023-10-16

## Context and Problem Statement

We need a way to record architectural decisions made in this project.

## Considered Options

* Do not capture significant decisions at all.
* Capture decisions in an unstructured text file.
* Capture decisions in a structured text file.

## Decision Outcome

Chosen option: "Capture decisions in a structured text file", because it
establishes a simple way to record decisions while keeping the effort
low. The append-only style of writing ADRs also makes it possible to
keep a record of the project history and to learn from the past.

### Positive Consequences

* Maintains a record of significant project architectural decisions and their context
* Provides an opportunity to learn from past decisions

### Negative Consequences

* Adds a small burden to each decision
* May be seen as unnecessary overhead for small projects or teams

## Links

* Reference: [Architecture Decision Records](https://adr.github.io/)
* Reference: [MADR](https://adr.github.io/madr/)
* Reference: [pyadr](https://github.com/opinionated-digital-center/pyadr)
