#!/usr/bin/env python3
"""
New Relic APM Health Assessment Tool — CLI Entry Point.

Production CLI orchestrator that runs the full health assessment workflow:
1. Load configuration (multi-profile: dev/prod)
2. Fetch metrics from New Relic API (or load from cached JSON)
3. Calculate weighted health score (0-100)
4. Generate and save markdown report

Usage:
    python main.py                              # Default: dev profile, 1 day
    python main.py --days 7 --profile prod      # Prod profile, 7-day window
    python main.py --from-file data/app-1d.json # Analyze cached data offline
    python main.py --validate-config            # Validate config and exit
    python main.py --no-cache                   # Skip saving data to cache
    python main.py --output-dir ./out           # Custom report output directory
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _EST = ZoneInfo("America/New_York")
except Exception:
    _EST = timezone(timedelta(hours=-5))

from modules.config_loader import load_config
from modules.api_client import ApiClient
from modules.health_calculator import HealthCalculator
from modules.report_generator import ReportGenerator

DATA_DIR = "data"
REPORTS_DIR = "reports"

logger = logging.getLogger("main")


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="New Relic APM Health Assessment Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --days 7 --profile prod\n"
            "  python main.py --from-file data/PROD_TMS-1d-2026-03-06.json\n"
            "  python main.py --validate-config --profile prod\n"
        ),
    )
    parser.add_argument(
        "--days", type=int, default=1, choices=[1, 3, 7, 14, 30],
        help="Time window in days (default: 1)",
    )
    parser.add_argument(
        "--profile", type=str, default="dev",
        help="Config profile: dev or prod (default: dev)",
    )
    parser.add_argument(
        "--from-file", type=str, default=None, dest="from_file",
        help="Path to a cached JSON data file to analyze offline (skip API fetch)",
    )
    parser.add_argument(
        "--no-cache", action="store_true", dest="no_cache",
        help="Skip saving fetched data to the data/ cache directory",
    )
    parser.add_argument(
        "--output-dir", type=str, default=REPORTS_DIR, dest="output_dir",
        help=f"Directory for generated reports (default: {REPORTS_DIR})",
    )
    parser.add_argument(
        "--validate-config", action="store_true", dest="validate_config",
        help="Validate configuration and exit without running assessment",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose/debug logging output",
    )
    return parser.parse_args(argv)


def _setup_logging(verbose: bool = False):
    """Configure root logging level."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _safe_fetch(label, fetch_fn, default):
    """Fetch enrichment data; return default on failure instead of aborting."""
    print(f"  - {label}")
    try:
        return fetch_fn()
    except Exception as e:
        print(f"    ⚠ Skipped ({e})")
        return default


def _load_data_from_file(filepath: str) -> dict:
    """Load previously cached JSON data for offline analysis."""
    if not os.path.isfile(filepath):
        print(f"✗ File not found: {filepath}")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"✓ Loaded cached data from {filepath}")
    return data


def _fetch_all_metrics(api_client: ApiClient, app_id: str, days: int, app_name: str) -> dict:
    """Fetch all metric categories from New Relic API."""
    print("  (This may take 1-3 minutes for comprehensive data collection...)")

    collection_start = datetime.now(_EST)

    # Core metrics (failures here are fatal)
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

    # Enrichment data (failures are non-fatal)
    error_details_data = _safe_fetch(
        "Fetching error details with stack traces...",
        lambda: api_client.fetch_error_details(app_id, days),
        {"error_details": []})

    slow_transactions_data = _safe_fetch(
        "Fetching slow transaction breakdown (top 20)...",
        lambda: api_client.fetch_slow_transactions(app_id, days),
        {"slow_transactions": []})

    database_details_data = _safe_fetch(
        "Fetching database query details...",
        lambda: api_client.fetch_database_details(app_id, days),
        {"database_details": []})

    slow_db_transactions_data = _safe_fetch(
        "Fetching top-20 slowest database transactions...",
        lambda: api_client.fetch_slow_db_transactions(app_id, days),
        {"slow_db_transactions": []})

    external_services_data = _safe_fetch(
        "Fetching external service breakdown...",
        lambda: api_client.fetch_external_services(app_id, days),
        {"external_services": []})

    application_logs_data = _safe_fetch(
        "Fetching application logs (errors/warnings/exceptions)...",
        lambda: api_client.fetch_application_logs(app_id, days, app_name=app_name),
        {"application_logs": []})

    log_volume_data = _safe_fetch(
        "Fetching log volume by level...",
        lambda: api_client.fetch_log_volume(app_id, days, app_name=app_name),
        {"log_volume": []})

    alerts_data = _safe_fetch(
        "Fetching alert/incident history...",
        lambda: api_client.fetch_alerts(app_id, days, app_name=app_name),
        {"alerts": []})

    hourly_trends_data = _safe_fetch(
        "Fetching hourly performance trends...",
        lambda: api_client.fetch_hourly_trends(app_id, days),
        {"hourly_trends": []})

    baselines_data = _safe_fetch(
        "Fetching 7-day baselines...",
        lambda: api_client.fetch_baselines(app_id),
        {"baselines": {}})

    deployments_data = _safe_fetch(
        "Fetching deployment markers...",
        lambda: api_client.fetch_deployments(app_id, days, app_name=app_name),
        {"deployments": []})

    collection_end = datetime.now(_EST)

    all_data = {
        "app_id": app_id,
        "app_name": app_name,
        "days": days,
        "collected_at": datetime.now(_EST).isoformat(),
        "collection_start": collection_start.isoformat(),
        "collection_end": collection_end.isoformat(),
        "performance": performance_data,
        "errors": error_data,
        "infrastructure": infrastructure_data,
        "database": database_data,
        "transactions": api_data,
        "error_details": error_details_data,
        "slow_transactions": slow_transactions_data,
        "database_details": database_details_data,
        "slow_db_transactions": slow_db_transactions_data,
        "external_services": external_services_data,
        "application_logs": application_logs_data,
        "log_volume": log_volume_data,
        "alerts": alerts_data,
        "hourly_trends": hourly_trends_data,
        "baselines": baselines_data,
        "deployments": deployments_data,
    }

    return all_data


