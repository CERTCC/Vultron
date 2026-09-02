---
title: A test fixture built on the wrong base class silently skipped the branch it was meant to cover
type: learning
timestamp: "2026-09-02T00:00:00Z"
source: ISSUE-2904
signal: concern
---

`test/wire/as2/vocab/test_vocab_utils.py` has had a `test_json2md` since the
file was written. It passed continuously while the function it tests was
100% broken for every real input.

The fixture was the problem:

```python
class Foo(as_Base):
    bar: str = "baz"
```

`_strip_published_udpated` is guarded by `hasattr(obj, "published")`. `as_Base`
declares neither `published` nor `updated` — those live on `as_Object`, one
level down. So both guards evaluated False, the body never ran, and the test
asserted that nothing went wrong. `as_Base` is also not frozen, so even a
fixture that *did* carry the fields would not have reproduced the failure.

**Why it matters:** this is worse than missing coverage. Missing coverage is
visible in a coverage report and reads as a known gap. A test like this reports
the function as covered while never executing the line that matters, so it
actively suppresses the signal. 101 published pages rendered Python tracebacks
for as long as this test was green.

**How to apply:** when a function branches on `hasattr`, `isinstance`,
`in model_fields`, or any other capability probe, the test fixture MUST be a
type that *takes* the branch. Prefer a real domain type over a minimal stand-in
subclass — here, `as_VulnerabilityReport` rather than a local `Foo(as_Base)`.
When a stand-in is genuinely needed, assert the precondition explicitly so the
fixture cannot silently drift out of the branch:

```python
def test_frozen_wire_object_carries_both_timestamps(self):
    report = _frozen_report()
    self.assertIsNotNone(report.published)
    self.assertTrue(type(report).model_config.get("frozen"))
```

Related: the two-branch base hierarchy means `as_Base` and `as_Object` differ
in both field set *and* mutability — see [[wire-artifact-immutability]] and
ADR-0017. Picking the wrong one for a fixture changes what the test can
possibly detect.
