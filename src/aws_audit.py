#!/usr/bin/env python3
"""
AWS Cost Audit command line interface.
"""

import argparse
from typing import Dict, Optional

try:
    from .audit_workflow import (
        AuditArtifacts,
        AuditResults,
        build_budget_definitions,
        collect_audit_results,
        generate_audit_artifacts,
        resolve_analysis_period,
    )
    from .cost_analyzer import get_analyzer
    from .report_generator import ReportGenerator
    from .visualizer import CostVisualizer
except ImportError:
    from audit_workflow import (
        AuditArtifacts,
        AuditResults,
        build_budget_definitions,
        collect_audit_results,
        generate_audit_artifacts,
        resolve_analysis_period,
    )
    from cost_analyzer import get_analyzer
    from report_generator import ReportGenerator
    from visualizer import CostVisualizer


FULL_AUDIT_BANNER = (
    "AWS COST AUDIT TOOL",
    "Comprehensive Cost Analysis & Optimization",
)

SAMPLE_SUMMARY_WIDTH = 60
QUICK_ANALYSIS_LIMIT = 10
OPTIMIZATION_PREVIEW_LIMIT = 5


def run_full_audit(
    use_mock: bool = True,
    aws_profile: Optional[str] = None,
    output_dir: str = "./output",
    reports_dir: str = "./reports",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, object]:
    """Run the complete audit workflow and generate all artifacts."""
    _print_banner(*FULL_AUDIT_BANNER)

    print("[1/3] Initializing components...")
    analyzer = get_analyzer(use_mock=use_mock, profile_name=aws_profile)
    visualizer = CostVisualizer(output_dir=output_dir)
    report_generator = ReportGenerator(output_dir=reports_dir)
    resolved_start_date, resolved_end_date = resolve_analysis_period(
        start_date=start_date,
        end_date=end_date,
    )
    print(f"      Analysis period: {resolved_start_date} to {resolved_end_date}")
    print()

    print("[2/3] Collecting audit data...")
    audit_results = collect_audit_results(
        analyzer=analyzer,
        start_date=resolved_start_date,
        end_date=resolved_end_date,
    )
    _print_audit_findings(audit_results)

    print("[3/3] Generating reports and visualizations...")
    artifacts = generate_audit_artifacts(
        audit_results=audit_results,
        visualizer=visualizer,
        report_generator=report_generator,
    )
    summary = audit_results.build_summary(report_generator)
    print()

    _print_completion_summary(
        summary=summary,
        artifacts=artifacts,
        output_dir=output_dir,
    )

    payload = audit_results.to_dict(report_generator)
    payload.update(artifacts.to_dict())
    return payload


def quick_analysis(
    use_mock: bool = True,
    aws_profile: Optional[str] = None,
) -> None:
    """Print a lightweight cost overview to the console."""
    analyzer = get_analyzer(use_mock=use_mock, profile_name=aws_profile)
    start_date, end_date = resolve_analysis_period()
    service_costs = analyzer.get_service_costs(start_date, end_date)
    total_cost = sum(service.cost for service in service_costs)
    idle_resources = analyzer.identify_idle_resources()

    print("\nAWS Cost Quick Analysis\n")
    print("Top 10 Services by Cost:")
    print("-" * 45)
    for index, service in enumerate(service_costs[:QUICK_ANALYSIS_LIMIT], start=1):
        percentage = (service.cost / total_cost * 100) if total_cost else 0
        print(
            f"{index:2}. {service.service_name:30} "
            f"${service.cost:>8,.2f} ({percentage:>5.1f}%)"
        )
    print("-" * 45)
    print(f"{'TOTAL':32} ${total_cost:>8,.2f}")

    print("\nQuick Optimization Scan:")
    print("-" * 45)
    for optimization in idle_resources[:OPTIMIZATION_PREVIEW_LIMIT]:
        print(
            f"  - [{optimization.priority}] {optimization.service}: "
            f"{optimization.description[:40]}..."
        )
    print()


