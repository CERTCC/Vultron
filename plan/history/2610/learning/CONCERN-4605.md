---
source: CONCERN-4605
timestamp: '2026-10-14T16:05:00.968197+00:00'
title: Does the codebase need a CaseActor class?
type: learning
---

## Problem

The maintainer (2026-10-14, during the PR #4520 review) is skeptical that the codebase needs a `CaseActor` class at all, unless it is purely a convenience for setting default values on an actor we use consistently — the same way a `VendorActor` or `ReporterActor` class would only DRY up our implementation and would never be an object outside it.

In the protocol, the CASE_MANAGER is an ordinary actor designated for a particular case; it is not a distinct identity or object type (ADR-0088). On the wire, a CaseActor is already an ActivityStreams `Service`.

Today `vultron/core/models/case_actor.py` defines `CaseActor(CoreObject)` with `type_ = Service`, an internal `outbox` tracking list, AS2 collection handling, and its own `CORE_VOCABULARY` registration under the key `"CaseActor"` (ADR-0017, #729). Wire-layer classes and examples also use it. Some code may treat it as a distinct type (vocabulary lookups, routing, type checks), which would encode a distinction the protocol does not have.

## Open questions

- Is `CaseActor` only a convenience preset for a `Service` actor, or does any code rely on it being a distinct type?
- Should it become a factory/preset (like a hypothetical `VendorActor`) with no separate vocabulary registration, or be removed in favour of a plain actor plus the CASE_MANAGER role?
- Which specs still name `CaseActor` as a type (e.g. CM-05-013's earlier wording) and need rewording?

## Reference

Raised by the maintainer while dropping CaseActor from CM-05-001's list of distinct protocol object types (PR #4520, #3601).

**Resolved**: 2026-10-14. Implementation is tracked in #4612. Decision: remove the class outright. The case actor is an ordinary `VultronService`. No protocol logic depends on the type, a stored `Service` already reads back as `VultronService`, and the `VultronOutbox` tracking list was dead. CM-05-013 no longer exists. The live spec that encodes the exception is ARCH-12-006, amended in #4612.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4611>.
