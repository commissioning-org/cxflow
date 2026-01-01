"""
Report management for Apache Superset.

Provides automated reporting:
- Report scheduling
- Alert configuration
- Export and delivery
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import SupersetClient

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Report types."""
    REPORT = "Report"
    ALERT = "Alert"


class ReportFormat(Enum):
    """Report export formats."""
    PNG = "PNG"
    CSV = "CSV"
    TEXT = "TEXT"


class ReportState(Enum):
    """Report execution states."""
    WORKING = "working"
    SUCCESS = "success"
    ERROR = "error"
    NOOP = "noop"
    GRACE = "grace"


class RecipientType(Enum):
    """Report recipient types."""
    EMAIL = "Email"
    SLACK = "Slack"


@dataclass
class ReportRecipient:
    """Report recipient configuration."""
    id: Optional[int] = None
    type: RecipientType = RecipientType.EMAIL
    recipient_config_json: str = ""
    
    @classmethod
    def email(cls, email: str) -> ReportRecipient:
        """Create email recipient."""
        import json
        return cls(
            type=RecipientType.EMAIL,
            recipient_config_json=json.dumps({"target": email}),
        )
    
    @classmethod
    def slack(cls, channel: str) -> ReportRecipient:
        """Create Slack recipient."""
        import json
        return cls(
            type=RecipientType.SLACK,
            recipient_config_json=json.dumps({"target": channel}),
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "recipient_config_json": self.recipient_config_json,
        }
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> ReportRecipient:
        return cls(
            id=data.get("id"),
            type=RecipientType(data.get("type", "Email")),
            recipient_config_json=data.get("recipient_config_json", "{}"),
        )


