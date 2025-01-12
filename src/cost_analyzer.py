#!/usr/bin/env python3
"""
AWS Cost Analyzer Module
Core functionality for analyzing AWS costs and identifying optimization opportunities.
"""

import boto3
import csv
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional

SERVICE_COST_CSV_FIELDS = [
    "service_name",
    "cost",
    "currency",
    "usage_quantity",
    "unit",
]
MOCK_BUDGET_SPEND_RATIOS = (
    (0.9647, 1.1358),
    (0.8923, 0.9457),
    (0.6913, 0.8247),
)


@dataclass
class ServiceCost:
    """Represents cost data for a single AWS service."""

    service_name: str
    cost: float
    currency: str = "USD"
    usage_quantity: float = 0.0
    unit: str = ""

    def to_dict(self) -> Dict:
        return {
            "service_name": self.service_name,
            "cost": self.cost,
            "currency": self.currency,
            "usage_quantity": self.usage_quantity,
            "unit": self.unit,
        }


@dataclass
class CostOptimization:
    """Represents a cost optimization recommendation."""

    service: str
    resource_id: str
    recommendation_type: str
    current_cost: float
    potential_savings: float
    description: str
    priority: str  # HIGH, MEDIUM, LOW
    implementation_effort: str  # EASY, MODERATE, COMPLEX

    def to_dict(self) -> Dict:
        return {
            "service": self.service,
            "resource_id": self.resource_id,
            "recommendation_type": self.recommendation_type,
            "current_cost": self.current_cost,
            "potential_savings": self.potential_savings,
            "description": self.description,
            "priority": self.priority,
            "implementation_effort": self.implementation_effort,
        }


@dataclass
class BudgetAlert:
    """Represents a budget alert configuration."""

    budget_name: str
    limit: float
    current_spend: float
    forecasted_spend: float
    threshold_percentage: float
    alert_status: str  # OK, WARNING, CRITICAL

    def to_dict(self) -> Dict:
        return {
            "budget_name": self.budget_name,
            "limit": self.limit,
            "current_spend": self.current_spend,
            "forecasted_spend": self.forecasted_spend,
            "threshold_percentage": self.threshold_percentage,
            "alert_status": self.alert_status,
        }


