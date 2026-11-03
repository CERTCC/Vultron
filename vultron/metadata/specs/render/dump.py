"""The ``spec-dump`` command: selector parsing, ADR checks and LLM JSON output
(SR-07).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, NoReturn

from vultron.metadata.specs.llm_export import (
    CROSS_CUTTING_TOPICS,
    to_index_text,
    to_llm_json,
    to_requirements_text,
    uncited_adrs,
    unknown_selectors,
)
from vultron.metadata.specs.registry import (
    SpecRegistry,
    load_registry,
)
from vultron.metadata.specs.schema import (
    RFC2119Priority,
    Scope,
    SpecKind,
    SpecTag,
)


class _DumpArgParser(argparse.ArgumentParser):
    """ArgumentParser that reports errors as ``Error: ...`` and exits 2.

    A flag given without its value is reported as ``--flag requires a
    value`` (the wording SR-07-006 tests pin) instead of argparse's default.
    """

    def error(self, message: str) -> NoReturn:
        missing = re.match(
            r"argument (--[\w-]+).*: expected one argument", message
        )
        if missing:
            message = f"{missing.group(1)} requires a value"
        self.print_usage(sys.stderr)
        self.exit(2, f"Error: {message}\n")


def _csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _empty_selectors(args: argparse.Namespace) -> list[str]:
    """Report a selector given but naming nothing, e.g. ``--topic ""``.

    An empty list means "select nothing" to the exporter but "no selection" to
    the size guard, so it used to print an empty dump under a warning about an
    unfiltered one. It is a typo either way; say so.
    """
    return [
        f"--{flag} was given but names no values"
        for flag, dest in (
            ("topic", "topic"),
            ("group", "group"),
            ("ids", "ids"),
            ("adr", "adr"),
        )
        if getattr(args, dest) == []
    ]


def _build_dump_parser() -> _DumpArgParser:
    parser = _DumpArgParser(
        prog="spec-dump",
        description=(
            "Export specs as LLM-optimized JSON. Selectors (--topic, --group,"
            " --ids, --adr, --cross-cutting) are unioned; --kind/--tag/--scope/"
            "--priority narrow the result. Start with --index."
        ),
    )
    parser.add_argument("spec_dir", nargs="?", default="specs")
    parser.add_argument(
        "--index",
        action="store_true",
        help="print a plain-text topic/group map instead of JSON",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="print selected requirements as one line each, not JSON",
    )
    parser.add_argument("--topic", type=_csv, help="comma list of topic IDs")
    parser.add_argument("--group", type=_csv, help="comma list of group IDs")
    parser.add_argument("--ids", type=_csv, help="comma list of spec IDs")
    parser.add_argument(
        "--adr",
        type=_csv,
        help=(
            "comma list of ADR-NNNN ids; selects the requirements whose adr:"
            " field names one"
        ),
    )
    parser.add_argument(
        "--deps",
        action="store_true",
        help="add transitive dependencies of the selected specs",
    )
    parser.add_argument(
        "--cross-cutting",
        action="store_true",
        help=f"add topics {','.join(CROSS_CUTTING_TOPICS)} to the selection",
    )
    parser.add_argument("--kind", type=_csv, help="comma list of kinds")
    parser.add_argument("--tag", type=_csv, help="comma list; ALL must match")
    parser.add_argument("--scope", help="prototype or production")
    parser.add_argument("--priority", help="e.g. MUST, SHOULD, MAY")
    parser.add_argument(
        "--slim",
        action="store_true",
        help="only id/priority/statement(/note) per requirement",
    )
    return parser


def _enum_problems(args: argparse.Namespace) -> list[str]:
    """Validate enum-valued flags; one message per offending flag."""
    checks = (
        ("kind", args.kind, SpecKind),
        ("tag", args.tag, SpecTag),
        ("scope", [args.scope] if args.scope else None, Scope),
        (
            "priority",
            [args.priority] if args.priority else None,
            RFC2119Priority,
        ),
    )
    problems: list[str] = []
    for label, values, enum in checks:
        valid = {item.value for item in enum}
        invalid = sorted(set(values or []) - valid)
        if invalid:
            problems.append(
                f"unknown {label} value(s): {', '.join(invalid)}."
                f" Valid values: {', '.join(sorted(valid))}"
            )
    return problems


_ADR_ID_RE = re.compile(r"ADR-\d{4}")


def _malformed_adrs(args: argparse.Namespace) -> list[str]:
    """Report ``--adr`` values that are not ``ADR-NNNN`` ids (SR-07-026)."""
    bad = sorted(a for a in args.adr or [] if not _ADR_ID_RE.fullmatch(a))
    if not bad:
        return []
    return [
        f"malformed adr value(s): {', '.join(bad)}. Expected ADR-NNNN,"
        " e.g. ADR-0127"
    ]


def _unknown_adrs(spec_dir: Path, adrs: list[str]) -> list[str]:
    """Report ``--adr`` ids that name no decision record (SR-07-026).

    Records live in ``docs/adr/`` beside the spec directory, archived ones
    included. A typo such as ``ADR-0172`` for ``ADR-0127`` would otherwise
    select nothing and read as "this record governs nothing".
    """
    adr_dir = spec_dir.resolve().parent / "docs" / "adr"
    if not adr_dir.is_dir():
        return [
            f"--adr needs the decision records beside the spec directory,"
            f" but {adr_dir} does not exist"
        ]
    known = {
        f"ADR-{path.name[:4]}"
        for path in adr_dir.rglob("*.md")
        if re.match(r"\d{4}-", path.name)
    }
    unknown = sorted(set(adrs) - known)
    if not unknown:
        return []
    return [
        f"unknown adr value(s): {', '.join(unknown)} (no record in {adr_dir})"
    ]


def _note_uncited_adrs(registry: SpecRegistry, adrs: list[str]) -> None:
    """Say on stderr which ``--adr`` records no requirement cites in ``adr:``.

    Such a record is reached only by a prose citation, so ``--adr`` selects
    nothing for it. Saying so keeps an empty selection from reading as "this
    record governs nothing" (SR-07-027).
    """
    for adr_id in uncited_adrs(registry, adrs):
        print(
            f"spec-dump: note: no requirement names {adr_id} in adr:; any"
            f" rule it carries is stated where specs/ or notes/ cite it"
            f" (grep -rn {adr_id} specs/ notes/)",
            file=sys.stderr,
        )


def _fail(problems: list[str]) -> NoReturn:
    for problem in problems:
        print(f"Error: {problem}", file=sys.stderr)
    sys.exit(2)


def _emit(text: str) -> None:
    """Print *text*; a closed pipe (``spec-dump --index | head``) is not an error."""
    try:
        print(text)
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())


def _selection_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    topics = args.topic
    if args.cross_cutting:
        topics = [*(topics or []), *CROSS_CUTTING_TOPICS]
    return {
        "topic": topics,
        "groups": args.group,
        "spec_ids": args.ids,
        "adrs": args.adr,
        "include_deps": args.deps,
        "kinds": args.kind,
        "scope": args.scope,
        "tags": args.tag,
        "priority": args.priority,
    }


def main_llm_json() -> None:
    """LLM-optimized spec dump entry point (spec-dump / spec-dump-llm-json).

    Exports specs as flat, inheritance-resolved JSON for coding agents
    (SR-07-006 through SR-07-013).  Defaults to the ``specs/`` directory
    relative to the current working directory.

    Usage::

        spec-dump --index                       # plain-text topic/group map
        spec-dump --cross-cutting --slim        # ARCH, CS, TB, HP, SL, EH
        spec-dump --topic CM,EP --group ARCH-01
        spec-dump --ids EP-04-001 --deps
        spec-dump --adr ADR-0127 --text         # requirements citing a record
        spec-dump --kind protocol,architecture --priority MUST
        spec-dump [specs/]                      # full dump (large; warns)

    Agents should start with ``--index`` and load targeted subsets rather
    than reading raw YAML files or the full dump.
    """
    args = _build_dump_parser().parse_args()
    problems = (
        _enum_problems(args) + _empty_selectors(args) + _malformed_adrs(args)
    )
    if problems:
        _fail(problems)

    spec_dir = Path(args.spec_dir)
    if not spec_dir.is_dir():
        _fail([f"spec directory not found: {spec_dir}"])

    registry = load_registry(spec_dir)
    problems = unknown_selectors(
        registry, topics=args.topic, groups=args.group, spec_ids=args.ids
    )
    if args.adr:
        problems += _unknown_adrs(spec_dir, args.adr)
    if problems:
        _fail(problems)

    if args.adr:
        _note_uncited_adrs(registry, args.adr)

    kwargs = _selection_kwargs(args)
    if args.index:
        _emit(to_index_text(registry, **kwargs))
        return

    # Only the *set* selectors narrow the corpus enough to be readable.
    # An attribute filter such as --kind or --priority keeps whole topics, so
    # counting one as a selection let `--text --kind protocol` print the 285 KB
    # wall the guard exists to prevent. `--topic ""` is not a selection either:
    # it selects nothing, and used to print an empty dump plus a 0.0 MB warning.
    narrowed = any(
        kwargs[key] for key in ("topic", "groups", "spec_ids", "adrs")
    ) or bool(args.cross_cutting)
    filtered = any(
        value for key, value in kwargs.items() if key != "include_deps"
    )
    if args.text:
        if not narrowed:
            _fail(
                [
                    "--text needs a non-empty selection (--topic/--group/"
                    "--ids/--adr/--cross-cutting); every requirement as text is a"
                    " ~1 MB wall, and an attribute filter such as --kind or"
                    " --priority does not narrow it enough. Start with"
                    " --index."
                ]
            )
        _emit(to_requirements_text(registry, **kwargs))
        return

    output = to_llm_json(registry, slim=args.slim, **kwargs)
    if not filtered:
        print(
            f"spec-dump: warning: unfiltered dump is ~{len(output) / 1e6:.1f} MB"
            f" (~{len(output) // 4000}k tokens); use --index for a map and"
            " --topic/--group/--ids/--adr/--cross-cutting [--slim] to load"
            " subsets",
            file=sys.stderr,
        )
    _emit(output)
