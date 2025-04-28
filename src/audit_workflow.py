#!/usr/bin/env python3
"""
Shared workflow helpers for AWS cost audit executions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Optional, Protocol, Sequence, Tuple

try:
    from .cost_analyzer import BudgetAlert, CostOptimization, ServiceCost
except ImportError:
    from cost_analyzer import BudgetAlert, CostOptimization, ServiceCost

if TYPE_CHECKING:
    try:
        from .report_generator import ReportGenerator
        from .visualizer import CostVisualizer
    except ImportError:
        from report_generator import ReportGenerator
        from visualizer import CostVisualizer


DEFAULT_BUDGETS: Tuple[Dict[str, float], ...] = (
    {"name": "Production Monthly", "limit": 5000.00},
    {"name": "Development Monthly", "limit": 1000.00},
    {"name": "Testing Monthly", "limit": 500.00},
)

SERVICE_COST_CSV_FIELDS: Tuple[str, ...] = (
    "service_name",
    "cost",
    "currency",
    "usage_quantity",
    "unit",
)


class ReportSummaryBuilder(Protocol):
    """Minimal interface needed to build the audit summary."""

    def generate_executive_summary(
        self,
        total_cost: float,
        potential_savings: float,
        recommendations_count: int,
        anomalies_count: int,
        forecast: float,
    ) -> Dict[str, object]:
        """Build the executive summary payload."""


class CostAnalyzerProtocol(Protocol):
    """Required analyzer behavior for the shared workflow."""

    def get_service_costs(self, start_date: str, end_date: str) -> List[ServiceCost]:
        """Return service costs for the requested period."""

    def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
    ) -> Dict[str, object]:
        """Return raw grouped cost and usage data."""

    def identify_idle_resources(self) -> List[CostOptimization]:
        """Return idle resource optimization opportunities."""

    def identify_right_sizing_opportunities(self) -> List[CostOptimization]:
        """Return right-sizing opportunities."""

    def get_reserved_instance_recommendations(self) -> List[Dict[str, object]]:
        """Return reserved instance recommendations."""

    def get_savings_plans_recommendations(self) -> List[Dict[str, object]]:
        """Return savings plans recommendations."""

    def get_cost_anomaly_detection(self) -> List[Dict[str, object]]:
        """Return detected anomalies."""

    def simulate_budget_alerts(
        self, budgets: List[Dict[str, float]]
    ) -> List[BudgetAlert]:
        """Return budget alerts for the supplied budget definitions."""

    def get_cost_forecast(
        self, start_date: str, end_date: str, granularity: str = "MONTHLY"
    ) -> Dict[str, object]:
        """Return the cost forecast payload."""


@dataclass(frozen=True)
class AuditArtifacts:
    """Paths to generated reports and visual assets."""

    html_report: str
    json_report: str
    markdown_report: str
    csv_report: str
    chart_files: List[str]

    def to_dict(self) -> Dict[str, object]:
        """Return artifact paths using the structure expected by the CLI."""
        return {
            "reports": {
                "html": self.html_report,
                "json": self.json_report,
                "markdown": self.markdown_report,
                "csv": self.csv_report,
            },
            "charts": self.chart_files,
        }


@dataclass(frozen=True)
class AuditResults:
    """Structured data collected during an audit run."""

    start_date: str
    end_date: str
    service_costs: List[ServiceCost]
    daily_costs: List[Dict[str, object]]
    idle_resources: List[CostOptimization]
    right_sizing_opportunities: List[CostOptimization]
    ri_recommendations: List[Dict[str, object]]
    savings_plans_recommendations: List[Dict[str, object]]
    anomalies: List[Dict[str, object]]
    budget_alerts: List[BudgetAlert]
    forecast: float

    @property
    def total_cost(self) -> float:
        """Return the total monthly spend across all services."""
        return sum(service.cost for service in self.service_costs)

    @property
    def optimizations(self) -> List[CostOptimization]:
        """Return all optimization recommendations in a single list."""
        return self.idle_resources + self.right_sizing_opportunities

    @property
    def potential_savings(self) -> float:
        """Return total estimated monthly savings."""
        return sum(item.potential_savings for item in self.optimizations)

    @property
    def service_costs_dict(self) -> List[Dict[str, object]]:
        """Serialize service costs for reports and charts."""
        return [service.to_dict() for service in self.service_costs]

    @property
    def optimizations_dict(self) -> List[Dict[str, object]]:
        """Serialize optimization recommendations for reports and charts."""
        return [item.to_dict() for item in self.optimizations]

    @property
    def budget_alerts_dict(self) -> List[Dict[str, object]]:
        """Serialize budget alerts for reports and charts."""
        return [alert.to_dict() for alert in self.budget_alerts]

    def build_summary(
        self, report_generator: ReportSummaryBuilder
    ) -> Dict[str, object]:
        """Build the executive summary using the report generator rules."""
        return report_generator.generate_executive_summary(
            total_cost=self.total_cost,
            potential_savings=self.potential_savings,
            recommendations_count=len(self.optimizations),
            anomalies_count=len(self.anomalies),
            forecast=self.forecast,
        )

    def to_dict(self, report_generator: ReportSummaryBuilder) -> Dict[str, object]:
        """Serialize the audit payload returned by the CLI."""
        summary = self.build_summary(report_generator)
        return {
            "summary": summary,
            "service_costs": self.service_costs_dict,
            "optimizations": self.optimizations_dict,
            "budget_alerts": self.budget_alerts_dict,
            "anomalies": self.anomalies,
        }


def resolve_analysis_period(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    lookback_days: int = 30,
) -> Tuple[str, str]:
    """Resolve the audit analysis window."""
    end_reference = (
        datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    )
    start_reference = (
        datetime.strptime(start_date, "%Y-%m-%d")
        if start_date
        else end_reference - timedelta(days=lookback_days)
    )
    return (
        start_reference.strftime("%Y-%m-%d"),
        end_reference.strftime("%Y-%m-%d"),
    )


def build_daily_costs(cost_and_usage: Dict[str, object]) -> List[Dict[str, object]]:
    """Convert Cost Explorer results into a daily cost list."""
    daily_costs: List[Dict[str, object]] = []
    for result in cost_and_usage.get("ResultsByTime", []):
        total_cost = sum(
            float(group["Metrics"]["UnblendedCost"]["Amount"])
            for group in result.get("Groups", [])
        )
        daily_costs.append(
            {
                "date": result["TimePeriod"]["Start"],
                "cost": total_cost,
            }
        )
    return daily_costs


def build_budget_definitions(
    budgets: Optional[Sequence[Dict[str, float]]] = None,
) -> List[Dict[str, float]]:
    """Return a mutable copy of the budget configuration."""
    source = budgets if budgets is not None else DEFAULT_BUDGETS
    return [dict(budget) for budget in source]


def collect_audit_results(
    analyzer: CostAnalyzerProtocol,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    budgets: Optional[Sequence[Dict[str, float]]] = None,
    forecast_multiplier: float = 1.10,
) -> AuditResults:
    """Collect all data required for a full audit run."""
    resolved_start_date, resolved_end_date = resolve_analysis_period(
        start_date=start_date,
        end_date=end_date,
    )
    budget_definitions = build_budget_definitions(budgets)

    service_costs = analyzer.get_service_costs(resolved_start_date, resolved_end_date)
    daily_costs = build_daily_costs(
        analyzer.get_cost_and_usage(
            resolved_start_date,
            resolved_end_date,
            granularity="DAILY",
        )
    )
    idle_resources = analyzer.identify_idle_resources()
    right_sizing_opportunities = analyzer.identify_right_sizing_opportunities()
    ri_recommendations = analyzer.get_reserved_instance_recommendations()
    savings_plans_recommendations = analyzer.get_savings_plans_recommendations()
    anomalies = analyzer.get_cost_anomaly_detection()
    budget_alerts = analyzer.simulate_budget_alerts(budget_definitions)

    total_cost = sum(service.cost for service in service_costs)
    forecast_end_date = (
        datetime.strptime(resolved_end_date, "%Y-%m-%d") + timedelta(days=30)
    ).strftime("%Y-%m-%d")
    forecast_data = analyzer.get_cost_forecast(resolved_end_date, forecast_end_date)
    forecast = float(
        forecast_data.get("Total", {}).get("Amount", total_cost * forecast_multiplier)
    )

    return AuditResults(
        start_date=resolved_start_date,
        end_date=resolved_end_date,
        service_costs=service_costs,
        daily_costs=daily_costs,
        idle_resources=idle_resources,
        right_sizing_opportunities=right_sizing_opportunities,
        ri_recommendations=ri_recommendations,
        savings_plans_recommendations=savings_plans_recommendations,
        anomalies=anomalies,
        budget_alerts=budget_alerts,
        forecast=forecast,
    )


def generate_audit_artifacts(
    audit_results: AuditResults,
    visualizer: CostVisualizer,
    report_generator: ReportGenerator,
) -> AuditArtifacts:
    """Generate reports and visualizations for an audit run."""
    service_costs = audit_results.service_costs_dict
    daily_costs = audit_results.daily_costs
    optimizations = audit_results.optimizations_dict
    budget_alerts = audit_results.budget_alerts_dict
    anomalies = audit_results.anomalies

    chart_files = [
        visualizer.plot_service_cost_breakdown(service_costs),
        visualizer.plot_cost_trend(daily_costs),
        visualizer.plot_cost_pie_chart(service_costs),
        visualizer.plot_savings_opportunities(optimizations),
        visualizer.plot_budget_status(budget_alerts),
    ]

    if anomalies:
        chart_files.append(
            visualizer.plot_anomaly_timeline(
                daily_costs,
                anomalies,
            )
        )

    chart_files.append(
        visualizer.create_dashboard(
            service_costs,
            daily_costs,
            optimizations,
            budget_alerts,
            anomalies,
        )
    )

    summary = audit_results.build_summary(report_generator)
    html_report = report_generator.generate_html_report(
        summary=summary,
        service_costs=service_costs,
        optimizations=optimizations,
        budget_alerts=budget_alerts,
        anomalies=anomalies,
    )
    json_report = report_generator.generate_json_report(
        summary=summary,
        service_costs=service_costs,
        optimizations=optimizations,
        budget_alerts=budget_alerts,
        anomalies=anomalies,
    )
    markdown_report = report_generator.generate_markdown_report(
        summary=summary,
        service_costs=service_costs,
        optimizations=optimizations,
        budget_alerts=budget_alerts,
        anomalies=anomalies,
    )
    csv_report = report_generator.generate_csv_report(
        service_costs,
        "service_costs.csv",
        fieldnames=list(SERVICE_COST_CSV_FIELDS),
    )

    return AuditArtifacts(
        html_report=html_report,
        json_report=json_report,
        markdown_report=markdown_report,
        csv_report=csv_report,
        chart_files=chart_files,
    )
