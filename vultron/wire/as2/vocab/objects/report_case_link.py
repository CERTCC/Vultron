#!/usr/bin/env python
"""Wire-layer vocabulary registration for :class:`VultronReportCaseLink`."""

from vultron.core.models.report_case_link import (  # noqa: F401
    VultronReportCaseLink,
)
from vultron.wire.as2.vocab.base.registry import VOCABULARY

VOCABULARY["ReportCaseLink"] = VultronReportCaseLink

__all__ = ["VultronReportCaseLink"]
