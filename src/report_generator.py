#!/usr/bin/env python3
"""
AWS Cost Report Generator
Generates comprehensive cost analysis reports in multiple formats.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Template
import csv


class ReportGenerator:
    """Generates AWS cost analysis reports."""

    def __init__(self, output_dir: str = "./reports"):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to save generated reports
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.report_date = datetime.now().strftime("%Y-%m-%d")

    def generate_executive_summary(
        self,
        total_cost: float,
        potential_savings: float,
        recommendations_count: int,
        anomalies_count: int,
        forecast: float,
    ) -> Dict:
        """
        Generate executive summary data.

        Args:
            total_cost: Current total cost
            potential_savings: Total potential savings
            recommendations_count: Number of recommendations
            anomalies_count: Number of anomalies detected
            forecast: Forecasted cost

        Returns:
            Executive summary dictionary
        """
        savings_percentage = (
            (potential_savings / total_cost * 100) if total_cost > 0 else 0
        )

        return {
            "report_date": self.report_date,
            "analysis_period": "Last 30 days",
            "total_spend": {"amount": total_cost, "formatted": f"${total_cost:,.2f}"},
            "forecasted_spend": {"amount": forecast, "formatted": f"${forecast:,.2f}"},
            "potential_monthly_savings": {
                "amount": potential_savings,
                "formatted": f"${potential_savings:,.2f}",
                "percentage": round(savings_percentage, 1),
            },
            "optimization_opportunities": recommendations_count,
            "anomalies_detected": anomalies_count,
            "health_score": self._calculate_health_score(
                savings_percentage, anomalies_count, recommendations_count
            ),
        }

    def _calculate_health_score(
        self,
        savings_percentage: float,
        anomalies_count: int,
        recommendations_count: int,
    ) -> Dict:
        """
        Calculate overall cost health score.

        Returns:
            Health score dictionary with score and status
        """
        score = 100

        # Deduct for potential savings (indicates waste)
        score -= min(savings_percentage * 2, 30)

        # Deduct for anomalies
        score -= min(anomalies_count * 5, 20)

        # Deduct for too many recommendations (indicates poor optimization)
        if recommendations_count > 10:
            score -= min((recommendations_count - 10) * 2, 20)

        score = max(score, 0)

        if score >= 80:
            status = "GOOD"
            color = "#1D8102"
        elif score >= 60:
            status = "FAIR"
            color = "#FF9900"
        else:
            status = "NEEDS_ATTENTION"
            color = "#D13212"

        return {"score": round(score), "status": status, "color": color}

    def generate_html_report(
        self,
        summary: Dict,
        service_costs: List[Dict],
        optimizations: List[Dict],
        budget_alerts: List[Dict],
        anomalies: List[Dict],
        output_filename: str = "cost_report.html",
    ) -> str:
        """
        Generate comprehensive HTML report.

        Args:
            summary: Executive summary data
            service_costs: Service cost breakdown
            optimizations: Optimization recommendations
            budget_alerts: Budget alert data
            anomalies: Detected anomalies
            output_filename: Output file name

        Returns:
            Path to generated report
        """
        html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Cost Analysis Report - {{ summary.report_date }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background-color: #f5f5f5;
            color: #232F3E;
            line-height: 1.6;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: linear-gradient(135deg, #232F3E 0%, #1a242f 100%);
            color: white;
            padding: 40px 0;
            margin-bottom: 30px;
        }

        header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        h1 {
            font-size: 28px;
            font-weight: 600;
        }

        .report-meta {
            text-align: right;
            opacity: 0.9;
        }

        .health-score {
            display: inline-flex;
            align-items: center;
            padding: 10px 20px;
            border-radius: 8px;
            font-size: 18px;
            font-weight: bold;
        }

        .health-score.good { background-color: #1D8102; }
        .health-score.fair { background-color: #FF9900; color: #232F3E; }
        .health-score.needs-attention { background-color: #D13212; }

        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        .card h3 {
            font-size: 14px;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 10px;
            letter-spacing: 0.5px;
        }

        .card .value {
            font-size: 32px;
            font-weight: 700;
            color: #232F3E;
        }

        .card .subtitle {
            font-size: 13px;
            color: #888;
            margin-top: 5px;
        }

        .card.highlight {
            background: linear-gradient(135deg, #FF9900 0%, #e68a00 100%);
            color: white;
        }

        .card.highlight h3 { color: rgba(255,255,255,0.9); }
        .card.highlight .value { color: white; }
        .card.highlight .subtitle { color: rgba(255,255,255,0.8); }

        section {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        section h2 {
            font-size: 20px;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }

        th {
            background-color: #f8f9fa;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            color: #666;
        }

        tr:hover {
            background-color: #f8f9fa;
        }

        .priority-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .priority-high { background-color: #fde8e8; color: #D13212; }
        .priority-medium { background-color: #fff3e0; color: #e68a00; }
        .priority-low { background-color: #e8f5e9; color: #1D8102; }

        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .status-ok { background-color: #e8f5e9; color: #1D8102; }
        .status-warning { background-color: #fff3e0; color: #e68a00; }
        .status-critical { background-color: #fde8e8; color: #D13212; }

        .effort-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
            background-color: #f0f0f0;
            color: #666;
        }

        .chart-placeholder {
            background-color: #f8f9fa;
            border: 2px dashed #ddd;
            border-radius: 8px;
            padding: 40px;
            text-align: center;
            color: #888;
        }

        .service-row td:first-child {
            font-weight: 500;
        }

        .cost {
            font-weight: 600;
            color: #232F3E;
        }

        .savings {
            color: #1D8102;
            font-weight: 600;
        }

        .anomaly-high { background-color: #fff5f5; }
        .anomaly-medium { background-color: #fffbf0; }

        footer {
            text-align: center;
            padding: 30px;
            color: #888;
            font-size: 14px;
        }

        @media print {
            body { background: white; }
            .card, section { box-shadow: none; border: 1px solid #eee; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div>
                <h1>AWS Cost Analysis Report</h1>
                <p style="opacity: 0.8; margin-top: 5px;">Comprehensive Cost Audit & Optimization</p>
            </div>
            <div class="report-meta">
                <div class="health-score {{ summary.health_score.status|lower|replace('_', '-') }}"
                     style="background-color: {{ summary.health_score.color }};">
                    Health Score: {{ summary.health_score.score }}/100
                </div>
                <p style="margin-top: 10px;">{{ summary.report_date }}</p>
            </div>
        </div>
    </header>

    <div class="container">
        <!-- Executive Summary Cards -->
        <div class="summary-cards">
            <div class="card">
                <h3>Total Spend (30 Days)</h3>
                <div class="value">{{ summary.total_spend.formatted }}</div>
                <div class="subtitle">{{ summary.analysis_period }}</div>
            </div>
            <div class="card highlight">
                <h3>Potential Monthly Savings</h3>
                <div class="value">{{ summary.potential_monthly_savings.formatted }}</div>
                <div class="subtitle">{{ summary.potential_monthly_savings.percentage }}% of current spend</div>
            </div>
            <div class="card">
                <h3>Forecasted Spend</h3>
                <div class="value">{{ summary.forecasted_spend.formatted }}</div>
                <div class="subtitle">End of month projection</div>
            </div>
            <div class="card">
                <h3>Optimization Opportunities</h3>
                <div class="value">{{ summary.optimization_opportunities }}</div>
                <div class="subtitle">{{ summary.anomalies_detected }} anomalies detected</div>
            </div>
        </div>

        <!-- Service Cost Breakdown -->
        <section>
            <h2>Service Cost Breakdown</h2>
            <table>
                <thead>
                    <tr>
                        <th>Service</th>
                        <th>Cost</th>
                        <th>% of Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for service in service_costs[:15] %}
                    <tr class="service-row">
                        <td>{{ service.service_name }}</td>
                        <td class="cost">${{ "%.2f"|format(service.cost) }}</td>
                        <td>{{ "%.1f"|format(service.cost / summary.total_spend.amount * 100) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>

        <!-- Optimization Recommendations -->
        <section>
            <h2>Cost Optimization Recommendations</h2>
            {% if optimizations %}
            <table>
                <thead>
                    <tr>
                        <th>Resource</th>
                        <th>Type</th>
                        <th>Description</th>
                        <th>Current Cost</th>
                        <th>Potential Savings</th>
                        <th>Priority</th>
                        <th>Effort</th>
                    </tr>
                </thead>
                <tbody>
                    {% for opt in optimizations %}
                    <tr>
                        <td><strong>{{ opt.service }}</strong><br><small>{{ opt.resource_id }}</small></td>
                        <td>{{ opt.recommendation_type }}</td>
                        <td>{{ opt.description }}</td>
                        <td class="cost">${{ "%.2f"|format(opt.current_cost) }}</td>
                        <td class="savings">${{ "%.2f"|format(opt.potential_savings) }}</td>
                        <td>
                            <span class="priority-badge priority-{{ opt.priority|lower }}">
                                {{ opt.priority }}
                            </span>
                        </td>
                        <td><span class="effort-badge">{{ opt.implementation_effort }}</span></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="color: #1D8102; text-align: center; padding: 20px;">
                ✓ No immediate optimization opportunities detected. Your infrastructure is well-optimized!
            </p>
            {% endif %}
        </section>

        <!-- Budget Status -->
        <section>
            <h2>Budget Status & Alerts</h2>
            <table>
                <thead>
                    <tr>
                        <th>Budget Name</th>
                        <th>Limit</th>
                        <th>Current Spend</th>
                        <th>Forecast</th>
                        <th>Utilization</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for budget in budget_alerts %}
                    <tr>
                        <td><strong>{{ budget.budget_name }}</strong></td>
                        <td>${{ "%.2f"|format(budget.limit) }}</td>
                        <td>${{ "%.2f"|format(budget.current_spend) }}</td>
                        <td>${{ "%.2f"|format(budget.forecasted_spend) }}</td>
                        <td>{{ budget.threshold_percentage }}%</td>
                        <td>
                            <span class="status-badge status-{{ budget.alert_status|lower }}">
                                {{ budget.alert_status }}
                            </span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </section>

        <!-- Cost Anomalies -->
        <section>
            <h2>Cost Anomalies Detected</h2>
            {% if anomalies %}
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Actual Cost</th>
                        <th>Expected Range</th>
                        <th>Deviation</th>
                        <th>Severity</th>
                    </tr>
                </thead>
                <tbody>
                    {% for anomaly in anomalies %}
                    <tr class="anomaly-{{ anomaly.severity|lower }}">
                        <td>{{ anomaly.date }}</td>
                        <td class="cost">${{ "%.2f"|format(anomaly.cost) }}</td>
                        <td>{{ anomaly.expected_range }}</td>
                        <td>+{{ "%.1f"|format(anomaly.deviation_percentage) }}%</td>
                        <td>
                            <span class="priority-badge priority-{{ 'high' if anomaly.severity == 'HIGH' else 'medium' }}">
                                {{ anomaly.severity }}
                            </span>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p style="color: #1D8102; text-align: center; padding: 20px;">
                ✓ No cost anomalies detected in the analysis period.
            </p>
            {% endif %}
        </section>

        <!-- Methodology -->
        <section>
            <h2>Analysis Methodology</h2>
            <div style="color: #555;">
                <p><strong>Data Sources:</strong></p>
                <ul style="margin-left: 20px; margin-bottom: 15px;">
                    <li>AWS Cost Explorer API for historical cost data</li>
                    <li>AWS CloudWatch for resource utilization metrics</li>
                    <li>AWS Budgets for spending limits and forecasts</li>
                    <li>EC2, RDS, and EBS APIs for resource inventory</li>
                </ul>

                <p><strong>Analysis Techniques:</strong></p>
                <ul style="margin-left: 20px; margin-bottom: 15px;">
                    <li><strong>Right-sizing Analysis:</strong> CPU utilization thresholds (<10% = downsize candidate)</li>
                    <li><strong>Idle Resource Detection:</strong> Stopped instances, unattached volumes, unused IPs</li>
                    <li><strong>Anomaly Detection:</strong> Statistical analysis using 2σ deviation from baseline</li>
                    <li><strong>Cost Forecasting:</strong> Linear extrapolation based on current spend rate</li>
                </ul>

                <p><strong>Recommendations Priority:</strong></p>
                <ul style="margin-left: 20px;">
                    <li><strong>HIGH:</strong> Immediate action recommended, significant savings potential</li>
                    <li><strong>MEDIUM:</strong> Action within 30 days recommended</li>
                    <li><strong>LOW:</strong> Consider for long-term optimization</li>
                </ul>
            </div>
        </section>
    </div>

    <footer>
        <p>Generated by AWS Cost Audit Tool | {{ summary.report_date }}</p>
        <p style="margin-top: 5px;">For detailed visualizations, see the accompanying charts in the output directory.</p>
    </footer>
</body>
</html>
        """

        template = Template(html_template)
        html_content = template.render(
            summary=summary,
            service_costs=service_costs,
            optimizations=optimizations,
            budget_alerts=budget_alerts,
            anomalies=anomalies,
        )

        output_path = os.path.join(self.output_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def generate_json_report(
        self,
        summary: Dict,
        service_costs: List[Dict],
        optimizations: List[Dict],
        budget_alerts: List[Dict],
        anomalies: List[Dict],
        output_filename: str = "cost_report.json",
    ) -> str:
        """
        Generate JSON report for programmatic consumption.

        Args:
            summary: Executive summary data
            service_costs: Service cost breakdown
            optimizations: Optimization recommendations
            budget_alerts: Budget alert data
            anomalies: Detected anomalies
            output_filename: Output file name

        Returns:
            Path to generated report
        """
        report_data = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "report_type": "AWS Cost Analysis",
                "version": "1.0",
            },
            "executive_summary": summary,
            "service_costs": service_costs,
            "optimizations": optimizations,
            "budget_alerts": budget_alerts,
            "anomalies": anomalies,
        }

        output_path = os.path.join(self.output_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, default=str, ensure_ascii=False)

        return output_path

    def generate_csv_report(
        self,
        data: List[Dict],
        output_filename: str,
        fieldnames: Optional[List[str]] = None,
    ) -> str:
        """
        Generate CSV report.

        Args:
            data: List of dictionaries to export
            output_filename: Output file name
            fieldnames: Optional list of field names

        Returns:
            Path to generated report
        """
        if not data:
            return ""

        output_path = os.path.join(self.output_dir, output_filename)

        if fieldnames is None:
            fieldnames = list(data[0].keys())

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(data)

        return output_path

    def generate_markdown_report(
        self,
        summary: Dict,
        service_costs: List[Dict],
        optimizations: List[Dict],
        budget_alerts: List[Dict],
        anomalies: List[Dict],
        output_filename: str = "cost_report.md",
    ) -> str:
        """
        Generate Markdown report for documentation systems.

        Args:
            summary: Executive summary data
            service_costs: Service cost breakdown
            optimizations: Optimization recommendations
            budget_alerts: Budget alert data
            anomalies: Detected anomalies
            output_filename: Output file name

        Returns:
            Path to generated report
        """
        md_content = f"""# AWS Cost Analysis Report

**Report Date:** {summary['report_date']}
**Health Score:** {summary['health_score']['score']}/100 ({summary['health_score']['status']})

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Spend (30 Days) | {summary['total_spend']['formatted']} |
| Forecasted Spend | {summary['forecasted_spend']['formatted']} |
| Potential Monthly Savings | {summary['potential_monthly_savings']['formatted']} ({summary['potential_monthly_savings']['percentage']}%) |
| Optimization Opportunities | {summary['optimization_opportunities']} |
| Anomalies Detected | {summary['anomalies_detected']} |

---

## Service Cost Breakdown

| Service | Cost | % of Total |
|---------|------|------------|
"""
        total = summary["total_spend"]["amount"]
        for service in service_costs[:15]:
            pct = (service["cost"] / total * 100) if total > 0 else 0
            md_content += f"| {service['service_name']} | ${service['cost']:,.2f} | {pct:.1f}% |\n"

        md_content += """
---

## Cost Optimization Recommendations

| Service | Resource | Type | Current Cost | Potential Savings | Priority |
|---------|----------|------|--------------|-------------------|----------|
"""
        for opt in optimizations:
            md_content += f"| {opt['service']} | {opt['resource_id']} | {opt['recommendation_type']} | ${opt['current_cost']:,.2f} | ${opt['potential_savings']:,.2f} | **{opt['priority']}** |\n"

        md_content += """
---

## Budget Status

| Budget | Limit | Current | Forecast | Status |
|--------|-------|---------|----------|--------|
"""
        for budget in budget_alerts:
            md_content += f"| {budget['budget_name']} | ${budget['limit']:,.2f} | ${budget['current_spend']:,.2f} | ${budget['forecasted_spend']:,.2f} | **{budget['alert_status']}** |\n"

        if anomalies:
            md_content += """
---

## Cost Anomalies

| Date | Actual Cost | Expected Range | Deviation | Severity |
|------|-------------|----------------|-----------|----------|
"""
            for anomaly in anomalies:
                md_content += f"| {anomaly['date']} | ${anomaly['cost']:,.2f} | {anomaly['expected_range']} | +{anomaly['deviation_percentage']:.1f}% | **{anomaly['severity']}** |\n"

        md_content += """
---

## Methodology

### Data Sources
- AWS Cost Explorer API for historical cost data
- AWS CloudWatch for resource utilization metrics
- AWS Budgets for spending limits and forecasts
- EC2, RDS, and EBS APIs for resource inventory

### Analysis Techniques
- **Right-sizing Analysis:** CPU utilization thresholds (<10% = downsize candidate)
- **Idle Resource Detection:** Stopped instances, unattached volumes, unused IPs
- **Anomaly Detection:** Statistical analysis using 2σ deviation from baseline
- **Cost Forecasting:** Linear extrapolation based on current spend rate

---

*Generated by AWS Cost Audit Tool*
"""

        output_path = os.path.join(self.output_dir, output_filename)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return output_path
