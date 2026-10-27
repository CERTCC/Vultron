---
description: >
  How to suggest a change to the Vultron protocol, its documentation, or the
  reference implementation, and what happens to the suggestion.
stakeholder_type: ALL
level: 100
page_type: how-to
subject: neutral
---

# Proposing a Change

This guide shows how to suggest a change to Vultron: to the protocol, to this documentation, or to the reference implementation.
All three are maintained in one public repository, [CERTCC/Vultron](https://github.com/CERTCC/Vultron){:target="_blank"}, so every proposal starts in the same place.

## Before you start

You need a GitHub account.
Read the [Open Questions](open_questions.md) first: if your question is already there, add to the issue it links rather than opening a new one.

## Suggest the change

1. Search the [issues](https://github.com/CERTCC/Vultron/issues){:target="_blank"} for one that already describes your change.
   If one does, comment on it.
2. If your idea still needs discussion before it is a concrete proposal, start a thread in [Discussions](https://github.com/CERTCC/Vultron/discussions){:target="_blank"}.
3. Otherwise, [open an issue](https://github.com/CERTCC/Vultron/issues/new){:target="_blank"}.
   Say what you want to change, why, and which pages or behaviors it affects.
   For a protocol change, name the section of the [Vultron Protocol Specification](../reference/vultron-spec/index.md) it touches.

## What happens next

The maintainers reply on the issue.
A change that alters how the protocol works is recorded as a decision record before it is made, so the reason for it stays on file.
These records are reached from [Working on This Implementation](../about/project_record.md).
A protocol change appears in a later version of the specification; [Versioning](../reference/versioning.md) explains how versions are numbered.

## If you want to make the change yourself

Discuss it on the issue first, so your work matches what the maintainers will accept.
Then follow [Contributing](../about/contributing.md), which sets out the terms of submission and how to open a pull request.
