"""Score docs/ pages for readability and rank them by revision opportunity.

Run from the repo root (see SKILL.md for the pinned textstat version):

    uvx --with 'textstat>=0.7.13,<0.8' python -I \
        .agents/skills/readability-audit/readability_audit.py [options]

Sentence and paragraph limits come from the docs style guide
(.agents/skills/shared/docs-style-guide.md): SG-14 (sentences over 28 words)
and SG-16 (paragraphs over five sentences). The scope follows the guide's
Scope table, plus the generated pages mkdocs excludes.
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass

import textstat

LONG_SENTENCE_WORDS = 28  # SG-14
LONG_PARAGRAPH_SENTENCES = 5  # SG-16
MIN_WORDS = 200  # smaller pages give unstable formula scores
MIN_SECTION_WORDS = 1000

# Out of scope per the style guide's Scope table, plus mkdocs exclude_docs.
OUT_OF_SCOPE = (
    "docs/adr/",
    "docs/reference/code/",
    "docs/reference/case_states/",
    "docs/reference/codebase/",
    "docs/reference/messages/_occasions/",
)

LIST_OR_HEADING = re.compile(r"^\s*(#+\s|[-*+]\s|\d+\.\s|>|\|)")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class PageScore:
    path: str
    words: int
    sentences: int
    long_sentences: int
    long_pct: float
    median_wps: float
    long_paragraphs: int
    fk_grade: float
    reading_ease: float
    poly_pct: float


def strip_markup(md: str) -> str:
    """Remove everything that is not prose; keep blank lines as block breaks."""
    md = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)  # front matter
    md = re.sub(r"```.*?```", "", md, flags=re.S)  # code and mermaid
    md = re.sub(r"\{%.*?%\}", "", md, flags=re.S)  # include-markdown
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"\$\$.*?\$\$", "", md, flags=re.S)  # display math
    md = re.sub(r"\\\[.*?\\\]", "", md, flags=re.S)  # bracketed display math
    md = re.sub(r"\\begin\{(\w+\*?)\}.*?\\end\{\1\}", "", md, flags=re.S)
    md = re.sub(r"\$[^$]+\$", "", md)  # inline math, may span lines
    md = re.sub(r"\(\s*\)", "", md)  # parentheses emptied by math removal
    md = re.sub(r"<[^>]+>", "", md)  # html tags
    md = re.sub(r"^\s*\|.*\|\s*$", "", md, flags=re.M)  # tables
    md = re.sub(r"^\s*\*\[[^\]]+\]:.*$", "", md, flags=re.M)  # abbreviations
    md = re.sub(r"^\s*\[[^\]]+\]:\s*\S+.*$", "", md, flags=re.M)  # link refs
    md = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", md)  # inline links
    md = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", md)  # reference links
    md = re.sub(r"`([^`]*)`", r"\1", md)
    md = re.sub(
        r"^\s*(!!!|\?\?\?\+?).*$", "", md, flags=re.M
    )  # admonition heads
    md = re.sub(r"\*{1,2}", "", md)
    # emphasis underscores sit at word edges; CASE_MANAGER keeps its own
    return re.sub(r"(?<!\w)_{1,2}|_{1,2}(?!\w)", "", md)


def blocks(md: str) -> list[list[str]]:
    """Split stripped markdown into blank-line-separated blocks of lines."""
    out: list[list[str]] = [[]]
    for line in md.splitlines():
        if line.strip():
            out[-1].append(line)
        elif out[-1]:
            out.append([])
    return [b for b in out if b]


def units(block: list[str]) -> list[str]:
    """Rejoin lines hard-wrapped mid-sentence, which breaks SG-38.

    A line starts a new unit when it is a list item or heading, or when the
    line before it ends a sentence; otherwise it continues that sentence.
    """
    out: list[str] = []
    for line in block:
        if (
            out
            and not LIST_OR_HEADING.match(line)
            and out[-1][-1] not in ".!?:"
        ):
            out[-1] += " " + line.strip()
        else:
            out.append(line.rstrip())
    return out


def sentences_of(line: str) -> list[str]:
    """One sentence per line (SG-38), split further where a line holds more."""
    line = re.sub(r"^\s*(#+|[-*+]|\d+\.|>)\s*", "", line).strip()
    if not line:
        return []
    if line[-1] not in ".!?:":
        line += "."  # headings and list items end without a stop
    return [s for s in SENTENCE_BREAK.split(line) if s.strip()]


def score(path: str, md: str) -> PageScore | None:
    bl = [units(b) for b in blocks(strip_markup(md))]
    sents = [s for b in bl for line in b for s in sentences_of(line)]
    if not sents:
        return None
    text = "\n".join(sents)
    words = textstat.lexicon_count(text)
    if words == 0:
        return None
    lengths = [textstat.lexicon_count(s) for s in sents]
    long_ = sum(n > LONG_SENTENCE_WORDS for n in lengths)
    long_paras = sum(
        1
        for b in bl
        if not LIST_OR_HEADING.match(b[0])
        and sum(len(sentences_of(line)) for line in b)
        > LONG_PARAGRAPH_SENTENCES
    )
    return PageScore(
        path=path,
        words=words,
        sentences=len(sents),
        long_sentences=long_,
        long_pct=round(100 * long_ / len(sents), 1),
        median_wps=statistics.median(lengths),
        long_paragraphs=long_paras,
        fk_grade=round(textstat.flesch_kincaid_grade(text), 1),
        reading_ease=round(textstat.flesch_reading_ease(text), 1),
        poly_pct=round(100 * textstat.polysyllabcount(text) / words, 1),
    )


def in_scope(path: str) -> bool:
    return path.startswith("docs/") and not path.startswith(OUT_OF_SCOPE)


def git_show(rev: str, path: str) -> str | None:
    r = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


def section_of(path: str) -> str:
    parts = path.split("/")[1:-1]
    return "/".join(parts[:2]) or "(docs root)"


def print_table(rows: list[PageScore], cum_total: int | None = None) -> None:
    if not rows:
        print("None.")
        return
    head = "| Page | Words | >28w | >28w % | Median w/s | Long ¶ | FK |"
    print(head + (" Cum % |" if cum_total else ""))
    print("|---" * (head.count("|") - 1 + bool(cum_total)) + "|")
    cum = 0
    for r in rows:
        cum += r.long_sentences
        line = (
            f"| `{r.path[5:]}` | {r.words} | {r.long_sentences} | {r.long_pct} "
            f"| {r.median_wps:g} | {r.long_paragraphs} | {r.fk_grade} |"
        )
        if cum_total:
            line += f" {100 * cum // cum_total} |"
        print(line)


def report(pages: list[PageScore], top: int) -> None:
    ranked = [p for p in pages if p.words >= MIN_WORDS]
    total_long = sum(p.long_sentences for p in pages)
    total_sents = sum(p.sentences for p in pages)
    print("# Readability audit\n")
    print(
        f"In-scope pages: {len(pages)} ({len(ranked)} with ≥{MIN_WORDS} words, "
        f"ranked). Words: {sum(p.words for p in pages)}. Sentences: "
        f"{total_sents}. Over {LONG_SENTENCE_WORDS} words (SG-14): {total_long} "
        f"({100 * total_long / max(total_sents, 1):.1f}%). Paragraphs over "
        f"{LONG_PARAGRAPH_SENTENCES} sentences (SG-16): "
        f"{sum(p.long_paragraphs for p in pages)}."
    )
    clean = sum(p.long_sentences == 0 for p in pages)
    print(f"Pages with no sentence over the limit: {clean} of {len(pages)}.\n")

    by_long = sorted(ranked, key=lambda p: (-p.long_sentences, -p.long_pct))
    print(f"## Pages with the most over-limit sentences (top {top})\n")
    print_table(by_long[:top], cum_total=total_long)
    print()
    for n in (n for n in (10, 20, 40) if n < len(by_long)):
        share = sum(p.long_sentences for p in by_long[:n])
        print(f"- Top {n} pages hold {100 * share / max(total_long, 1):.0f}%")

    print("\n## Sections\n")
    groups: dict[str, list[PageScore]] = defaultdict(list)
    for p in pages:
        groups[section_of(p.path)].append(p)
    print("| Section | Pages | Words | >28w | >28w % | FK (word-weighted) |")
    print("|---|---|---|---|---|---|")
    stats = []
    for sec, ps in groups.items():
        w = sum(p.words for p in ps)
        if w < MIN_SECTION_WORDS:
            continue
        s = sum(p.sentences for p in ps)
        n = sum(p.long_sentences for p in ps)
        fk = sum(p.fk_grade * p.words for p in ps) / w
        stats.append((n, sec, len(ps), w, 100 * n / s, fk))
    for n, sec, count, w, pct, fk in sorted(stats, reverse=True):
        print(f"| `{sec}` | {count} | {w} | {n} | {pct:.1f} | {fk:.1f} |")

    print("\n## High grade with short sentences (word choice, not length)\n")
    wordy = [p for p in ranked if p.fk_grade >= 11 and p.median_wps <= 12]
    print_table(sorted(wordy, key=lambda p: -p.fk_grade)[:10])

    print("\n## Best pages\n")
    shown = {p.path for p in by_long[:top]}
    best = sorted(
        (p for p in ranked if p.path not in shown),
        key=lambda p: (p.long_pct, p.fk_grade),
    )[:10]
    print_table(best)


def compare(rev: str, pages: list[PageScore]) -> None:
    print(f"# Readability change since `{rev}`\n")
    print("| Page | >28w | Median w/s | Long ¶ | FK | Words |")
    print("|---|---|---|---|---|---|")
    before_all, after_all = [], []
    for after in pages:
        old = git_show(rev, after.path)
        before = score(after.path, old) if old else None
        if before is None:
            print(
                f"| `{after.path[5:]}` (new) | {after.long_sentences} "
                f"| {after.median_wps:g} | {after.long_paragraphs} "
                f"| {after.fk_grade} | {after.words} |"
            )
            continue
        if before == after:
            continue  # unchanged since REV
        before_all.append(before)
        after_all.append(after)
        print(
            f"| `{after.path[5:]}` | {before.long_sentences} → {after.long_sentences} "
            f"| {before.median_wps:g} → {after.median_wps:g} "
            f"| {before.long_paragraphs} → {after.long_paragraphs} "
            f"| {before.fk_grade} → {after.fk_grade} | {before.words} → {after.words} |"
        )
    if before_all:
        b = sum(p.long_sentences for p in before_all)
        a = sum(p.long_sentences for p in after_all)
        print(f"\nOver-limit sentences on changed pages: {b} → {a}.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Rank docs/ pages by readability revision opportunity."
    )
    ap.add_argument(
        "paths",
        nargs="*",
        default=["docs"],
        help="files or directories to score (default: docs)",
    )
    ap.add_argument(
        "--top", type=int, default=30, help="rows in the page ranking"
    )
    ap.add_argument(
        "--match", help="keep only pages whose path matches this regex"
    )
    ap.add_argument(
        "--baseline",
        metavar="REV",
        help="compare each page against its version at REV",
    )
    ap.add_argument(
        "--csv", metavar="FILE", help="write every page score to FILE"
    )
    ap.add_argument(
        "--paths-out",
        metavar="FILE",
        help="write the ranked paths, one per line, to FILE",
    )
    args = ap.parse_args()

    files: list[pathlib.Path] = []
    for arg in args.paths:
        p = pathlib.Path(arg)
        files.extend(sorted(p.rglob("*.md")) if p.is_dir() else [p])
    match = re.compile(args.match) if args.match else None
    pages = [
        s
        for f in files
        if in_scope(f.as_posix())
        and (not match or match.search(f.as_posix()))
        and (s := score(f.as_posix(), f.read_text(errors="replace")))
    ]
    if not pages:
        print("error: no in-scope pages matched", file=sys.stderr)
        return 1

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(asdict(pages[0])))
            w.writeheader()
            w.writerows(asdict(p) for p in pages)
    if args.paths_out:
        ranked = sorted(
            (p for p in pages if p.words >= MIN_WORDS),
            key=lambda p: (-p.long_sentences, -p.long_pct),
        )
        pathlib.Path(args.paths_out).write_text(
            "".join(
                f"{p.path}\n" for p in ranked[: args.top] if p.long_sentences
            )
        )

    if args.baseline:
        compare(args.baseline, pages)
    else:
        report(pages, args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
