from __future__ import annotations

import ast
from pathlib import Path

TEST_DIR = Path(__file__).parent


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _find_test_enum_classes() -> list[str]:
    offenders: list[str] = []
    for path in TEST_DIR.rglob("test*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.startswith("Test"):
                continue
            base_names = {_base_name(base) for base in node.bases}
            if {"Enum", "IntEnum"} & base_names:
                offenders.append(
                    str(path.relative_to(TEST_DIR.parent) / node.name)
                )
    return offenders


def test_helper_enums_do_not_look_like_pytest_test_classes() -> None:
    offenders = _find_test_enum_classes()
    if offenders:
        details = "\n".join(f"  {offender}" for offender in offenders)
        raise AssertionError(
            "Helper enums in test modules must not start with 'Test' because "
            "pytest will try to collect them as test classes and emit "
            f"PytestCollectionWarning:\n{details}"
        )
