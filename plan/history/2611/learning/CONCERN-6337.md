---
source: CONCERN-6337
timestamp: '2026-11-12T19:03:17.519529+00:00'
title: ConnectorPlugin requires push methods, so a read-only polled VINCE connector
  cannot satisfy it
type: learning
---

Theme: theme:capability-architecture — the VINCE connector plugs into a connector shape that fits a read-only, polled source, so the later VINCE gateway extends it instead of replacing it.

## Summary

`ConnectorPlugin` (`vultron/adapters/connectors/base.py`) requires two methods: `on_inbound_event` (the outside system pushes an event in) and `on_outbound_event` (Vultron pushes an event out). The shadow's VINCE connector does neither. A Sentinel polls it, and it must have no write path (#5963 AC-2). So it cannot satisfy the Protocol without a write method it must not have.

## Surface Symptom vs. Underlying Problem

- **Surface symptom:** the example `VinceConnector` (`connectors/example/vince.py`) raises `NotImplementedError` in both methods. It reads as a stub waiting for code.
- **Underlying problem:** the Protocol assumes a two-way, push-driven connector. It has no shape for a read-only source that a caller polls. Even its docstring's example mappings (case created → `create_case`) assume push.
- **Correct, keep:** entry-point discovery under `vultron.connectors` (ARCH-05-003, #5610). Connectors live in adapters, and core never imports them (ARCH-05-001). A connector is any plugin to an outside system, whatever its direction (`CONTEXT.md`).

## Category

Design / architecture.

## Severity

Medium. It blocks #5963, and through it the Epic's finish line.

## Evidence

- `vultron/adapters/connectors/base.py`: both methods are required members of a `runtime_checkable` Protocol.
- `vultron/adapters/connectors/example/vince.py`: push-style mappings in the docstring.
- #5963 AC-2: the client's public interface has no method that sends a write request.

## Impact if Ignored

#5963 either adds an `on_outbound_event` that must refuse every call (a write path in the interface, which AC-2 forbids), or skips the Protocol and so is not discovered as a plugin (AC-3 fails).

## Suggested Action

Decide the connector shape before #5963. One option: split the Protocol into a read side that a Sentinel polls and an optional write side. The shadow's VINCE connector implements only the read side, and the 2027 VINCE gateway adds the write side. Update ARCH-05-002 if the shape changes.

#5610 does not wait on this. Its loader checks each entry point against whichever Protocol exists; if the Protocol splits, only that check changes.

**Resolved**: 2026-11-12 — implementation tracked in #6358.

Docs PR: https://github.com/CERTCC/Vultron/pull/6357.

Spec: `specs/architecture.yaml`.

Notes: `notes/architecture-hexagonal.md`.
