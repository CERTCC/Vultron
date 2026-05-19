---
title: Demo CI — GitHub Actions Demo Integration Workflow
status: active
---

# Demo CI — GitHub Actions Demo Integration Workflow

Design decisions and implementation guidance for `DEMOCI-01` through
`DEMOCI-03` (`specs/demo-ci.yaml`). Addresses the gap where all pytest tests
pass while the live demo silently fails (e.g., issue #557: 404 errors in logs,
process exits 0).

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Pursue demo runner hardening and CI workflow together? | Yes — both, in order | Runner hardening is a prerequisite: CI exit code detection only works if the runner exits non-zero on failure |
| CI workflow trigger | PRs to main (path-filtered) + `workflow_dispatch` | Automatic regression detection on every relevant PR; manual trigger for debugging |
| Path filter scope | `vultron/**`, `docker/**`, `integration_tests/**`, `pyproject.toml`, `uv.lock` | All files that can affect demo container behaviour |
| Dependabot PRs | Skip via `startsWith(github.head_ref, 'dependabot/')` | Dependabot PRs arrive in waves; `python-app.yml` still guards broken deps |
| Workflow location | Separate `demo-integration.yml` | Keeps demo pipeline isolated from unit-test pipeline; both run concurrently |
| Demo scenario in CI | Two-actor only initially | Most complete and stable scenario; add others incrementally as they mature |
| Failure detection | `--exit-code-from demo-runner` | Simplest reliable signal once runner exits non-zero on failure |
| Error accumulation | Accumulate all, raise `DemoFailureError` at end | Full diagnostic output from a single run |
| Error tracking location | Extend `demo_step` / `demo_check` context managers | All steps already use them; centralises the change |
| Image caching | GitHub Actions Docker layer cache | Avoids rebuilding unchanged dependency layer on every run |
| Log upload | Artifact, failure only | Clean successful runs; full context when debugging |
| CI timeout | 15 minutes | Demo takes 3–5 min; headroom without infinite hangs |
| Extensibility documentation | Both spec requirement + notes file | Future agents need to know the pattern; spec captures the contract |

---

## Demo Runner Hardening (DEMOCI-01)

### DemoFailureError

Add `DemoFailureError` to `vultron/errors.py`:

```python
class DemoFailureError(VultronError):
    """Raised when a demo scenario completes with one or more step failures."""
    def __init__(self, message: str, failures: list[str]) -> None:
        super().__init__(message)
        self.failures = failures
```

### Extending `demo_step` and `demo_check`

The cleanest approach is a per-scenario error accumulator that the context
managers report to. Introduce a module-level accumulator in
`vultron/demo/utils.py` (or a context-local one passed through the demo
scenario function):

```python
from contextlib import contextmanager
from typing import Generator

_demo_failures: list[str] = []

def reset_demo_failures() -> None:
    """Call at the start of each scenario to clear any prior failures."""
    _demo_failures.clear()

def assert_demo_success() -> None:
    """Call at the end of a scenario; raises DemoFailureError if any failures."""
    if _demo_failures:
        raise DemoFailureError(
            f"{len(_demo_failures)} demo step(s) failed",
            failures=list(_demo_failures),
        )

@contextmanager
def demo_step(description: str) -> Generator[None, None, None]:
    logger.info(f"🚥 {description}")
    try:
        yield
        logger.info(f"🟢 {description}")
    except Exception as exc:
        logger.error(f"🔴 {description}: {exc}")
        _demo_failures.append(f"STEP FAILED: {description} — {exc}")
        # Do NOT re-raise: accumulate and continue

@contextmanager
def demo_check(description: str) -> Generator[None, None, None]:
    logger.info(f"📋 {description}")
    try:
        yield
        logger.info(f"✅ {description}")
    except Exception as exc:
        logger.error(f"❌ {description}: {exc}")
        _demo_failures.append(f"CHECK FAILED: {description} — {exc}")
        # Do NOT re-raise: accumulate and continue
```

> **Important**: `demo_step` currently re-raises on exception. Changing it to
> accumulate-and-continue is a behaviour change. Review existing callers to
> ensure no caller depends on the re-raise for control flow (e.g., early
> return after a failed seed step). Where a step is critical and subsequent
> steps cannot run without it, wrap the accumulator check inline:
>
> ```python
> with demo_step("Critical seed step"):
>     seed_actors()
> if _demo_failures:
>     assert_demo_success()  # fail fast if critical step failed
> ```

### HTTP 404 detection

In `vultron/demo/utils.py`, the HTTP helper functions (e.g., `post_to_inbox`,
`get_actor`) should check the response status code and record a failure for
any 404:

