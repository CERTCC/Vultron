# Decisions

This section contains decision records for the Vultron project.

## What is an ADR?

An architectural decision record (ADR) is a document that captures an important architectural decision made along with its context and consequences.
We're using the expanded concept of an *Any Decision Record* (ADR) to capture any decision that is important to the project, not just architectural decisions.
We use [Markdown Any Decision Records (MADR)](https://adr.github.io/madr/) to document our architectural decisions.

### When to write an ADR

Write an ADR whenever you make an important decision that affects the project.
This includes decisions about the architecture, design, or implementation of the project, as well as decisions about the project's processes, tools, or infrastructure.
If you're not sure whether a decision is important enough to warrant an ADR, err on the side of writing one.
Discussing the decision with the team in a pull request, issue, or discussion is a good way to determine whether it's important enough to warrant an ADR.

### How to write an ADR

For new ADRs, please use [adr-template.md](_adr-template.md) as basis.
More information on MADR is available at <https://adr.github.io/madr/>.
General information about architectural decision records is available at <https://adr.github.io/>.

## Accepted ADRs

- [ADR-0000 Record architecture decisions](0000-record-architecture-decisions.md)
- [ADR-0001 Use Markdown Any Decision Records](0001-use-markdown-any-decision-records.md)
- [ADR-0002 Model Vultron Processes as Behavior Trees](0002-model-processes-with-behavior-trees.md)
- [ADR-0003 Build Our Own Behavior Tree Engine](0003-build-custom-python-bt-engine.md)
- [ADR-0004 Use Factory Pattern to Create Behavior Tree Nodes](0004-use-factory-methods-for-common-bt-node-types.md)
- [ADR-0005 Use ActivityStreams Vocabulary as Vultron Message Format](0005-activitystreams-vocabulary-as-vultron-message-format.md)
- [ADR-0006 Use CalVer for Project Versioning](0006-use-calver-for-project-versioning.md)

## Proposed ADRs

- none

## Rejected ADRs

- none

## Deprecated ADRs

- none

## Superseded ADRs

- none