@dataclass
class ReportSchedule:
    """Report schedule configuration."""
    id: int
    name: str
    type: ReportType = ReportType.REPORT
    crontab: str = "0 9 * * *"  # 9 AM daily
    
    # Target (chart or dashboard)
    dashboard_id: Optional[int] = None
    chart_id: Optional[int] = None
    
    # Alert settings
    database_id: Optional[int] = None
    sql: Optional[str] = None
    validator_type: Optional[str] = None  # "operator" or "not null"
    validator_config_json: Optional[str] = None
    
    # Report settings
    report_format: ReportFormat = ReportFormat.PNG
    description: Optional[str] = None
    context_markdown: Optional[str] = None
    
    # Recipients
    recipients: List[ReportRecipient] = field(default_factory=list)
    
    # State
    active: bool = True
    last_state: Optional[ReportState] = None
    last_eval_dttm: Optional[datetime] = None
    last_value: Optional[float] = None
    last_value_row_json: Optional[str] = None
    
    # Settings
    log_retention: int = 90
    grace_period: int = 60 * 60 * 4  # 4 hours
    working_timeout: int = 60 * 60  # 1 hour
    
    # Owner
    owners: List[int] = field(default_factory=list)
    created_by: Optional[str] = None
    changed_by: Optional[str] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> ReportSchedule:
        """Create from API response."""
        result = data.get("result", data)
        
        recipients = [
            ReportRecipient.from_api(r)
            for r in result.get("recipients", [])
        ]
        
        last_state = None
        if result.get("last_state"):
            try:
                last_state = ReportState(result.get("last_state"))
            except ValueError:
                pass
        
        return cls(
            id=result.get("id", 0),
            name=result.get("name", ""),
            type=ReportType(result.get("type", "Report")),
            crontab=result.get("crontab", ""),
            dashboard_id=result.get("dashboard_id"),
            chart_id=result.get("chart_id"),
            database_id=result.get("database_id"),
            sql=result.get("sql"),
            validator_type=result.get("validator_type"),
            validator_config_json=result.get("validator_config_json"),
            report_format=ReportFormat(result.get("report_format", "PNG")),
            description=result.get("description"),
            context_markdown=result.get("context_markdown"),
            recipients=recipients,
            active=result.get("active", True),
            last_state=last_state,
            log_retention=result.get("log_retention", 90),
            grace_period=result.get("grace_period", 60 * 60 * 4),
            working_timeout=result.get("working_timeout", 60 * 60),
            owners=[o.get("id") for o in result.get("owners", []) if isinstance(o, dict)],
        )
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to API payload."""
        payload = {
            "name": self.name,
            "type": self.type.value,
            "crontab": self.crontab,
            "active": self.active,
            "report_format": self.report_format.value,
            "description": self.description,
            "context_markdown": self.context_markdown,
            "recipients": [r.to_api_payload() for r in self.recipients],
            "log_retention": self.log_retention,
            "grace_period": self.grace_period,
            "working_timeout": self.working_timeout,
            "owners": self.owners,
        }
        
        if self.dashboard_id:
            payload["dashboard"] = self.dashboard_id
        if self.chart_id:
            payload["chart"] = self.chart_id
        if self.database_id:
            payload["database"] = self.database_id
        if self.sql:
            payload["sql"] = self.sql
        if self.validator_type:
            payload["validator_type"] = self.validator_type
        if self.validator_config_json:
            payload["validator_config_json"] = self.validator_config_json
        
        return payload


@dataclass
class ReportLog:
    """Report execution log entry."""
    id: int
    report_schedule_id: int
    state: ReportState
    start_dttm: Optional[datetime] = None
    end_dttm: Optional[datetime] = None
    value: Optional[float] = None
    error_message: Optional[str] = None
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> ReportLog:
        return cls(
            id=data.get("id", 0),
            report_schedule_id=data.get("report_schedule_id", 0),
            state=ReportState(data.get("state", "noop")),
            value=data.get("value"),
            error_message=data.get("error_message"),
        )


class ReportManager:
    """
    High-level report management.
    
    Usage:
        manager = ReportManager(client)
        
        # List reports
        reports = manager.list_reports()
        
        # Create dashboard report
        report = manager.create_dashboard_report(
            name="Weekly Sales Report",
            dashboard_id=1,
            crontab="0 9 * * 1",  # Monday 9 AM
            recipients=[
                ReportRecipient.email("team@example.com"),
            ],
        )
        
        # Create alert
        alert = manager.create_alert(
            name="High Error Rate Alert",
            database_id=1,
            sql="SELECT COUNT(*) FROM errors WHERE timestamp > NOW() - INTERVAL '1 hour'",
            threshold=100,
            recipients=[
                ReportRecipient.slack("#alerts"),
            ],
        )
    """
    
    def __init__(self, client: SupersetClient):
        self.client = client
    
    def list_reports(
        self,
        page: int = 0,
        page_size: int = 100,
        report_type: Optional[ReportType] = None,
        active_only: bool = False,
    ) -> List[ReportSchedule]:
        """List all reports and alerts."""
        filters = []
        
        if report_type:
            filters.append({"col": "type", "opr": "eq", "value": report_type.value})
        
        if active_only:
            filters.append({"col": "active", "opr": "eq", "value": True})
        
        result = self.client.get_reports(
            page=page,
            page_size=page_size,
            filters=filters,
        )
        
        reports = []
        for item in result.get("result", []):
            reports.append(ReportSchedule.from_api({"result": item}))
        
        return reports
    
    def get_report(self, report_id: int) -> ReportSchedule:
        """Get report by ID."""
        result = self.client.get_report(report_id)
        return ReportSchedule.from_api(result)
    
    def create_dashboard_report(
        self,
        name: str,
        dashboard_id: int,
        crontab: str,
        recipients: List[ReportRecipient],
        report_format: ReportFormat = ReportFormat.PNG,
        description: Optional[str] = None,
        owners: Optional[List[int]] = None,
    ) -> ReportSchedule:
        """Create a dashboard report."""
        report_data = {
            "name": name,
            "type": ReportType.REPORT.value,
            "dashboard": dashboard_id,
            "crontab": crontab,
            "report_format": report_format.value,
            "description": description,
            "recipients": [r.to_api_payload() for r in recipients],
            "owners": owners or [],
            "active": True,
        }
        
        result = self.client.create_report(report_data)
        return self.get_report(result.get("id"))
    
    def create_chart_report(
        self,
        name: str,
        chart_id: int,
        crontab: str,
        recipients: List[ReportRecipient],
        report_format: ReportFormat = ReportFormat.PNG,
        description: Optional[str] = None,
        owners: Optional[List[int]] = None,
    ) -> ReportSchedule:
        """Create a chart report."""
        report_data = {
            "name": name,
            "type": ReportType.REPORT.value,
            "chart": chart_id,
            "crontab": crontab,
            "report_format": report_format.value,
            "description": description,
            "recipients": [r.to_api_payload() for r in recipients],
            "owners": owners or [],
            "active": True,
        }
        
        result = self.client.create_report(report_data)
        return self.get_report(result.get("id"))
    
    def create_alert(
        self,
        name: str,
        database_id: int,
        sql: str,
        threshold: float,
        crontab: str,
        recipients: List[ReportRecipient],
        comparison_operator: str = ">",  # ">", "<", ">=", "<=", "==", "!="
        description: Optional[str] = None,
        dashboard_id: Optional[int] = None,
        chart_id: Optional[int] = None,
        owners: Optional[List[int]] = None,
    ) -> ReportSchedule:
        """Create an alert."""
        import json
        
        validator_config = {
            "op": comparison_operator,
            "threshold": threshold,
        }
        
        report_data = {
            "name": name,
            "type": ReportType.ALERT.value,
            "database": database_id,
            "sql": sql,
            "validator_type": "operator",
            "validator_config_json": json.dumps(validator_config),
            "crontab": crontab,
            "description": description,
            "recipients": [r.to_api_payload() for r in recipients],
            "owners": owners or [],
            "active": True,
        }
        
        if dashboard_id:
            report_data["dashboard"] = dashboard_id
        if chart_id:
            report_data["chart"] = chart_id
        
        result = self.client.create_report(report_data)
        return self.get_report(result.get("id"))
    
    def create_null_check_alert(
        self,
        name: str,
        database_id: int,
        sql: str,
        crontab: str,
        recipients: List[ReportRecipient],
        description: Optional[str] = None,
        owners: Optional[List[int]] = None,
    ) -> ReportSchedule:
        """Create an alert that triggers when SQL returns non-null results."""
        report_data = {
            "name": name,
            "type": ReportType.ALERT.value,
            "database": database_id,
            "sql": sql,
            "validator_type": "not null",
            "crontab": crontab,
            "description": description,
            "recipients": [r.to_api_payload() for r in recipients],
            "owners": owners or [],
            "active": True,
        }
        
        result = self.client.create_report(report_data)
        return self.get_report(result.get("id"))
    
    def update_report(
        self,
        report_id: int,
        **kwargs,
    ) -> ReportSchedule:
        """Update an existing report."""
        self.client.update_report(report_id, kwargs)
        return self.get_report(report_id)
    
    def delete_report(self, report_id: int) -> bool:
        """Delete a report."""
        try:
            self.client.delete_report(report_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete report {report_id}: {e}")
            return False
    
    def enable_report(self, report_id: int) -> ReportSchedule:
        """Enable a report."""
        return self.update_report(report_id, active=True)
    
    def disable_report(self, report_id: int) -> ReportSchedule:
        """Disable a report."""
        return self.update_report(report_id, active=False)
    
    def get_report_logs(
        self,
        report_id: int,
        page: int = 0,
        page_size: int = 100,
    ) -> List[ReportLog]:
        """Get execution logs for a report."""
        result = self.client.get_report_logs(report_id, page=page, page_size=page_size)
        
        logs = []
        for item in result.get("result", []):
            logs.append(ReportLog.from_api(item))
        
        return logs
    
    def trigger_report(self, report_id: int) -> bool:
        """Manually trigger a report execution."""
        try:
            self.client.trigger_report(report_id)
            return True
        except Exception as e:
            logger.error(f"Failed to trigger report {report_id}: {e}")
            return False


# Cron schedule helpers

class CronSchedule:
    """Helper class for common cron schedules."""
    
    EVERY_MINUTE = "* * * * *"
    EVERY_5_MINUTES = "*/5 * * * *"
    EVERY_15_MINUTES = "*/15 * * * *"
    EVERY_30_MINUTES = "*/30 * * * *"
    HOURLY = "0 * * * *"
    DAILY_9AM = "0 9 * * *"
    DAILY_MIDNIGHT = "0 0 * * *"
    WEEKLY_MONDAY_9AM = "0 9 * * 1"
    WEEKLY_FRIDAY_5PM = "0 17 * * 5"
    MONTHLY_FIRST = "0 9 1 * *"
    MONTHLY_LAST_WEEKDAY = "0 9 L * 1-5"  # Not supported by all cron implementations
    
    @staticmethod
    def daily_at(hour: int, minute: int = 0) -> str:
        """Generate daily schedule at specific time."""
        return f"{minute} {hour} * * *"
    
    @staticmethod
    def weekly_on(day: int, hour: int = 9, minute: int = 0) -> str:
        """Generate weekly schedule (0=Sunday, 1=Monday, etc.)."""
        return f"{minute} {hour} * * {day}"
    
    @staticmethod
    def monthly_on(day: int, hour: int = 9, minute: int = 0) -> str:
        """Generate monthly schedule on specific day."""
        return f"{minute} {hour} {day} * *"
