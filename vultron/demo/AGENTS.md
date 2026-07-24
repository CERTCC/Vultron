# AGENTS.md — vultron/demo/

> For project-wide conventions see the root [AGENTS.md](../../AGENTS.md).
> This file covers rules specific to demo scripts and multi-actor scenario code.

---

## Common Pitfalls — demo layer

### Puppeteer Actors via Trigger Endpoints, Never Spoof via Inbox Injection

When building multi-actor demo scripts, always drive actor behavior through
**real HTTP trigger endpoints** (e.g., `POST /{actor_id}/trigger/accept-actor-recommendation`).
Never construct and POST activities directly to actor inboxes to fake an
approval or state change.

**Why:** Inbox injection bypasses the BT evaluation layer entirely and creates
demos that exercise the wrong code path. The distinction:

- **Puppeteering** = sending a trigger that causes the actor to decide and act
  (validates the behavior tree path)
- **Spoofing** = forging the resulting activity as if the actor had already
  decided (skips the BT entirely)

**How to apply:** Before writing any demo step where one actor "responds" to
another, check whether the trigger endpoint for that response exists. If it
doesn't, implement the full hexagonal stack (trigger endpoint → service layer
→ BT) first, then write the demo step. Working around a missing endpoint by
injecting the response directly means the demo proves nothing about the
actual behavior tree path.

<!-- Source: ISSUE-1535 -->

---

### BT Demo `main()` Must Be Callable With No Arguments (Console-Script Entry Points)

`[project.scripts]` entry points invoke `main()` with **no arguments**. Demo
modules that define `def main(args):` — where `args` is a required positional
parsed by an `if __name__ == "__main__"` block — will fail immediately with
`TypeError: main() missing 1 required positional argument` when invoked via
`uv run <script>`.

**Fix:** give `main` an `args=None` default and fall back to `_parse_args()`:

```python
def main(args=None) -> None:
    if args is None:
        args = _parse_args()
    ...
```

This preserves the path used by `vultron/demo/cli.py`'s click sub-group (which
passes a `SimpleNamespace` via `_bt_args()`) while also being callable with
zero arguments from a console script.

**Always test the actual console script** (`PYTHONPATH= uv run <script>`) — not
just the module import — and clear `PYTHONPATH=/app` devcontainer contamination
(see root `AGENTS.md` § "PYTHONPATH=/app contaminates imports").

<!-- Source: ISSUE-1568 -->

---

### Extract Before Reuse: No Copy-Paste from Existing Scenario Files

Before writing a **second use** of a pattern from an existing scenario file,
extract it to `vultron/demo/helpers/` first. Do not copy-paste a function body,
a polling loop, a verification block, or any other logical unit from an
existing scenario file into a new one.

**Why:** Every demo scenario written by copying the previous one propagates
latent bugs alongside valid patterns. Issue #1632 documented residual
duplication remaining after PR #1629 reactively extracted five helper modules.
Copy-paste is the root cause; extraction-first prevents the problem from
recurring.

**How to apply:**

1. Before writing a new scenario step, grep `vultron/demo/helpers/` for an
   existing helper that covers the same pattern.
2. If one exists, import and call it. Do not inline a copy.
3. If none exists and this is the second occurrence of the pattern, extract it
   to the appropriate `helpers/` module first, then call it from both places.
4. A pattern that appears only once may stay inline, but add a comment marking
   it as a candidate for extraction when a second use arises.

This rule applies to scenario files in `vultron/demo/scenario/`. Exchange demos
under `vultron/demo/exchange/` are lower-level and may duplicate less when a
full helper would add more abstraction than value.

See `specs/multi-actor-demo.yaml` DEMOMA-16-001 for the normative requirement
(a MUST-level specialisation of the project-wide SHOULD rule CS-22-001 in
`specs/code-style.yaml`).

<!-- Source: ISSUE-1652 -->
