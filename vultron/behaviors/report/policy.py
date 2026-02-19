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

"""
Report validation and prioritization policy implementations.

This module provides policy classes for:
1. Report validation: credibility and validity during the validation workflow.
2. Case prioritization: whether to engage (RM.ACCEPTED) or defer (RM.DEFERRED)
   a case after it has been created from a validated report.

Per specs/behavior-tree-integration.md, policies are pluggable and extensible.
Phase 1 provides stub always-accept policies as prototype simplifications.

Extension Points:
    - Subclass ValidationPolicy to implement custom decision logic
    - Subclass PrioritizationPolicy to implement SSVC or other priority logic
    - Policies can access report/case data, metadata, and context
    - Future: SSVC evaluation, machine learning models, human-in-the-loop
"""

import logging

from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport

logger = logging.getLogger(__name__)


class ValidationPolicy:
    """
    Abstract base class for report validation policies.

    Policies evaluate whether reports should be accepted or rejected during
    the validation workflow. Subclasses implement specific decision logic.

    This class defines the interface for pluggable policy implementations.
    """

    def is_credible(self, report: VulnerabilityReport) -> bool:
        """
        Evaluate whether report source is credible.

        Credibility checks assess whether the reporter is trustworthy and
        the report appears legitimate (not spam, not malicious).

        Args:
            report: VulnerabilityReport object to evaluate

        Returns:
            True if report source is credible, False otherwise

        Example:
            >>> policy = ValidationPolicy()
            >>> report = VulnerabilityReport(name="CVE-2024-001", content="...")
            >>> policy.is_credible(report)
            NotImplementedError
        """
        raise NotImplementedError("Subclasses must implement is_credible()")

    def is_valid(self, report: VulnerabilityReport) -> bool:
        """
        Evaluate whether report content is technically valid.

        Validity checks assess whether the report describes a real
        vulnerability with sufficient technical detail and accurate impact
        assessment.

        Args:
            report: VulnerabilityReport object to evaluate

        Returns:
            True if report content is valid, False otherwise

        Example:
            >>> policy = ValidationPolicy()
            >>> report = VulnerabilityReport(name="CVE-2024-001", content="...")
            >>> policy.is_valid(report)
            NotImplementedError
        """
        raise NotImplementedError("Subclasses must implement is_valid()")


class AlwaysAcceptPolicy(ValidationPolicy):
    """
    Default policy that accepts all reports (prototype simplification).

    This policy always returns True for both credibility and validity checks,
    effectively auto-accepting all submitted reports. Suitable for:
    - Prototype/demo environments
    - Internal testing
    - Trusted reporter scenarios
    - Development and exploration

    Phase 1 implementation: Simple always-accept logic with INFO-level logging.

    Future enhancements:
    - Configurable acceptance criteria
    - Metadata-based filtering
    - Integration with external validation services
    - Reputation-based scoring

    Example:
        >>> from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
        >>> policy = AlwaysAcceptPolicy()
        >>> report = VulnerabilityReport(
        ...     as_id="https://example.org/reports/CVE-2024-001",
        ...     name="CVE-2024-001",
        ...     content="Buffer overflow in parse_input()"
        ... )
        >>> policy.is_credible(report)
        True
        >>> policy.is_valid(report)
        True
    """

    def is_credible(self, report: VulnerabilityReport) -> bool:
        """
        Accept report as credible (always returns True).

        Logs acceptance decision at INFO level for observability.

        Args:
            report: VulnerabilityReport object to evaluate

        Returns:
            True (always accepts)
        """
        logger.info(
            f"Policy: Accepting report {report.as_id} as credible (AlwaysAcceptPolicy)"
        )
        return True

    def is_valid(self, report: VulnerabilityReport) -> bool:
        """
        Accept report as valid (always returns True).

        Logs acceptance decision at INFO level for observability.

        Args:
            report: VulnerabilityReport object to evaluate

        Returns:
            True (always accepts)
        """
        logger.info(
            f"Policy: Accepting report {report.as_id} as valid (AlwaysAcceptPolicy)"
        )
        return True


class PrioritizationPolicy:
    """
    Abstract base class for case prioritization policies.

    Policies evaluate whether a case should be engaged (RM.ACCEPTED) or
    deferred (RM.DEFERRED). Subclasses implement specific decision logic.

    Future: Plug in SSVC (Stakeholder-Specific Vulnerability Categorization)
    or other priority frameworks here. See specs/prototype-shortcuts.md
    PROTO-05-001 for the deferral policy on SSVC integration.
    """

    def should_engage(self, case: VulnerabilityCase) -> bool:
        """
        Evaluate whether the case should be engaged (accepted for active work).

        Args:
            case: VulnerabilityCase to evaluate

        Returns:
            True to engage (RM.ACCEPTED), False to defer (RM.DEFERRED)
        """
        raise NotImplementedError("Subclasses must implement should_engage()")


class AlwaysPrioritizePolicy(PrioritizationPolicy):
    """
    Default policy that always engages cases (prototype simplification).

    Always returns True, transitioning the actor to RM.ACCEPTED for every
    case. Suitable for prototype and trusted-coordinator scenarios.

    Future: Replace with SSVC-based evaluation (see PROTO-05-001).

    Example:
        >>> policy = AlwaysPrioritizePolicy()
        >>> case = VulnerabilityCase(name="Test Case")
        >>> policy.should_engage(case)
        True
    """

    def should_engage(self, case: VulnerabilityCase) -> bool:
        """
        Always engage the case (returns True).

        Args:
            case: VulnerabilityCase to evaluate (unused in this stub)

        Returns:
            True (always engages)
        """
        logger.info(
            f"Policy: Engaging case {case.as_id} (AlwaysPrioritizePolicy)"
        )
        return True