def budget_check(
    use_mock: bool = True,
    aws_profile: Optional[str] = None,
) -> None:
    """Print the current budget status."""
    analyzer = get_analyzer(use_mock=use_mock, profile_name=aws_profile)
    budget_alerts = analyzer.simulate_budget_alerts(build_budget_definitions())

    print("\nBudget Status Check\n")
    for alert in budget_alerts:
        print(f"{_format_budget_status(alert.alert_status)} {alert.budget_name}")
        print(f"   Limit: ${alert.limit:,.2f}")
        print(
            "   Current: "
            f"${alert.current_spend:,.2f} ({alert.threshold_percentage:.1f}%)"
        )
        print(f"   Forecast: ${alert.forecasted_spend:,.2f}")
        print(f"   Status: {alert.alert_status}")
        print()


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="AWS Cost Audit Tool - Analyze and optimize AWS costs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full audit with mock data (demo)
  python -m src.aws_audit --full --mock

  # Run full audit with AWS credentials
  python -m src.aws_audit --full --profile production

  # Quick analysis
  python -m src.aws_audit --quick

  # Budget check only
  python -m src.aws_audit --budget

  # Custom output directories
  python -m src.aws_audit --full --output ./charts --reports ./docs
        """,
    )

    parser.add_argument(
        "--full",
        "-f",
        action="store_true",
        help="Run full cost audit with reports",
    )
    parser.add_argument(
        "--quick",
        "-q",
        action="store_true",
        help="Run quick cost analysis (console output only)",
    )
    parser.add_argument(
        "--budget",
        "-b",
        action="store_true",
        help="Check budget status only",
    )
    parser.add_argument(
        "--mock",
        "-m",
        action="store_true",
        default=True,
        help="Use mock data for demonstration (default: True)",
    )
    parser.add_argument(
        "--profile",
        "-p",
        type=str,
        help="AWS profile name from ~/.aws/credentials",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="./output",
        help="Output directory for charts (default: ./output)",
    )
    parser.add_argument(
        "--reports",
        "-r",
        type=str,
        default="./reports",
        help="Output directory for reports (default: ./reports)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Analysis start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Analysis end date (YYYY-MM-DD)",
    )
    return parser


def main() -> None:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    use_mock = args.mock and not args.profile

    if args.quick:
        quick_analysis(use_mock=use_mock, aws_profile=args.profile)
        return

    if args.budget:
        budget_check(use_mock=use_mock, aws_profile=args.profile)
        return

    run_full_audit(
        use_mock=use_mock,
        aws_profile=args.profile,
        output_dir=args.output,
        reports_dir=args.reports,
        start_date=args.start_date,
        end_date=args.end_date,
    )


def _print_banner(title: str, subtitle: str) -> None:
    """Print the standard command banner."""
    print("=" * SAMPLE_SUMMARY_WIDTH)
    print(f"   {title}")
    print(f"   {subtitle}")
    print("=" * SAMPLE_SUMMARY_WIDTH)
    print()


def _print_audit_findings(audit_results: AuditResults) -> None:
    """Print the key findings gathered during the audit."""
    print(f"      Services analyzed: {len(audit_results.service_costs)}")
    print(f"      Total spend: ${audit_results.total_cost:,.2f}")
    print(f"      Days analyzed: {len(audit_results.daily_costs)}")
    print(f"      Idle resources: {len(audit_results.idle_resources)}")
    print(
        "      Right-sizing opportunities: "
        f"{len(audit_results.right_sizing_opportunities)}"
    )
    print(f"      Potential monthly savings: ${audit_results.potential_savings:,.2f}")
    print(f"      RI recommendations: {len(audit_results.ri_recommendations)}")
    print(
        "      Savings Plans recommendations: "
        f"{len(audit_results.savings_plans_recommendations)}"
    )
    print(f"      Anomalies detected: {len(audit_results.anomalies)}")
    for anomaly in audit_results.anomalies:
        print(
            f"        - {anomaly['date']}: "
            f"${anomaly['cost']:,.2f} ({anomaly['severity']})"
        )
    for alert in audit_results.budget_alerts:
        print(
            "      "
            f"{_format_budget_status(alert.alert_status)} "
            f"{alert.budget_name}: "
            f"{alert.threshold_percentage:.1f}% ({alert.alert_status})"
        )
    print()


def _print_completion_summary(
    summary: Dict[str, object],
    artifacts: AuditArtifacts,
    output_dir: str,
) -> None:
    """Print generated files and the executive summary."""
    print("=" * SAMPLE_SUMMARY_WIDTH)
    print("   AUDIT COMPLETE")
    print("=" * SAMPLE_SUMMARY_WIDTH)
    print()
    print("Generated Reports:")
    print(f"  - HTML Report: {artifacts.html_report}")
    print(f"  - JSON Report: {artifacts.json_report}")
    print(f"  - Markdown Report: {artifacts.markdown_report}")
    print(f"  - CSV Export: {artifacts.csv_report}")
    print()
    print("Generated Visualizations:")
    print(f"  - Service Cost Breakdown: {output_dir}/service_cost_breakdown.png")
    print(f"  - Cost Trend: {output_dir}/cost_trend.png")
    print(f"  - Cost Distribution: {output_dir}/cost_distribution.png")
    print(f"  - Savings Opportunities: {output_dir}/savings_opportunities.png")
    print(f"  - Budget Status: {output_dir}/budget_status.png")
    print(f"  - Cost Dashboard: {output_dir}/cost_dashboard.png")
    if any(path.endswith("anomaly_timeline.png") for path in artifacts.chart_files):
        print(f"  - Anomaly Timeline: {output_dir}/anomaly_timeline.png")
    print()
    print("-" * SAMPLE_SUMMARY_WIDTH)
    print("EXECUTIVE SUMMARY")
    print("-" * SAMPLE_SUMMARY_WIDTH)
    print(f"Total Spend (30 days):     {summary['total_spend']['formatted']}")
    print(
        "Potential Monthly Savings: "
        f"{summary['potential_monthly_savings']['formatted']} "
        f"({summary['potential_monthly_savings']['percentage']:.1f}%)"
    )
    print(
        "Health Score:              "
        f"{summary['health_score']['score']}/100 "
        f"({summary['health_score']['status']})"
    )
    print("-" * SAMPLE_SUMMARY_WIDTH)
    print()


def _format_budget_status(status: str) -> str:
    """Return an ASCII-only status label for console output."""
    return {
        "OK": "[OK]",
        "WARNING": "[WARN]",
        "CRITICAL": "[ALERT]",
    }.get(status, "[INFO]")


if __name__ == "__main__":
    main()
