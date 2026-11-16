"""VINCE case reader — example stub.

Illustrates a connector plugin that implements one core port,
:class:`~vultron.core.ports.case_reader.CaseReader`, and nothing else: it
reads a VINCE (Vulnerability Information and Coordination Environment) case
and has no method that writes to VINCE (ADR-0191, ARCH-05-005).  The VINCE
case reader itself is built in #5963.

Read mappings (not yet implemented), by VINCE crosswalk row; the rows, their
caveats and their times are in ``docs/reference/vince_crosswalk.md``
(CRD-03-001):

- The case (``VINCE-CA``): the case itself becomes the
  ``VulnerabilityCase``, with an ``issue-tracking`` case reference to its
  VINCE URL (CRD-03-002); ``status`` = ``Inactive`` closes CERT/CC's RM.
- Participants (``VINCE-PA``): CERT/CC as Coordinator, Case Owner and Case
  Manager; each listed vendor as a Vendor; the report's contact as the
  Reporter, or a "withheld" placeholder when the contact is not shared.
- Report management (``VINCE-RM``): report submission and case creation set
  CERT/CC's RM; a vendor's listing and its per-vul ``status`` set that
  vendor's RM.
- Embargo (``VINCE-EM``): ``due_date`` becomes an active embargo, which each
  vendor at RM Received or later is inferred to accept.
- Case state (``VINCE-CS``): the report form's answers and the published
  vulnerability note set P, X and A.
- Content (``VINCE-CT``): vuls become vulnerability items, posts become case
  notes, and the report's fields become its content.

A VINCE value no row names comes back as an untranslated fact with the
unknown-value reason, never as a refused case (CRD-03-003, CRD-03-004).
"""

from vultron.core.models.case_reading import CaseReading, UnobservableFact

#: What the VINCE API never exposes, for any case (crosswalk § Unobservable).
VINCE_UNOBSERVABLE: tuple[UnobservableFact, ...] = (
    UnobservableFact(
        fact="Fix ready (F), fix deployed (D)",
        why="No VINCE field records them.",
    ),
    UnobservableFact(
        fact="A vendor was notified, a vendor viewed the case",
        why=(
            "VINCE records these in its case activity log, which only the"
            " coordinator web pages show."
        ),
    ),
    UnobservableFact(
        fact="CERT/CC's own RM steps after the case opens, other than closure",
        why="The case activity log holds them.",
    ),
    UnobservableFact(
        fact="A message, a task or a publish event in the case activity log",
        why="The case activity log holds them.",
    ),
    UnobservableFact(
        fact="When due_date was set or changed",
        why="VINCE stores only the case's last modified time.",
    ),
)


class VinceCaseReader:
    """Example VINCE case reader — not yet implemented (#5963)."""

    name = "vince"
    unobservable: tuple[UnobservableFact, ...] = VINCE_UNOBSERVABLE

    def read_case(self, case_id: str) -> CaseReading:
        """Read the VINCE case *case_id* (its ``vuid``)."""
        raise NotImplementedError("The VINCE case reader is built in #5963")