def _flatten_metrics(all_data: dict) -> dict:
    """Flatten nested metric dicts into a single dict for HealthCalculator."""
    metrics = {}
    for key in ("performance", "errors", "infrastructure", "database", "transactions"):
        nested = all_data.get(key, {})
        # Unwrap one level if the key contains a sub-dict with same name
        if isinstance(nested, dict) and key in nested:
            nested = nested[key]
        metrics.update(nested)
    return metrics


def main(argv=None):
    """Run a complete health assessment."""
    args = parse_args(argv)
    _setup_logging(args.verbose)

    print("=" * 70)
    print("New Relic APM Health Assessment Tool")
    print("=" * 70)
    print()

    # ── Step 1: Load configuration ──────────────────────────────────────
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
        print("Please ensure your config file exists:")
        print(f"  .newrelic_config.{args.profile}.json")
        print()
        print("Required fields: api_key, account_id, app_ids")
        sys.exit(1)

    # ── Validate-only mode ──────────────────────────────────────────────
    if args.validate_config:
        print("✓ Configuration is valid.")
        sys.exit(0)

    app_id = config["app_ids"][0]
    app_name = config.get("app_name", f"app-{app_id}")
    days = config.get("days", 1)

    # ── Step 2: Get data (from file or API) ─────────────────────────────
    collection_start = None
    collection_end = None

    if args.from_file:
        print(f"Step 2: Loading data from file...")
        all_data = _load_data_from_file(args.from_file)
        app_name = all_data.get("app_name", app_name)
        days = all_data.get("days", days)
        print()
    else:
        print("Step 2: Connecting to New Relic API...")
        api_client = ApiClient(
            api_key=config["api_key"],
            account_id=config["account_id"],
            timeout=config.get("timeout", 30),
            max_retries=config.get("max_retries", 2),
        )
        print(f"✓ API client initialized")
        print(f"  - App ID: {app_id}")
        print(f"  - Time period: Last {days} day(s)")
        print()

        print("Step 3: Fetching metrics from New Relic...")
        try:
            all_data = _fetch_all_metrics(api_client, app_id, days, app_name)
            collection_start = datetime.fromisoformat(all_data["collection_start"])
            collection_end = datetime.fromisoformat(all_data["collection_end"])
        except Exception as e:
            print(f"✗ API error: {e}")
            print()
            print("Common issues:")
            print("  - Invalid API key (check config file)")
            print("  - Invalid account ID or app ID")
            print("  - Network connectivity issues")
            sys.exit(1)

        # Save to cache
        if not args.no_cache:
            os.makedirs(DATA_DIR, exist_ok=True)
            cache_ts = datetime.now(_EST).strftime("%Y-%m-%d-%H%M%S")
            cache_file = os.path.join(DATA_DIR, f"{app_name}-{days}d-{cache_ts}.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2)
            print(f"✓ Data saved to {cache_file}")
        print()

    # ── Step 4: Calculate health score ──────────────────────────────────
    step = "Step 3" if args.from_file else "Step 4"
    print(f"{step}: Calculating health score...")
    calculator = HealthCalculator()
    flat_metrics = _flatten_metrics(all_data)
    health_data = calculator.calculate_health_score(flat_metrics)

    print(f"✓ Health score: {health_data['overall_score']}/100")
    print(f"  - Status: {health_data['status']}")
    critical_count = sum(1 for f in health_data["findings"] if f["severity"] == "Critical")
    print(f"  - Critical Issues: {critical_count}")
    print()

    # ── Step 5: Generate report ─────────────────────────────────────────
    step = "Step 4" if args.from_file else "Step 5"
    print(f"{step}: Generating health report...")
    generator = ReportGenerator()

    report_config = {
        "app_name": app_name,
        "account_id": config["account_id"],
        "app_id": app_id,
        "days": days,
    }

    report = generator.generate_report(
        health_data, app_id, report_config, metrics=all_data,
        collection_start=collection_start, collection_end=collection_end,
    )
    print(f"✓ Report generated ({len(report)} characters)")
    print()

    # ── Step 6: Save report ─────────────────────────────────────────────
    step = "Step 5" if args.from_file else "Step 6"
    print(f"{step}: Saving report...")
    filepath = generator.save_report(report, app_id=app_name, reports_dir=args.output_dir)
    print()

    # ── Summary ─────────────────────────────────────────────────────────
    print("=" * 70)
    print("Assessment Complete!")
    print("=" * 70)
    print(f"Health Score: {health_data['overall_score']}/100 ({health_data['status']})")
    print(f"Report saved: {filepath}")
    print()
    print("Next steps:")
    print("  1. Open the report in VS Code to review findings")
    print("  2. Use @analysis-agent in Copilot Chat for deep-dive analysis")
    print("  3. Use @recommend-agent for AI-powered code fix recommendations")
    print()

    return health_data["overall_score"]


if __name__ == "__main__":
    main()
