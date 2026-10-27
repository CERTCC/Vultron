---
description: >
  Structured requirements organized by portability tier: Protocol,
  Foundation, Architecture, Project, and Process.
stakeholder_type: [platform-developer, project-contributor]
level: 400
page_type: routing
subject: protocol
contents: routing
---

# Protocol Requirements

Structured requirements for the Vultron protocol and its implementation,
organized by portability tier. Each page is generated directly from the
`specs/*.yaml` source files at documentation build time, so the content always
reflects the current state of the specification.

The protocol requirements bind every implementation, in any language:

| Tier | Description |
|------|-------------|
| [Protocol](protocol.md) | The Vultron layer — required of any implementation in any language |
| [Foundation](foundation.md) | Rules inherited from ActivityStreams 2.0, ActivityPub, and HTTP |

The implementation requirements are for CERT/CC's reference implementation only, and another implementation need not follow them:

| Tier | Description |
|------|-------------|
| [Architecture](architecture.md) | How this implementation is structured — recommended, not required for compliance |
| [Project](project.md) | This codebase only — deployment choices, operating limits, internals |
| [Process](process.md) | How we run this project — CI, GitHub workflow, agent conventions |

Who must obey a rule decides its tier; naming code never does.
An implementer reads Protocol and Foundation.
