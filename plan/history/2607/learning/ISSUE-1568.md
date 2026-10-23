---
title: BT demo main() must be callable with no args to work as a console-script entry point
type: learning
timestamp: 2026-07-21T00:00:00Z
source: ISSUE-1568
---

## Observation

The `vultron/bt/base/demo/` demos (`pacman`, `robot`, `cvd`) define
`def main(args): ...` — the `args` positional is provided by their
`if __name__ == "__main__"` block, which calls `_parse_args()` first.

But `pyproject.toml` `[project.scripts]` entry points invoke `main()` with
**no arguments** (e.g. `vultrabot_pacman="...pacman:main"`). So
`uv run vultrabot_pacman` fails immediately with:

```text
TypeError: main() missing 1 required positional argument: 'args'
```

This was latently broken for `vultrabot_pacman`/`vultrabot_robot` and for the
`vultrabot` entry point (which additionally pointed at a deleted module).

## Fix

Make `main` self-parse when called with no args, preserving the path used by
`vultron/demo/cli.py`'s click sub-group (which passes a `SimpleNamespace` via
`_bt_args()`):

```python
def main(args=None) -> None:
    if args is None:
        args = _parse_args()
    ...
```

## Pattern to apply

When wiring a `vultron/bt/base/demo/` module (or any module) to a
`[project.scripts]` entry point, verify the target callable is invocable with
zero arguments. If it currently takes a parsed-args positional, give it an
`args=None` default and fall back to `_parse_args()`. Test the actual console
script (`PYTHONPATH= uv run <script>`), not just the module import — and
remember the devcontainer's `PYTHONPATH=/app` must be cleared or the stale
baked image shadows the relocated module (see
[[20260720-pythonpath-app-contaminates-uv-run]]).

**Promoted**: 2026-07-22 — captured in `vultron/demo/AGENTS.md`.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1608>8>8>.
