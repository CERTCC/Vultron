#!/usr/bin/env python3
"""Colorize docker compose log output with per-service hex colors.

Reads ``docker compose up --ansi=never`` output from stdin and applies
configurable 24-bit ANSI foreground colors to each service's log-line
prefix, producing consistent coloring regardless of container startup
order.

Color configuration is loaded from the file pointed to by the
``COMPOSE_SERVICE_COLORS`` environment variable (default:
``docker/service-colors.env`` relative to this script's parent
directory).  Each non-blank, non-comment line in that file must have
the form::

    service_name=HEXCOLOR

where ``service_name`` is the bare docker-compose service name (replica
suffixes like ``-1`` are stripped automatically) and ``HEXCOLOR`` is a
``#RRGGBB`` value.

Colors are applied only when stdout is a TTY; output redirected to a
file or pipe is passed through unchanged so log archives stay readable.

Usage (from the repository root)::

    docker compose ... up --ansi=never 2>&1 | python3 \\
        integration_tests/demo/colorize_compose_logs.py
"""

import os
import re
import sys
from pathlib import Path

# ── Default config file path ──────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_COLORS_FILE = (
    _SCRIPT_DIR.parent.parent / "docker" / "service-colors.env"
)

COLORS_FILE = Path(
    os.environ.get("COMPOSE_SERVICE_COLORS", str(_DEFAULT_COLORS_FILE))
)

# ── Load color map ────────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def _hex_to_ansi(hexcolor: str) -> str:
    """Return a 24-bit ANSI foreground color escape for *hexcolor* (``#RRGGBB``)."""
    m = _HEX_RE.match(hexcolor.strip())
    if not m:
        return ""
    h = m.group(1)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\033[38;2;{r};{g};{b}m"


def _load_colors(path: Path) -> dict[str, str]:
    """Parse *path* into a ``{service_name: ansi_escape}`` dict."""
    colors: dict[str, str] = {}
    if not path.exists():
        return colors
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            name, _, hexcolor = line.partition("=")
            ansi = _hex_to_ansi(hexcolor.strip())
            if ansi:
                colors[name.strip()] = ansi
    return colors


_COLORS = _load_colors(COLORS_FILE)
_RESET = "\033[0m"

# ── Line pattern ──────────────────────────────────────────────────────────────
# Matches the "service-name-N  | " prefix that docker compose emits in
# --ansi=never (plain-text) mode.  The service name may contain letters,
# digits, underscores, and hyphens.  The replica index (-1, -2, …) is
# optional; its base name is used for color lookup.
_PREFIX_RE = re.compile(r"^([a-zA-Z0-9_-]+?)(-\d+)?\s+\|\s")


def _colorize(line: str) -> str:
    """Return *line* with its service-name prefix wrapped in the configured color."""
    m = _PREFIX_RE.match(line)
    if not m:
        return line
    base_name = m.group(1)  # e.g. "finder" from "finder-1"
    full_name = m.group(1) + (m.group(2) or "")  # e.g. "finder-1"
    ansi = _COLORS.get(full_name) or _COLORS.get(base_name)
    if not ansi:
        return line
    end = m.end()  # character position after "  | "
    return f"{ansi}{line[:end]}{_RESET}{line[end:]}"


def main() -> None:
    """Read stdin line-by-line and write colorized output to stdout."""
    is_tty = sys.stdout.isatty()
    for line in sys.stdin:
        if is_tty:
            sys.stdout.write(_colorize(line))
        else:
            sys.stdout.write(line)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
