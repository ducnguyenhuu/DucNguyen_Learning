#!/usr/bin/env python3
"""
Demo / legacy entry point for the AI Log Analysis tool.

Preferred entry point: python main.py (see main.py for full CLI options).

This script is kept for backward compatibility and delegates
the same end-to-end workflow as main.py:
1. Load configuration
2. Fetch data from New Relic API
3. Calculate health score
4. Generate and save report

Usage:
    python demo.py [--days DAYS] [--profile PROFILE]

    --days     Time window in days (1, 3, 7, 14, 30). Default: 1
    --profile  Config profile to use (dev, prod).    Default: dev

For additional CLI options (--from-file, --no-cache, --validate-config, etc.),
use ``python main.py --help``.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    _EST = ZoneInfo("America/New_York")
except Exception:
    # Fallback when tzdata is not installed (Windows without tzdata package)
    _EST = timezone(timedelta(hours=-5))
from modules.config_loader import load_config
from modules.api_client import ApiClient
from modules.health_calculator import HealthCalculator
from modules.report_generator import ReportGenerator

DATA_DIR = "data"


def parse_args():
    parser = argparse.ArgumentParser(description="New Relic Health Assessment")
    parser.add_argument(
        "--days", type=int, default=1, choices=[1, 3, 7, 14, 30],
        help="Time window in days (default: 1)"
    )
    parser.add_argument(
        "--profile", type=str, default="dev",
        help="Config profile to use: dev or prod (default: dev)"
    )
    return parser.parse_args()


def main():
    """Run a complete health assessment."""
    args = parse_args()

    print("=" * 70)
    print("AI-Powered Log Analysis - New Relic Health Assessment")
    print("=" * 70)
    print()

    # Step 1: Load configuration
    print("Step 1: Loading configuration...")
    try:
        config = load_config(profile=args.profile, days=args.days)
        print(f"✓ Configuration loaded successfully")
        print(f"  - Profile: {args.profile}")
        print(f"  - Account ID: {config['account_id']}")
        print(f"  - App IDs: {config['app_ids']}")
        print()
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        print()
        print("Please edit .newrelic_config.dev.json and add your New Relic credentials:")
        print("  1. Get API Key: New Relic → Account Settings → API Keys → User Key")
        print("  2. Get Account ID: New Relic → Account Settings → Account Information")
        print("  3. Get App ID: New Relic → APM → Select your app → Settings → Application")
        sys.exit(1)

    # Step 2: Initialize API client
    print("Step 2: Connecting to New Relic API...")
    api_client = ApiClient(
        api_key=config['api_key'],
        account_id=config['account_id'],
        timeout=config.get('timeout', 30),
        max_retries=config.get('max_retries', 2)
    )

    # Use the first app ID from config
    app_id = config['app_ids'][0]
    app_name = config.get('app_name', f'app-{app_id}')
    days = config.get('days', 1)

    print(f"✓ API client initialized")
    print(f"  - App ID: {app_id}")
    print(f"  - Time period: Last {days} day(s)")
    print()

    # Step 3: Fetch data from New Relic
    print("Step 3: Fetching metrics from New Relic...")
    print("  (This may take 1-3 minutes for comprehensive data collection...)")
    try:
        # Core metrics
        collection_start = datetime.now(_EST)
        print("  - Fetching performance metrics (P50/P95/P99, Apdex, throughput)...")
        performance_data = api_client.fetch_performance_metrics(app_id, days)

        print("  - Fetching error metrics...")
        error_data = api_client.fetch_error_metrics(app_id, days)

        print("  - Fetching infrastructure metrics...")
        infrastructure_data = api_client.fetch_infrastructure_metrics(app_id, days, app_name=app_name)

        print("  - Fetching database metrics...")
        database_data = api_client.fetch_database_metrics(app_id, days)

        print("  - Fetching API/transaction metrics...")
        api_data = api_client.fetch_transaction_metrics(app_id, days)

        # Detailed breakdowns — each is enrichment data, so failures are non-fatal
        def _safe_fetch(label, fetch_fn, default):
            """Fetch enrichment data; return default on failure instead of aborting."""
            print(f"  - {label}")
            try:
                return fetch_fn()
            except Exception as e:
                print(f"    ⚠ Skipped ({e})")
                return default

        error_details_data = _safe_fetch(
            "Fetching error details with stack traces...",
            lambda: api_client.fetch_error_details(app_id, days),
            {'error_details': []})

        slow_transactions_data = _safe_fetch(
            "Fetching slow transaction breakdown (top 20)...",
            lambda: api_client.fetch_slow_transactions(app_id, days),
            {'slow_transactions': []})

        database_details_data = _safe_fetch(
            "Fetching database query details...",
            lambda: api_client.fetch_database_details(app_id, days),
            {'database_details': []})

        slow_db_transactions_data = _safe_fetch(
            "Fetching top-20 slowest database transactions...",
            lambda: api_client.fetch_slow_db_transactions(app_id, days),
            {'slow_db_transactions': []})

        external_services_data = _safe_fetch(
            "Fetching external service breakdown...",
            lambda: api_client.fetch_external_services(app_id, days),
            {'external_services': []})

        # Logs
        application_logs_data = _safe_fetch(
            "Fetching application logs (errors/warnings/exceptions)...",
            lambda: api_client.fetch_application_logs(app_id, days, app_name=app_name),
            {'application_logs': []})

        log_volume_data = _safe_fetch(
            "Fetching log volume by level...",
            lambda: api_client.fetch_log_volume(app_id, days, app_name=app_name),
            {'log_volume': []})

        # Context data
        alerts_data = _safe_fetch(
            "Fetching alert/incident history...",
            lambda: api_client.fetch_alerts(app_id, days, app_name=app_name),
            {'alerts': []})

        hourly_trends_data = _safe_fetch(
            "Fetching hourly performance trends...",
            lambda: api_client.fetch_hourly_trends(app_id, days),
            {'hourly_trends': []})

        baselines_data = _safe_fetch(
            "Fetching 7-day baselines...",
            lambda: api_client.fetch_baselines(app_id),
            {'baselines': {}})

        deployments_data = _safe_fetch(
            "Fetching deployment markers...",
            lambda: api_client.fetch_deployments(app_id, days, app_name=app_name),
            {'deployments': []})
        collection_end = datetime.now(_EST)

        # Save raw data to data/ folder
        os.makedirs(DATA_DIR, exist_ok=True)
        cache_ts = datetime.now(_EST).strftime("%Y-%m-%d-%H%M%S")
        cache_file = os.path.join(DATA_DIR, f"{app_name}-{days}d-{cache_ts}.json")
        
        all_data = {
            'app_id': app_id,
            'app_name': app_name,
            'days': days,
            'collected_at': datetime.now(_EST).isoformat(),
            'performance': performance_data,
            'errors': error_data,
            'infrastructure': infrastructure_data,
            'database': database_data,
            'transactions': api_data,
            'error_details': error_details_data,
            'slow_transactions': slow_transactions_data,
            'database_details': database_details_data,
            'slow_db_transactions': slow_db_transactions_data,
            'external_services': external_services_data,
            'application_logs': application_logs_data,
            'log_volume': log_volume_data,
            'alerts': alerts_data,
            'hourly_trends': hourly_trends_data,
            'baselines': baselines_data,
            'deployments': deployments_data
        }
        
        with open(cache_file, 'w') as f:
            json.dump(all_data, f, indent=2)

        print(f"✓ Data fetched and saved to {cache_file}")
        print()
    except Exception as e:
        print(f"✗ API error: {e}")
        print()
        print("Common issues:")
        print("  - Invalid API key (check .newrelic_config.dev.json)")
        print("  - Invalid account ID or app ID")
        print("  - Network connectivity issues")
        print("  - New Relic API rate limits")
        sys.exit(1)

    # Step 4: Calculate health score
    print("Step 4: Calculating health score...")
    calculator = HealthCalculator()

    # Flatten all nested metric dicts into a single flat dict for health_calculator
    metrics = {}
    metrics.update(performance_data.get('performance', {}))
    metrics.update(error_data.get('errors', {}))
    metrics.update(infrastructure_data.get('infrastructure', {}))
    metrics.update(database_data.get('database', {}))
    metrics.update(api_data.get('transactions', {}))

    health_data = calculator.calculate_health_score(metrics)

    print(f"✓ Health score calculated: {health_data['overall_score']}/100")
    print(f"  - Status: {health_data['status']}")
    critical_count = sum(1 for f in health_data['findings'] if f['severity'] == 'Critical')
    print(f"  - Critical Issues: {critical_count}")
    print()

    # Step 5: Generate report
    print("Step 5: Generating health report...")
    generator = ReportGenerator()

    report_config = {
        'app_name': app_name,
        'account_id': config['account_id'],
        'app_id': app_id,
        'days': days
    }

    # Pass full metrics dict for detailed report sections
    report = generator.generate_report(
        health_data, app_id, report_config, metrics=all_data,
        collection_start=collection_start, collection_end=collection_end
    )
    print(f"✓ Report generated ({len(report)} characters)")
    print()

    # Step 6: Save report
    print("Step 6: Saving report to disk...")
    filepath = generator.save_report(report, app_id=app_name)
    print()

    # Summary
    print("=" * 70)
    print("Assessment Complete!")
    print("=" * 70)
    print(f"Health Score: {health_data['overall_score']}/100 ({health_data['status']})")
    print(f"Data saved:   {cache_file}")
    print(f"Report saved: {filepath}")
    print()
    print("Next steps:")
    print("  1. Open the report in VS Code to review findings")
    print("  2. Run @recommend-agent in GitHub Copilot Chat for AI-powered recommendations")
    print("  3. Implement recommended fixes")
    print()


if __name__ == '__main__':
    main()
