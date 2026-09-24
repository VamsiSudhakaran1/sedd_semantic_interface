"""Stable public JSON report contract for canonical interface comparisons."""

from sema_sedd.report.html import render_html_report
from sema_sedd.report.interface_html import render_interface_html
from sema_sedd.report.json_report import (
    REPORT_SCHEMA_VERSION,
    ReportDiagnostic,
    ReportSource,
    public_change_id,
    report_from_changes,
    report_json,
    report_schema,
)

__all__ = [
    "REPORT_SCHEMA_VERSION",
    "ReportDiagnostic",
    "ReportSource",
    "public_change_id",
    "report_from_changes",
    "report_json",
    "report_schema",
    "render_html_report",
    "render_interface_html",
]
