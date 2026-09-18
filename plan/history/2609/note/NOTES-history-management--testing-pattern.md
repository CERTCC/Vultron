---
source: NOTES-history-management--testing-pattern
timestamp: '2026-09-17T17:25:22.424697+00:00'
title: Testing Pattern
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) skeleton for shipped tool; deprecated date: field
**Superseded by:** test/metadata/test_append_history.py

---

## Testing Pattern

```python
# test/metadata/test_append_history.py
import subprocess
from pathlib import Path

def test_append_creates_entry_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    content = "---\ntitle: Test\ntype: idea\ndate: 2026-04-28\nsource: IDEA-TEST\n---\n\nBody."
    result = subprocess.run(
        ["uv", "run", "append-history", "idea"],
        input=content,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    entry_files = list(Path("plan/history").rglob("*.md"))
    assert any("IDEA-TEST" in f.name for f in entry_files)

def test_append_regenerates_readme(tmp_path, monkeypatch):
    # After append, plan/history/YYMM/README.md should exist
    ...

def test_invalid_type_exits_nonzero():
    result = subprocess.run(
        ["uv", "run", "append-history", "bogus_type"],
        input="content",
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
```
