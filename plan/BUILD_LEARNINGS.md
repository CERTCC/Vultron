## Implementation Notes

Longer-term notes can be found in `/notes/*.md`. This file is ephemeral
and will be reset periodically, so it's meant to capture more immediate
insights, issues, and learnings during the implementation process.

Append new items below any existing ones, marking them with the date and a
header.

### 2026-05-21 — #610: Starlette path parameter type for URL-keyed endpoints

When a FastAPI/Starlette endpoint needs to accept keys that may contain
forward slashes (e.g., HTTP URL IDs), use `{key:path}` instead of `{key}`.
Register the catch-all route **last** so specific literal routes (e.g.,
`/Offers/`, `/Actors/`) are matched first. The `%2F`-decoding-before-routing
behaviour in Starlette means there is no client-side workaround; only the
server-side `path` converter fixes the root cause.
