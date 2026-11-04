#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Architecture ratchet: every guard under ``vultron/`` runs in production.

A guard whose production call site never reaches it passes its own unit tests
and enforces nothing.  That shape is worse than missing coverage, because the
tests *suppress* the signal: a coverage report shows a gap, while a green
direct-call test reports the requirement as covered and nothing anywhere
reports a problem (ISSUE-3156).

Two confirmed instances led to this ratchet:

* ``_validate_entry_timestamps`` implemented five CLP-14 and CLP-15
  requirements.  ``_validate_canonical_entry`` ran it only under
  ``if case_published is not None:``, and ``CreateLogEntryNode.update()`` —
  the sole production caller — never passed ``case_published``.  The guard
  never executed in production for its whole life, while
  ``test_canonical_entry.py`` held fourteen passing tests for it, every one
  calling the private validator directly with hand-supplied arguments
  (ISSUE-2824).
* ``json2md`` rendered tracebacks for every real input while its test stayed
  green, because the fixture subclassed a base class without the attributes
  both ``hasattr`` guards tested (ISSUE-2904).

Two rules, one ratchet, because a caller alone is not enough — the first
witness *had* a caller:

1. **A private guard has a production caller.**  Every undecorated,
   single-underscore, non-dunder definition under ``vultron/`` that raises in
   its own scope is referenced somewhere else under ``vultron/``.  A guard
   nothing names is dead on arrival.
2. **The parameter that opens a guard is supplied.**  Where a parameter
   defaulting to ``None`` gates a refusal — the branch taken when the caller
   supplies it raises, or delegates to a guard that raises — some call site
   under ``vultron/`` passes that parameter.  A gate nothing opens is a
   check that never runs, which is exactly what the first witness was.

