---
title: sub-agents claiming to "trim" compound statements often leave the original intact
type: learning
timestamp: 2026-08-20T18:30:00Z
source: ISSUE-2393-b
signal: concern
---

When splitting compound spec requirements, sub-agents frequently reported
"trimmed to single MUST" but left the original statement text unchanged, with
all the semicolons still present. After 8 parallel agents processed 30 files,
4 violations remained because agents added new child entries but did not
actually rewrite the parent statement.

**Mitigation**: after any mass split operation, always re-run the violation
detection script against all modified files to catch incomplete splits before
running spec-lint. Do not trust sub-agent completion reports — verify with the
detection script.

The detection script (backtick-aware):

```python
import yaml, glob, re

def count_outside_bt(text, char):
    count = 0; in_bt = False
    for c in text:
        if c == '`': in_bt = not in_bt
        elif not in_bt and c == char: count += 1
    return count

for f in sorted(glob.glob('specs/*.yaml')):
    with open(f) as fh:
        data = yaml.safe_load(fh)
    for g in (data.get('groups') or []):
        for spec in (g.get('specs') or []):
            stmt = spec.get('statement', '')
            cleaned = re.sub(r'`[^`]*`', '', stmt)
            sc = count_outside_bt(stmt, ';')
            mc = len(re.findall(r'MUST ', cleaned))
            if sc >= 2 or mc >= 3:
                print(f"[{spec['id']}] ;={sc} MUST={mc}: {stmt[:80]}")
```

**Promoted**: 2026-08-24 — captured in AGENTS.md.
Docs PR: [PR URL TBD].
