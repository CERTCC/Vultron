---
description: >
  Structured requirements organized by portability tier: Protocol and
  Foundation in the Protocol Specification's Requirements Catalog, and
  Architecture, Project, and Process for the reference implementation.
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: routing
subject: protocol
contents: routing
---

# Protocol Requirements

Structured requirements for the Vultron protocol and its implementation, organized by portability tier.
Each tier is generated directly from the `specs/*.yaml` source files at documentation build time, so the content always reflects the current state of the specification.

The protocol requirements bind every implementation, in any language.
They are the normative text of the Protocol Specification, and they are published in its [§14 Requirements Catalog](../vultron-spec/requirements/index.md):

| Tier | Description |
|------|-------------|
| Protocol | The Vultron layer — required of any implementation in any language. Its requirements are grouped by theme, from [§14.1 Vultron Protocol](../vultron-spec/requirements/vultron-protocol.md) to [§14.7 Transport and Security](../vultron-spec/requirements/transport-security.md). |
| Foundation | Rules inherited from ActivityStreams 2.0, ActivityPub, and the Hypertext Transfer Protocol (HTTP). They are in [§14.8 Inherited Requirements](../vultron-spec/requirements/foundation.md). |

The implementation requirements are for CERT/CC's reference implementation only, and another implementation need not follow them:

| Tier | Description |
|------|-------------|
| [Architecture](architecture.md) | How this implementation is structured — recommended, not required for compliance |
| [Project](project.md) | This codebase only — deployment choices, operating limits, internals |
| [Process](process.md) | How we run this project — CI, GitHub workflow, agent conventions |

Who must obey a rule decides its tier; naming code never does.
An implementer reads Protocol and Foundation.