Both subject sets are keyed on the **act** — refusing, and gating a refusal —
not on a name for validators, so renaming a guard keeps it in the set
(``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act").  Each
set comes in two shapes, module-level functions and methods, and each shape
is asserted separately: a bare "the subject set is non-empty" guard cannot
tell one shape from two, so a refactor that emptied one would pass it
silently (#5535).

**What this ratchet does not cover.**  It reads production code only, so it
cannot tell a guard that fires in production from one whose *tests* all reach
it by direct call.  That half is a test-authoring rule, not a structural one:
``test/core/behaviors/sync/nodes/test_chain_timestamp_guard.py`` is the shape
such a test takes, driving the guard through ``CreateLogEntryNode`` rather
than calling the private validator.  A check for it was measured and
dropped: no spec-marked test in the repo calls any of these guards directly
today, so the arm had no subjects and could only ever pass.

Resolution lives in ``_guard_reachability.py``; that module's docstring lists
the four over-approximations it makes, each of which can only let a
violation through, never invent one.  Its judgements are driven over inline
source by the detector tests below, so a detector change cannot pass its own
tests while reading the package differently.

Corpus: TB-13-001, TB-13-002, TB-13-003 (``specs/testability.yaml``).
Ratchet discipline: ARCH-18-001, ARCH-18-002 (``specs/architecture.yaml``),
TB-10-002, TB-10-003.
"""

from test.architecture import _guard_reachability as _reach

# ---------------------------------------------------------------------------
# Known guards with no production reference (empty: every private guard under
# vultron/ is reached from production code).
#
# Each entry would be a guard that enforces a rule nothing can ever break,
# because nothing calls it.  Remove an entry in the same commit that wires
# the guard up or deletes it (ARCH-18-002, TB-10-003); a new entry needs its
# owning issue named beside it.
# ---------------------------------------------------------------------------
KNOWN_UNREACHED_GUARDS: frozenset[str] = frozenset()

# ---------------------------------------------------------------------------
# Known gating parameters no call site supplies (empty: every gated refusal
# under vultron/ is opened by some caller).
#
# Each entry would be a check that cannot run, the shape that left the
# CLP-14/CLP-15 claimed-timestamp invariants unenforced for the whole life of
# the guard that implements them (ISSUE-2824).  Remove an entry in the same
# commit that supplies the argument or drops the gate (ARCH-18-002,
# TB-10-003).
# ---------------------------------------------------------------------------
KNOWN_UNSUPPLIED_GATES: frozenset[str] = frozenset()


def _ratchet_message(
    actual: frozenset[str], known: frozenset[str], *, rule: str
) -> str:
    """The two-sided diff an equality failure reports (ARCH-18-001)."""
    lines: list[str] = []
    if new := actual - known:
        lines.append(f"NEW violations ({rule}):")
        lines.extend(f"  + {site}" for site in sorted(new))
    if resolved := known - actual:
        lines.append(
            "RESOLVED violations (remove these entries in this commit —"
            " ARCH-18-002, TB-10-003):"
        )
        lines.extend(f"  - {site}" for site in sorted(resolved))
    return "\n\n" + "\n".join(lines)


def test_the_diff_names_a_new_violation_and_the_rule_it_breaks() -> None:
    """A site the baseline does not hold is reported as added."""
    message = _ratchet_message(
        frozenset({"a.py:1 _x()"}), frozenset(), rule="the rule"
    )
    assert "NEW violations (the rule):" in message
    assert "+ a.py:1 _x()" in message
    assert "RESOLVED" not in message


def test_the_diff_names_a_resolved_violation_and_what_to_do() -> None:
    """A baseline entry the scan no longer finds must be removed.

    Both baselines are empty, so only this test reaches the branch that
    says so — the failure message a future entry's removal would print.
    """
    message = _ratchet_message(
        frozenset(), frozenset({"a.py:1 _x()"}), rule="the rule"
    )
    assert "RESOLVED violations" in message
    assert "ARCH-18-002, TB-10-003" in message
    assert "- a.py:1 _x()" in message
    assert "NEW violations" not in message


# ---------------------------------------------------------------------------
# The two arms
# ---------------------------------------------------------------------------
def test_every_private_guard_has_a_production_caller() -> None:
    """A private guard nothing under ``vultron/`` names is dead code.

    See the module docstring for the rule and the witnesses.
    """
    actual = _reach.findings().unreached
    assert actual == KNOWN_UNREACHED_GUARDS, _ratchet_message(
        actual,
        KNOWN_UNREACHED_GUARDS,
        rule="a private guard that raises must be called, or referenced for"
        " something else to call, somewhere under vultron/ — otherwise it"
        " enforces nothing and no test of it can fail for a real reason",
    )


def test_every_gated_refusal_is_opened_by_some_caller() -> None:
    """A gate no caller opens is a check that never runs.

    This is the arm that catches the first witness: the guard had a caller,
    and the caller never passed the argument the check needed (ISSUE-2824).
    """
    actual = _reach.findings().unsupplied
    assert actual == KNOWN_UNSUPPLIED_GATES, _ratchet_message(
        actual,
        KNOWN_UNSUPPLIED_GATES,
        rule="a parameter whose presence opens a refusal must be supplied at"
        " some call site under vultron/ — otherwise the check behind it"
        " cannot run, however many tests call the guard directly",
    )


# ---------------------------------------------------------------------------
# Non-empty subject guards, one per shape.
#
# An empty subject set makes both arms above pass vacuously, and a single
# "the set is non-empty" assertion cannot tell one shape from two: a
# migration that left only methods, or only functions, would keep it green
# while the ratchet silently stopped covering the other (#5535).  Both shapes
# of both subject sets are live, so each is asserted found.
# ---------------------------------------------------------------------------
def test_the_scan_finds_module_level_private_guards() -> None:
    """The module-level shape of arm A's subject set is populated."""
    assert [
        guard for guard in _reach.findings().guards if not guard.in_class
    ], (
        "no module-level private guard found under vultron/ — the scan has"
        " stopped seeing a shape it used to cover, so arm A now passes"
        " vacuously for it"
    )


def test_the_scan_finds_private_guard_methods() -> None:
    """The method shape of arm A's subject set is populated."""
    assert [guard for guard in _reach.findings().guards if guard.in_class], (
        "no private guard method found under vultron/ — a guard reached as"
        " self._check(...) is the second shape arm A covers, and the scan"
        " no longer finds it"
    )


def test_the_scan_finds_module_level_parameter_gates() -> None:
    """The module-level shape of arm B's subject set is populated."""
    assert [gate for gate in _reach.findings().gates if not gate.in_class], (
        "no module-level parameter gate found under vultron/ — arm B now"
        " passes vacuously for that shape"
    )


def test_the_scan_finds_parameter_gates_in_methods() -> None:
    """The method shape of arm B's subject set is populated."""
    assert [gate for gate in _reach.findings().gates if gate.in_class], (
        "no parameter gate in a method found under vultron/ — arm B now"
        " passes vacuously for that shape"
    )


# ---------------------------------------------------------------------------
# Synthetic detector tests — the witness, reconstructed
# ---------------------------------------------------------------------------
#: ``_validate_canonical_entry`` as it stood before ISSUE-2824, reduced to the
#: three parts that mattered: a guard that raises, a caller that gates the
#: delegation on an optional argument, and the one production call site that
#: never passed it.
_WITNESS = """
def _validate_entry_timestamps(*, case_published, skew_tolerance):
    if case_published is not None and 1 < 2:
        raise VultronCanonicalEntryError("CLP-14-013 - entry predates case")


def _validate_canonical_entry(*, case_id, case_published=None):
    if not case_id:
        raise VultronCanonicalEntryError("CLP-07-011 - case_id is required")
    if case_published is not None:
        _validate_entry_timestamps(
            case_published=case_published, skew_tolerance=1
        )


class CreateLogEntryNode:
    def update(self):
        _validate_canonical_entry(case_id="case-1")
"""


def test_detector_catches_the_witness_gate() -> None:
    """The pre-fix ISSUE-2824 shape is reported, with its parameter named."""
    findings = _reach.findings_in_source(_WITNESS)
    assert findings.unsupplied == {
        "inline.py:7 _validate_canonical_entry() [case_published]"
    }


def test_detector_clears_the_witness_once_the_caller_supplies_it() -> None:
    """The fix is a caller that passes the argument, and nothing else."""
    fixed = _WITNESS.replace(
        '_validate_canonical_entry(case_id="case-1")',
        '_validate_canonical_entry(case_id="case-1", case_published=NOW)',
    )
    assert _reach.findings_in_source(fixed).unsupplied == frozenset()
    assert [
        gate.parameter for gate in _reach.findings_in_source(fixed).gates
    ] == ["case_published"], (
        "the gate must still be a subject once it is opened, not drop out"
    )


def test_detector_counts_a_positional_argument_as_supplying_the_gate() -> None:
    """A gate on a positional parameter is opened by a positional call."""
    source = """
def _check(value, limit=None):
    if limit is not None:
        raise ValueError("over")


def run():
    _check(1, 2)
"""
    assert _reach.findings_in_source(source).unsupplied == frozenset()


def test_detector_does_not_count_a_shorter_positional_call() -> None:
    """A call that stops before the gated parameter does not open it."""
    source = """
def _check(value, limit=None):
    if limit is not None:
        raise ValueError("over")


def run():
    _check(1)
"""
    assert _reach.findings_in_source(source).unsupplied == {
        "inline.py:2 _check() [limit]"
    }


def test_detector_counts_a_kwargs_splat_as_supplying_the_gate() -> None:
    """A splat may carry anything, so it is given the benefit of the doubt."""
    source = """
def _check(*, limit=None):
    if limit is not None:
        raise ValueError("over")


def run(**options):
    _check(**options)
"""
    assert _reach.findings_in_source(source).unsupplied == frozenset()


def test_detector_ignores_the_recursive_call_inside_the_definition() -> None:
    """A call on the guard's own ``def`` line cannot supply its parameter.

    The call-site filter drops sites at the definition's own line so a
    default spelled as a call in the signature is not mistaken for a caller.
    """
    source = """
def _check(*, limit=None, inner=_check(limit=1)):
    if limit is not None:
        raise ValueError("over")


def run():
    _check()
"""
    assert _reach.findings_in_source(source).unsupplied == {
        "inline.py:2 _check() [limit]"
    }


# ---------------------------------------------------------------------------
# Synthetic detector tests — what is not a gate
# ---------------------------------------------------------------------------
def test_detector_does_not_treat_an_absent_value_default_as_a_gate() -> None:
    """``x if p is None else y`` is an injection seam, not a gate.

    The branch that refuses runs when the caller *omits* the parameter, so
    requiring a caller to supply it would be backwards.  Read without
    polarity, this reported the scenario exporter's ``specs=None`` seam as a
    dead check.
    """
    source = """
def discover():
    raise ValueError("DEMOCI-11-008 - no scenarios")


def build_payload(specs=None):
    resolved = discover() if specs is None else tuple(specs)
    return resolved


def main():
    build_payload()
"""
    assert _reach.findings_in_source(source).gates == ()


def test_detector_does_not_treat_a_required_parameter_as_a_gate() -> None:
    """A parameter with no ``None`` default cannot be omitted."""
    source = """
def _check(*, limit):
    if limit is not None:
        raise ValueError("over")


def run():
    _check(limit=1)
"""
    assert _reach.findings_in_source(source).gates == ()


def test_detector_does_not_treat_an_unguarded_branch_as_a_gate() -> None:
    """A branch that refuses nothing is not a check, so it is not a gate."""
    source = """
def _check(*, label=None):
    if label is not None:
        print(label)
    raise ValueError("always")


def run():
    _check()
"""
    assert _reach.findings_in_source(source).gates == ()


def test_detector_skips_a_dunder_whose_gate_has_no_named_call_site() -> None:
    """``__init__``'s arguments are passed at ``ClassName(...)``.

    A gate in a dunder is invisible to the supply check rather than
    unsupplied, so flagging it would report a violation that cannot be
    fixed.
    """
    source = """
class Monitor:
    def __init__(self, *, threshold=None):
        if threshold is not None:
            raise ValueError("unsupported")


def run():
    Monitor()
"""
    assert _reach.findings_in_source(source).gates == ()


# ---------------------------------------------------------------------------
# Synthetic detector tests — what is not a private guard
# ---------------------------------------------------------------------------
def test_detector_reports_a_private_guard_nothing_names() -> None:
    """The arm-A violation shape, with the defining site named."""
    source = """
def _check_nonempty_list(value, field_name):
    if value is not None and len(value) == 0:
        raise ValueError(f"{field_name} must be non-empty if present")
    return value
"""
    assert _reach.findings_in_source(source).unreached == {
        "inline.py:2 _check_nonempty_list()"
    }


def test_detector_clears_a_private_guard_a_caller_names() -> None:
    """One reference anywhere in production clears arm A."""
    source = """
def _check_nonempty_list(value, field_name):
    if value is not None and len(value) == 0:
        raise ValueError(f"{field_name} must be non-empty if present")
    return value


def validate(value):
    return _check_nonempty_list(value, "scope")
"""
    assert _reach.findings_in_source(source).unreached == frozenset()


def test_detector_does_not_count_a_mention_in_prose_as_a_reference() -> None:
    """A guard only talked about in a docstring or comment is still dead.

    The reference pass walks the tree, where a docstring is a string
    constant and a comment is nothing at all, so neither can stand in for a
    call.  A text scan would have read both as a caller.
    """
    source = '''
def _check_nonempty_list(value):
    if not value:
        raise ValueError("empty")


def validate(value):
    """Delegates to _check_nonempty_list."""
    # _check_nonempty_list(value)
    return value
'''
    assert _reach.findings_in_source(source).unreached == {
        "inline.py:2 _check_nonempty_list()"
    }


def test_detector_does_not_require_a_caller_for_a_decorated_validator() -> (
    None
):
    """A Pydantic validator is invoked by the model, not by a call site."""
    source = """
class Model(BaseModel):
    @field_validator("scope")
    @classmethod
    def _nonempty_if_present(cls, value):
        if value is not None and len(value) == 0:
            raise ValueError("must be non-empty if present")
        return value
"""
    assert _reach.findings_in_source(source).guards == ()


def test_detector_does_not_treat_a_public_function_as_a_private_guard() -> (
    None
):
    """Arm A is about privacy: only this package can call a private name."""
    source = """
def check_nonempty_list(value):
    if not value:
        raise ValueError("empty")
"""
    assert _reach.findings_in_source(source).guards == ()


def test_detector_does_not_treat_a_bare_reraise_as_a_refusal() -> None:
    """``raise`` with no exception re-raises; it refuses nothing of its own."""
    source = """
def _retry(operation):
    try:
        return operation()
    except OSError:
        raise
"""
    assert _reach.findings_in_source(source).guards == ()


def test_detector_does_not_attribute_a_nested_raise_to_its_enclosing_def() -> (
    None
):
    """A nested function's raise belongs to the nested scope.

    The enclosing definition builds a callable; whoever runs that callable
    is what reaches the refusal, so requiring a call site for the enclosing
    name would be the wrong question.
    """
    source = """
def _make_checker():
    def _inner(value):
        if not value:
            raise ValueError("empty")

    return _inner
"""
    assert [
        guard.name for guard in _reach.findings_in_source(source).guards
    ] == ["_inner"]


def test_detector_finds_a_guard_method_as_its_own_shape() -> None:
    """A private method that raises is a guard, marked as the method shape."""
    source = """
class Node:
    def _refuse_unless_manager(self, role):
        if role != "CASE_MANAGER":
            raise ValueError("CLP-09-001 - not the manager")

    def update(self):
        self._refuse_unless_manager("CASE_MANAGER")
"""
    findings = _reach.findings_in_source(source)
    assert [(guard.name, guard.in_class) for guard in findings.guards] == [
        ("_refuse_unless_manager", True)
    ]
    assert findings.unreached == frozenset()
