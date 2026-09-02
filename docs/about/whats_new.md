# What's New

Pages added in the last 90 days:

```python exec="true" idprefix=""
import subprocess
import datetime
import os

since = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()

result = subprocess.run(
    [
        "git", "log",
        "--diff-filter=A",
        "--name-only",
        "--format=",
        f"--since={since}",
        "--",
        "docs/",
    ],
    capture_output=True,
    text=True,
)

files = sorted({
    f.strip() for f in result.stdout.splitlines()
    if f.strip().endswith(".md")
})

# Strip paths excluded from nav (underscore-prefixed, includes/, etc.)
def is_navigable(path):
    parts = path.split("/")
    return not any(p.startswith("_") for p in parts) and "includes" not in parts

files = [f for f in files if is_navigable(f)]

if not files:
    print("_No pages added in the last 90 days._")
else:
    for f in files:
        # docs/some/path/page.md -> /some/path/page/
        url_path = f.removeprefix("docs/").removesuffix(".md") + "/"
        # Build a readable title from the filename
        title = os.path.basename(f).removesuffix(".md").replace("-", " ").replace("_", " ").title()
        print(f"- [{title}](/{url_path})")
```
