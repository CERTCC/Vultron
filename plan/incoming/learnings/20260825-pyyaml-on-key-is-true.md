---
title: PyYAML parses bare `on:` mapping key as Python True, not string "on"
type: learning
timestamp: 2026-08-25T00:00:00Z
source: ISSUE-2184
signal: concern
---

PyYAML (which follows YAML 1.1) resolves the bare token `on` as a boolean
`True` when it appears as a mapping key. A GitHub Actions workflow file that
begins with `on:` is therefore loaded by `yaml.safe_load()` as
`{True: {...}, 'name': '...', 'jobs': {...}}` — NOT `{'on': {...}, ...}`.

Any test or tool that reads workflow YAML and queries the trigger block must use:

```python
on = wf_data.get(True, wf_data.get("on", {}))  # type: ignore[call-overload]
```

The `# type: ignore[call-overload]` is required because `dict[str, Any]`
does not accept a `bool` key — but the actual runtime dict has one.

Discovered during PR #2612 (`task/2184-ci-failure-alerting`) while writing
`test/ci/test_workflow_failure_notification.py`. The fix is applied in that
file. The existing `test_workflow_sha_pinning.py` never queries trigger type
and is not affected.

**Risk**: any new test that parses workflow YAML and tries to filter by trigger
(push-to-main, schedule, etc.) will silently match zero workflows if it uses
`wf_data.get("on", {})` — and its parametrize fixture will produce an empty
list, making all parametrized test cases SKIP instead of FAIL. The
`test_qualifying_workflows_found` assertion in the notification test catches
this specifically.
