---
source: CONCERN-505
timestamp: '2026-08-07T20:16:42.756829+00:00'
title: 15 outstanding TODO/FIXME/XXX markers in production code
type: learning
---

11 outstanding TODO/FIXME/HACK comments remain in production source files,
concentrated in core state machines, wire-layer vocabulary, and legacy BT
modules. These represent partially-finished refactors or deferred design
decisions that accumulate silently over time.

Affected files: `vultron/core/states/cs.py`, `vultron/wire/as2/vocab/objects/embargo_event.py`,
`vultron/wire/as2/vocab/examples/embargo.py`, `vultron/wire/as2/vocab/examples/report.py`,
`vultron/wire/as2/vocab/activities/case_participant.py` (2 TODOs),
`vultron/wire/as2/vocab/base/objects/object_types.py`,
`vultron/wire/as2/vocab/base/objects/collections.py`,
`vultron/bt/report_management/_behaviors/report_to_others.py`,
`vultron/bt/base/bt_node.py`,
`vultron/bt/base/demo/pacman.py`.

**Resolved**: 2026-08-07 — implementation tracked in
[#2096](https://github.com/CERTCC/Vultron/issues/2096),
[#2097](https://github.com/CERTCC/Vultron/issues/2097),
[#2098](https://github.com/CERTCC/Vultron/issues/2098),
[#2099](https://github.com/CERTCC/Vultron/issues/2099).