class AWSCostAnalyzer:
    """
    Main class for AWS Cost Analysis.
    Provides methods to retrieve, analyze, and optimize AWS costs.
    """

    def __init__(self, profile_name: Optional[str] = None, region: str = "us-east-1"):
        """
        Initialize the AWS Cost Analyzer.

        Args:
            profile_name: AWS profile name from ~/.aws/credentials
            region: AWS region for API calls
        """
        self.region = region
        self.session = self._create_session(profile_name)
        self.ce_client = self.session.client(
            "ce", region_name="us-east-1"
        )  # Cost Explorer only in us-east-1
        self.budgets_client = self.session.client("budgets", region_name="us-east-1")
        self.ec2_client = self.session.client("ec2")
        self.rds_client = self.session.client("rds")
        self.cloudwatch_client = self.session.client("cloudwatch")

    def _create_session(self, profile_name: Optional[str]) -> boto3.Session:
        """Create boto3 session with optional profile."""
        if profile_name:
            return boto3.Session(profile_name=profile_name)
        return boto3.Session()

    def get_cost_and_usage(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAILY",
        group_by: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Get cost and usage data from AWS Cost Explorer.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY, MONTHLY, or HOURLY
            group_by: List of group by dimensions

        Returns:
            Cost Explorer response data
        """
        if group_by is None:
            group_by = [{"Type": "DIMENSION", "Key": "SERVICE"}]

        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity=granularity,
                Metrics=["BlendedCost", "UnblendedCost", "UsageQuantity"],
                GroupBy=group_by,
            )
            return response
        except Exception as e:
            print(f"Error fetching cost data: {e}")
            return {}

    def get_cost_forecast(
        self, start_date: str, end_date: str, granularity: str = "MONTHLY"
    ) -> Dict:
        """
        Get cost forecast for the specified period.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            granularity: DAILY or MONTHLY

        Returns:
            Forecast data
        """
        try:
            response = self.ce_client.get_cost_forecast(
                TimePeriod={"Start": start_date, "End": end_date},
                Granularity=granularity,
                Metric="UNBLENDED_COST",
            )
            return response
        except Exception as e:
            print(f"Error fetching forecast: {e}")
            return {}

    def get_service_costs(self, start_date: str, end_date: str) -> List[ServiceCost]:
        """
        Get cost breakdown by AWS service.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of ServiceCost objects
        """
        response = self.get_cost_and_usage(start_date, end_date, "MONTHLY")
        service_costs = []

        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                service_name = group["Keys"][0]
                metrics = group["Metrics"]

                service_cost = ServiceCost(
                    service_name=service_name,
                    cost=float(metrics["UnblendedCost"]["Amount"]),
                    currency=metrics["UnblendedCost"]["Unit"],
                    usage_quantity=float(
                        metrics.get("UsageQuantity", {}).get("Amount", 0)
                    ),
                    unit=metrics.get("UsageQuantity", {}).get("Unit", ""),
                )
                service_costs.append(service_cost)

        return sorted(service_costs, key=lambda x: x.cost, reverse=True)

    def get_reserved_instance_recommendations(self) -> List[Dict]:
        """
        Get Reserved Instance purchase recommendations.

        Returns:
            List of RI recommendations
        """
        try:
            response = self.ce_client.get_reservation_purchase_recommendation(
                Service="Amazon Elastic Compute Cloud - Compute"
            )
            return response.get("Recommendations", [])
        except Exception as e:
            print(f"Error fetching RI recommendations: {e}")
            return []

    def get_savings_plans_recommendations(self) -> List[Dict]:
        """
        Get Savings Plans recommendations.

        Returns:
            List of Savings Plans recommendations
        """
        try:
            response = self.ce_client.get_savings_plans_purchase_recommendation(
                SavingsPlansType="COMPUTE_SP"
            )
            return response.get("Recommendations", [])
        except Exception as e:
            print(f"Error fetching Savings Plans recommendations: {e}")
            return []

    def identify_idle_resources(self) -> List[CostOptimization]:
        """
        Identify idle or underutilized resources.

        Returns:
            List of CostOptimization recommendations
        """
        optimizations = []

        # Check for stopped EC2 instances
        try:
            instances = self.ec2_client.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
            )

            for reservation in instances.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    instance_type = instance["InstanceType"]

                    # Estimate monthly cost (simplified)
                    estimated_cost = self._estimate_instance_cost(instance_type)

                    optimizations.append(
                        CostOptimization(
                            service="EC2",
                            resource_id=instance_id,
                            recommendation_type="Idle Resource",
                            current_cost=estimated_cost,
                            potential_savings=estimated_cost,
                            description=f"Stopped instance {instance_id} ({instance_type}) incurring storage costs",
                            priority="MEDIUM",
                            implementation_effort="EASY",
                        )
                    )
        except Exception as e:
            print(f"Error checking EC2 instances: {e}")

        # Check for unattached EBS volumes
        try:
            volumes = self.ec2_client.describe_volumes(
                Filters=[{"Name": "status", "Values": ["available"]}]
            )

            for volume in volumes.get("Volumes", []):
                volume_id = volume["VolumeId"]
                size_gb = volume["Size"]
                estimated_cost = size_gb * 0.10  # Approximate GP2 cost

                optimizations.append(
                    CostOptimization(
                        service="EBS",
                        resource_id=volume_id,
                        recommendation_type="Unattached Storage",
                        current_cost=estimated_cost,
                        potential_savings=estimated_cost,
                        description=f"Unattached volume {volume_id} ({size_gb}GB) costing ~${estimated_cost:.2f}/month",
                        priority="HIGH",
                        implementation_effort="EASY",
                    )
                )
        except Exception as e:
            print(f"Error checking EBS volumes: {e}")

        return optimizations

    def identify_right_sizing_opportunities(self) -> List[CostOptimization]:
        """
        Identify EC2 instances that could be right-sized.

        Returns:
            List of right-sizing recommendations
        """
        optimizations = []

        try:
            # Get CloudWatch metrics for instances
            instances = self.ec2_client.describe_instances()

            for reservation in instances.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    if instance["State"]["Name"] != "running":
                        continue

                    instance_id = instance["InstanceId"]
                    instance_type = instance["InstanceType"]

                    # Get CPU utilization for past 14 days
                    end_time = datetime.utcnow()
                    start_time = end_time - timedelta(days=14)

                    try:
                        metrics = self.cloudwatch_client.get_metric_statistics(
                            Namespace="AWS/EC2",
                            MetricName="CPUUtilization",
                            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,  # Daily
                            Statistics=["Average"],
                        )

                        datapoints = metrics.get("Datapoints", [])
                        if datapoints:
                            avg_cpu = sum(d["Average"] for d in datapoints) / len(
                                datapoints
                            )

                            if avg_cpu < 10:
                                estimated_cost = self._estimate_instance_cost(
                                    instance_type
                                )
                                savings = estimated_cost * 0.5  # Assume 50% savings

                                optimizations.append(
                                    CostOptimization(
                                        service="EC2",
                                        resource_id=instance_id,
                                        recommendation_type="Right-Sizing",
                                        current_cost=estimated_cost,
                                        potential_savings=savings,
                                        description=f"Instance {instance_id} has avg CPU {avg_cpu:.1f}%. Consider downsizing.",
                                        priority="HIGH",
                                        implementation_effort="MODERATE",
                                    )
                                )
                    except Exception:
                        continue
        except Exception as e:
            print(f"Error in right-sizing analysis: {e}")

        return optimizations

    def _estimate_instance_cost(self, instance_type: str) -> float:
        """
        Estimate monthly cost for an EC2 instance type.

        Args:
            instance_type: EC2 instance type (e.g., 't3.medium')

        Returns:
            Estimated monthly cost
        """
        # Simplified pricing table (USD/month, 730 hours)
        pricing = {
            "t3.nano": 3.65,
            "t3.micro": 7.30,
            "t3.small": 14.60,
            "t3.medium": 29.20,
            "t3.large": 58.40,
            "t3.xlarge": 116.80,
            "t3.2xlarge": 233.60,
            "m5.large": 70.00,
            "m5.xlarge": 140.00,
            "m5.2xlarge": 280.00,
            "c5.large": 62.00,
            "c5.xlarge": 124.00,
            "r5.large": 91.00,
            "r5.xlarge": 182.00,
        }
        return pricing.get(instance_type, 50.00)  # Default estimate

    def simulate_budget_alerts(self, budgets: List[Dict]) -> List[BudgetAlert]:
        """
        Simulate budget alerts based on current spend.

        Args:
            budgets: List of budget configurations

        Returns:
            List of BudgetAlert objects
        """
        alerts = []

        today = datetime.utcnow()
        start_of_month = today.replace(day=1).strftime("%Y-%m-%d")
        end_of_month = (
            (today.replace(day=1) + timedelta(days=32))
            .replace(day=1)
            .strftime("%Y-%m-%d")
        )

        # Get current month costs
        service_costs = self.get_service_costs(
            start_of_month, today.strftime("%Y-%m-%d")
        )
        total_spend = sum(sc.cost for sc in service_costs)

        # Get forecast
        try:
            forecast = self.get_cost_forecast(
                today.strftime("%Y-%m-%d"), end_of_month, "MONTHLY"
            )
            forecasted_spend = float(
                forecast.get("Total", {}).get("Amount", total_spend * 1.2)
            )
        except Exception:
            # Simple linear extrapolation
            days_passed = today.day
            days_in_month = (today.replace(day=1) + timedelta(days=32)).replace(
                day=1
            ) - today.replace(day=1)
            forecasted_spend = (total_spend / days_passed) * days_in_month.days

        for budget in budgets:
            budget_name = budget["name"]
            limit = budget["limit"]

            threshold_pct = (total_spend / limit) * 100
            forecast_pct = (forecasted_spend / limit) * 100

            alerts.append(
                BudgetAlert(
                    budget_name=budget_name,
                    limit=limit,
                    current_spend=total_spend,
                    forecasted_spend=forecasted_spend,
                    threshold_percentage=round(threshold_pct, 2),
                    alert_status=_resolve_budget_status(
                        threshold_percentage=threshold_pct,
                        forecast_percentage=forecast_pct,
                    ),
                )
            )

        return alerts

    def get_cost_anomaly_detection(self) -> List[Dict]:
        """
        Detect cost anomalies using historical data analysis.

        Returns:
            List of detected anomalies
        """
        anomalies = []

        # Get 90 days of daily cost data
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)

        response = self.get_cost_and_usage(
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            granularity="DAILY",
        )

        daily_costs = []
        for result in response.get("ResultsByTime", []):
            date = result["TimePeriod"]["Start"]
            cost = sum(
                float(group["Metrics"]["UnblendedCost"]["Amount"])
                for group in result.get("Groups", [])
            )
            daily_costs.append({"date": date, "cost": cost})

        if len(daily_costs) > 30:
            # Calculate baseline (average of first 60 days)
            baseline_costs = daily_costs[:60]
            avg_cost = sum(d["cost"] for d in baseline_costs) / len(baseline_costs)
            std_dev = (
                sum((d["cost"] - avg_cost) ** 2 for d in baseline_costs)
                / len(baseline_costs)
            ) ** 0.5

            # Detect anomalies in recent days
            for day in daily_costs[-7:]:
                if day["cost"] > avg_cost + (2 * std_dev):
                    anomalies.append(
                        {
                            "date": day["date"],
                            "cost": day["cost"],
                            "expected_range": f"${avg_cost:.2f} ± ${2*std_dev:.2f}",
                            "deviation_percentage": (
                                (day["cost"] - avg_cost) / avg_cost
                            )
                            * 100,
                            "severity": (
                                "HIGH"
                                if day["cost"] > avg_cost + (3 * std_dev)
                                else "MEDIUM"
                            ),
                        }
                    )

        return anomalies

    def export_costs_to_csv(
        self, service_costs: List[ServiceCost], output_path: str
    ) -> None:
        """
        Export service costs to CSV file.

        Args:
            service_costs: List of ServiceCost objects
            output_path: Path to output CSV file
        """
        _write_service_costs_to_csv(service_costs, output_path)

        print(f"Exported costs to {output_path}")


# Mock data generator for demonstration
class MockCostAnalyzer:
    """
    Mock implementation for demonstration without AWS credentials.
    Generates realistic sample data for portfolio showcase.
    """

    def __init__(self):
        self.services = [
            ("Amazon EC2", 2847.32, "USD"),
            ("Amazon RDS", 1523.45, "USD"),
            ("Amazon S3", 456.78, "USD"),
            ("AWS Lambda", 234.56, "USD"),
            ("Amazon CloudWatch", 189.23, "USD"),
            ("Amazon DynamoDB", 156.89, "USD"),
            ("Amazon API Gateway", 123.45, "USD"),
            ("AWS CloudFormation", 89.67, "USD"),
            ("Amazon SNS", 45.23, "USD"),
            ("AWS Key Management Service", 34.56, "USD"),
            ("Amazon Route 53", 28.90, "USD"),
            ("Amazon CloudFront", 234.12, "USD"),
            ("Amazon ECS", 567.89, "USD"),
            ("Amazon EKS", 890.12, "USD"),
            ("AWS Secrets Manager", 23.45, "USD"),
        ]

    def get_service_costs(self, start_date: str, end_date: str) -> List[ServiceCost]:
        """Generate mock service costs."""
        import random

        return [
            ServiceCost(
                service_name=name,
                cost=cost * random.uniform(0.9, 1.1),
                currency=currency,
                usage_quantity=random.uniform(100, 10000),
                unit="units",
            )
            for name, cost, currency in self.services
        ]

    def get_cost_and_usage(
        self, start_date: str, end_date: str, granularity: str = "DAILY"
    ) -> Dict:
        """Generate mock cost and usage data."""
        from datetime import datetime, timedelta
        import random

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        current = start

        results = []
        base_cost = 500

        while current < end:
            # Add some variance and occasional spikes
            daily_variance = random.uniform(0.8, 1.2)
            if random.random() < 0.05:  # 5% chance of spike
                daily_variance = random.uniform(1.5, 2.0)

            groups = [
                {
                    "Keys": [service[0]],
                    "Metrics": {
                        "UnblendedCost": {
                            "Amount": str(service[1] / 30 * daily_variance),
                            "Unit": "USD",
                        },
                        "BlendedCost": {
                            "Amount": str(service[1] / 30 * daily_variance * 0.98),
                            "Unit": "USD",
                        },
                        "UsageQuantity": {
                            "Amount": str(random.uniform(100, 5000)),
                            "Unit": "units",
                        },
                    },
                }
                for service in self.services[:5]  # Top 5 services for daily breakdown
            ]

            results.append(
                {
                    "TimePeriod": {
                        "Start": current.strftime("%Y-%m-%d"),
                        "End": (current + timedelta(days=1)).strftime("%Y-%m-%d"),
                    },
                    "Groups": groups,
                    "Total": {
                        "UnblendedCost": {
                            "Amount": str(base_cost * daily_variance),
                            "Unit": "USD",
                        }
                    },
                }
            )
            current += timedelta(days=1)

        return {"ResultsByTime": results}

    def get_cost_forecast(
        self, start_date: str, end_date: str, granularity: str = "MONTHLY"
    ) -> Dict:
        """Generate mock forecast data."""
        import random

        return {
            "Total": {"Amount": str(random.uniform(7000, 8500)), "Unit": "USD"},
            "ForecastResultsByTime": [
                {
                    "TimePeriod": {"Start": start_date, "End": end_date},
                    "MeanValue": "7650.00",
                }
            ],
        }

    def identify_idle_resources(self) -> List[CostOptimization]:
        """Generate mock idle resource recommendations."""
        return [
            CostOptimization(
                service="EC2",
                resource_id="i-0abc123def456",
                recommendation_type="Idle Resource",
                current_cost=87.60,
                potential_savings=87.60,
                description="Stopped t3.large instance incurring EBS storage costs",
                priority="MEDIUM",
                implementation_effort="EASY",
            ),
            CostOptimization(
                service="EBS",
                resource_id="vol-0xyz789abc123",
                recommendation_type="Unattached Storage",
                current_cost=45.00,
                potential_savings=45.00,
                description="Unattached 450GB GP2 volume not in use",
                priority="HIGH",
                implementation_effort="EASY",
            ),
            CostOptimization(
                service="RDS",
                resource_id="db-unused-test",
                recommendation_type="Idle Resource",
                current_cost=156.00,
                potential_savings=156.00,
                description="Unused db.t3.medium instance with no connections in 30 days",
                priority="HIGH",
                implementation_effort="MODERATE",
            ),
            CostOptimization(
                service="Elastic IP",
                resource_id="eipalloc-12345",
                recommendation_type="Unassociated IP",
                current_cost=43.80,
                potential_savings=43.80,
                description="Elastic IP not attached to any running instance",
                priority="MEDIUM",
                implementation_effort="EASY",
            ),
        ]

    def identify_right_sizing_opportunities(self) -> List[CostOptimization]:
        """Generate mock right-sizing recommendations."""
        return [
            CostOptimization(
                service="EC2",
                resource_id="i-web-server-01",
                recommendation_type="Right-Sizing",
                current_cost=292.00,
                potential_savings=146.00,
                description="m5.xlarge averaging 8% CPU. Downsize to m5.large",
                priority="HIGH",
                implementation_effort="MODERATE",
            ),
            CostOptimization(
                service="EC2",
                resource_id="i-api-server-02",
                recommendation_type="Right-Sizing",
                current_cost=140.00,
                potential_savings=70.00,
                description="m5.large averaging 12% CPU. Consider t3.large",
                priority="MEDIUM",
                implementation_effort="MODERATE",
            ),
            CostOptimization(
                service="RDS",
                resource_id="db-production",
                recommendation_type="Right-Sizing",
                current_cost=456.00,
                potential_savings=228.00,
                description="db.r5.xlarge averaging 15% CPU. Consider db.r5.large",
                priority="HIGH",
                implementation_effort="COMPLEX",
            ),
        ]

    def get_reserved_instance_recommendations(self) -> List[Dict]:
        """Generate mock RI recommendations."""
        return [
            {
                "InstanceType": "m5.large",
                "AccountScope": "PAYER",
                "LookbackPeriodInDays": 60,
                "PaymentOption": "ALL_UPFRONT",
                "TermInYears": 1,
                "SavingsPercentage": 42,
                "EstimatedMonthlySavings": 84.00,
                "UpfrontCost": 840.00,
            },
            {
                "InstanceType": "c5.xlarge",
                "AccountScope": "PAYER",
                "LookbackPeriodInDays": 60,
                "PaymentOption": "PARTIAL_UPFRONT",
                "TermInYears": 1,
                "SavingsPercentage": 38,
                "EstimatedMonthlySavings": 76.00,
                "UpfrontCost": 456.00,
            },
        ]

    def get_savings_plans_recommendations(self) -> List[Dict]:
        """Generate mock Savings Plans recommendations."""
        return [
            {
                "SavingsPlansType": "COMPUTE_SP",
                "PaymentOption": "ALL_UPFRONT",
                "TermInYears": 1,
                "SavingsPercentage": 35,
                "EstimatedMonthlySavings": 210.00,
                "HourlyCommitment": 1.50,
                "UpfrontCost": 1095.00,
            }
        ]

    def get_cost_anomaly_detection(self) -> List[Dict]:
        """Generate mock anomaly detection results."""
        return [
            {
                "date": "2026-03-10",
                "cost": 892.45,
                "expected_range": "$525.00 ± $105.00",
                "deviation_percentage": 69.9,
                "severity": "HIGH",
            },
            {
                "date": "2026-03-12",
                "cost": 678.23,
                "expected_range": "$525.00 ± $105.00",
                "deviation_percentage": 29.2,
                "severity": "MEDIUM",
            },
        ]

    def simulate_budget_alerts(self, budgets: List[Dict]) -> List[BudgetAlert]:
        """Simulate budget alerts with mock data."""
        alerts = []

        for budget, (current_ratio, forecast_ratio) in zip(
            budgets, _expand_mock_budget_ratios(len(budgets))
        ):
            limit = budget["limit"]
            threshold_percentage = current_ratio * 100
            forecast_percentage = forecast_ratio * 100
            alerts.append(
                BudgetAlert(
                    budget_name=budget["name"],
                    limit=limit,
                    current_spend=round(limit * current_ratio, 2),
                    forecasted_spend=round(limit * forecast_ratio, 2),
                    threshold_percentage=round(threshold_percentage, 2),
                    alert_status=_resolve_budget_status(
                        threshold_percentage=threshold_percentage,
                        forecast_percentage=forecast_percentage,
                    ),
                )
            )

        return alerts

    def export_costs_to_csv(
        self, service_costs: List[ServiceCost], output_path: str
    ) -> None:
        """Export costs to CSV."""
        _write_service_costs_to_csv(service_costs, output_path)


def get_analyzer(use_mock: bool = True, profile_name: Optional[str] = None) -> object:
    """
    Factory function to get appropriate analyzer.

    Args:
        use_mock: If True, returns MockCostAnalyzer for demo
        profile_name: AWS profile name (only used if use_mock=False)

    Returns:
        CostAnalyzer instance
    """
    if use_mock:
        return MockCostAnalyzer()
    return AWSCostAnalyzer(profile_name=profile_name)


def _write_service_costs_to_csv(
    service_costs: List[ServiceCost], output_path: str
) -> None:
    """Persist service costs using a consistent CSV schema."""
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=SERVICE_COST_CSV_FIELDS)
        writer.writeheader()
        for service_cost in service_costs:
            writer.writerow(service_cost.to_dict())


def _resolve_budget_status(
    threshold_percentage: float, forecast_percentage: float
) -> str:
    """Return the budget status for current and forecast spend."""
    if threshold_percentage >= 100 or forecast_percentage >= 100:
        return "CRITICAL"
    if threshold_percentage >= 80 or forecast_percentage >= 90:
        return "WARNING"
    return "OK"


def _expand_mock_budget_ratios(count: int) -> List[tuple[float, float]]:
    """Return enough mock spend profiles for the requested budget count."""
    if count <= len(MOCK_BUDGET_SPEND_RATIOS):
        return list(MOCK_BUDGET_SPEND_RATIOS[:count])

    ratios = list(MOCK_BUDGET_SPEND_RATIOS)
    while len(ratios) < count:
        ratios.append(MOCK_BUDGET_SPEND_RATIOS[-1])
    return ratios
