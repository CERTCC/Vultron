"""A throwaway checkout for the docs level-order tests (DF-11-002).

Shared by ``test_level_order.py``, ``test_concept_registry.py`` and
``test_level_baseline.py``: a glossary, a 400-level page introducing
``Case Ledger Entry``, and whatever pages a test adds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vultron.metadata.docs.level_order import check_level_order
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

GLOSSARY = """\
---
stakeholder_type: [project-contributor]
level: 300
---
# Glossary

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Case Ledger Entry** | A committed entry | Log item |
| **CASE_MANAGER** | The role that commits | — |
| **Coordinated Vulnerability Disclosure (CVD)** | The process | — |
| **V/v** | Vendor awareness | — |
"""


def leveled_page(
    level: int | None = 300,
    body: str = "# Page\n",
    *,
    audience: str = "[cvd-practitioner]",
    introduces: str | None = None,
) -> str:
    lines = [f"stakeholder_type: {audience}"]
    if level is not None:
        lines.append(f"level: {level}")
    if introduces is not None:
        lines.append(f"introduces: {introduces}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


LEDGER = leveled_page(400, "# Ledger\n", introduces="[Case Ledger Entry]")


def make_repo(tmp_path: Path, files: dict[str, str], nav=None) -> Path:
    """A checkout with a glossary, the 400-level ledger page, and *files*."""
    tree = {
        "reference/glossary.md": GLOSSARY,
        "topics/ledger.md": LEDGER,
        **files,
    }
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump({"nav": nav if nav is not None else sorted(tree)})
    )
    for rel, text in tree.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def assert_passes(root: Path) -> None:
    """The check raises nothing and tolerates nothing: *root* is compliant."""
    assert check_level_order(root, baseline={}).baselined == []


def failures(root: Path, baseline=None) -> tuple[MetadataLoadError, ...]:
    with pytest.raises(MetadataLoadErrors) as info:
        check_level_order(root, baseline={} if baseline is None else baseline)
    return info.value.failures


VIOLATING = leveled_page(300, "# A\n\nEach case ledger entry is signed.\n")