```python
def _check_response(response: requests.Response, context: str) -> None:
    if response.status_code == 404:
        msg = f"HTTP 404 from {response.url} ({context})"
        logger.error(msg)
        _demo_failures.append(msg)
    response.raise_for_status()
```

Call `_check_response(resp, "post_to_inbox")` after every HTTP call.

### Entry points

Each scenario `main()` function should follow this pattern:

```python
def main() -> None:
    reset_demo_failures()
    try:
        run_scenario()
    finally:
        assert_demo_success()  # raises DemoFailureError if any failures
```

The `DemoFailureError` propagates to the top-level Click command, which exits
non-zero (Click converts unhandled exceptions to exit code 1 by default, or
use `sys.exit(1)` explicitly).

---

## GitHub Actions Workflow (DEMOCI-02)

### Skeleton: `.github/workflows/demo-integration.yml`

```yaml
name: Demo Integration

on:
  pull_request:
    branches: ["main"]
    paths:
      - "vultron/**"
      - "docker/**"
      - "integration_tests/**"
      - "pyproject.toml"
      - "uv.lock"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  demo:
    name: Two-Actor Demo Integration
    runs-on: ubuntu-latest
    timeout-minutes: 15
    # Skip for Dependabot PRs — python-app.yml test suite guards broken deps.
    if: "!startsWith(github.head_ref, 'dependabot/')"

    steps:
      - uses: actions/checkout@<pinned-sha>

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@<pinned-sha>

      - name: Cache Docker layers
        uses: actions/cache@<pinned-sha>
        with:
          path: /tmp/.buildx-cache
          key: ${{ runner.os }}-buildx-${{ hashFiles('docker/Dockerfile', 'pyproject.toml', 'uv.lock') }}
          restore-keys: |
            ${{ runner.os }}-buildx-

      - name: Build images
        run: |
          docker compose -f docker/docker-compose-multi-actor.yml build \
            --build-arg BUILDKIT_INLINE_CACHE=1

      - name: Run two-actor demo
        run: |
          docker compose -f docker/docker-compose-multi-actor.yml \
            up --abort-on-container-exit --exit-code-from demo-runner \
            -e DEMO=two-actor

      - name: Collect container logs
        if: failure()
        run: |
          docker compose -f docker/docker-compose-multi-actor.yml logs \
            > /tmp/demo-logs.txt 2>&1

      - name: Upload logs artifact
        if: failure()
        uses: actions/upload-artifact@<pinned-sha>
        with:
          name: demo-container-logs
          path: /tmp/demo-logs.txt
          retention-days: 7

      - name: Tear down containers and volumes
        if: always()
        run: |
          docker compose -f docker/docker-compose-multi-actor.yml down -v
```

> **SHA pinning**: All `uses:` references MUST use pinned SHA commits
> (CISEC-01). Replace `<pinned-sha>` with the correct hashes before merging.
> See `.github/workflows/python-app.yml` for the pattern already in use.

---

## Extensibility for Additional Demo Scenarios (DEMOCI-03)

When a new demo scenario (e.g., `three-actor`, `multi-vendor`) reaches a
stable, reproducible state, update `demo-integration.yml` in the same PR
that introduces the scenario. The recommended pattern is a matrix job:

```yaml
strategy:
  matrix:
    demo: [two-actor, three-actor]
  fail-fast: false
```

`fail-fast: false` ensures that one failing scenario does not prevent others
from running, giving a complete picture of CI health across all demos.

Until a scenario is ready for CI, document it in the `demo-integration.yml`
as a comment so future contributors know where to add it:

```yaml
# Future scenarios to add when stable:
#   - three-actor  (multi-coordinator; tracked in #<issue>)
#   - multi-vendor (tracked in #<issue>)
```

---

## Testing Pattern

Integration tests for the demo runner harness itself (`test/demo/`) should
verify:

1. `reset_demo_failures()` clears the accumulator.
2. A failing `demo_step` block adds an entry to `_demo_failures` and does not
   re-raise.
3. `assert_demo_success()` raises `DemoFailureError` when failures are present.
4. A 404 HTTP response from any helper is recorded as a failure.
5. `assert_demo_success()` does not raise when `_demo_failures` is empty.

---

## Related Specs and Notes

- `specs/multi-actor-demo.yaml` — DEMOMA container orchestration requirements
- `specs/demo-cli.yaml` — DC demo CLI isolation and entry-point requirements
- `specs/ci-security.yaml` — CISEC SHA pinning requirement for workflow files
- `notes/two-actor-demo.md` — Two-actor scenario design reference
