---
title: "TASK-AF.8-10 — Factory call-site type annotation fixes"
type: implementation
date: '2026-04-30'
source: TASK-AF.8-10
---

## TASK-AF.8-10 — Factory call-site type annotation fixes

Completed the TASK-AF.8-10 factory migration by fixing 91 mypy/pyright type
errors introduced when migrating `vocab/examples/` and `demo/` call sites
from internal Vultron activity subclasses to factory functions.

Root cause: factory functions return base AS2 wire types (`as_Offer`,
`as_Create`, etc.) but the migrated code still had `-> VultronActivity`
return type annotations. `VultronActivity` is a domain model; it is NOT a
supertype of the AS2 wire types.

### Files changed

- `vultron/wire/as2/vocab/examples/` (all 7 files): changed `-> VultronActivity`
  return annotations to the specific AS2 base wire types returned by factories.
- `vultron/demo/utils.py#get_offer_from_datalayer`: removed unnecessary
  `VultronActivity.model_validate(raw.model_dump(...))` wrapping; returns
  `as_Offer` directly.
- `vultron/demo/exchange/receive_report_demo.py`, `trigger_demo.py`: corrected
  return types to `-> as_Offer`.
- `vultron/demo/scenario/two_actor_demo.py`, `three_actor_demo.py`,
  `multi_vendor_demo.py`: replaced `VultronActivity.model_validate(...)` calls
  with specific AS2 wire types; updated function signatures.
- `test/wire/as2/vocab/test_vocab_examples.py`: added `isinstance` assertion
  for `ChoosePreferredEmbargoActivity` to enable pyright type narrowing before
  `.one_of` access.

### Outcome

- Black, flake8, mypy, pyright: all pass (0 errors)
- pytest: 2181 passed, 12 skipped
- AF.12 (rename internal classes private) remains as next sub-task
