"""
Report Generation Module for AI Log Analysis System.

This module generates executive-ready markdown reports with health assessments,
metric breakdowns, and actionable findings.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    _EST = ZoneInfo("America/New_York")
except Exception:
    # Fallback when tzdata is not installed (Windows without tzdata package)
    _EST = timezone(timedelta(hours=-5))
from typing import Dict, Any, Optional

# Configure module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ReportGenerator:
    """
    Generates health assessment reports in markdown format.
    
    The ReportGenerator creates professional, executive-ready reports that include:
    - Executive summary with overall health score
    - Assessment metadata and data collection information
    - Detailed metric breakdowns by category (generated in subsequent stories)
    - Findings and recommendations (generated in subsequent stories)
    """
    
    def __init__(self):
        """Initialize the ReportGenerator."""
        logger.debug("[DEBUG] [report_generator] ReportGenerator initialized")
    
    def generate_report(
        self,
        health_data: Dict[str, Any],
        app_id: str,
        config: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None,
        collection_start: Optional[datetime] = None,
        collection_end: Optional[datetime] = None,
        cache_age: Optional[int] = None
    ) -> str:
        """
        Generate a comprehensive health assessment report in markdown format.
        
        Args:
            health_data: Health scoring results from HealthCalculator.calculate_health_score()
                Expected keys: overall_score, status, status_emoji, category_scores, findings
            app_id: New Relic application ID or name
            config: Configuration dictionary containing:
                - new_relic.account_id: New Relic account ID
                - new_relic.api_key: API key (not included in report)
                - days: Assessment period in days
            metrics: Optional raw metrics dictionary from ApiClient
            collection_start: Optional data collection start timestamp
            collection_end: Optional data collection end timestamp
            cache_age: Optional age of cached data in seconds (None = fresh data)
        
        Returns:
            Markdown-formatted report string
        
        Raises:
            ValueError: If required fields are missing from health_data or config
        """
        logger.info(f"[INFO] [report_generator] Generating health report for app: {app_id}")
        
        # Validate required fields
        self._validate_inputs(health_data, config)
        
        # Build report sections
        report_sections = []
        
        # Header and executive summary
        report_sections.append(self._generate_header(app_id))
        report_sections.append(self._generate_executive_summary(
            health_data, config, collection_start, collection_end
        ))
        report_sections.append(self._generate_metadata_section(
            app_id, config, collection_start, collection_end, cache_age
        ))
        
        # Metric breakdown sections (if metrics provided)
        if metrics:
            logger.debug("[DEBUG] [report_generator] Generating metric breakdown sections")
            category_scores = health_data.get('category_scores', {})
            
            report_sections.append(self._generate_performance_section(metrics, category_scores))
            report_sections.append(self._generate_error_section(metrics, category_scores))
            report_sections.append(self._generate_infrastructure_section(metrics, category_scores))
            report_sections.append(self._generate_database_section(metrics, category_scores))
            report_sections.append(self._generate_api_section(metrics, category_scores))
            
            # Enriched data sections (only rendered if data exists)
            for section_gen in [
                self._generate_slow_transactions_section,
                self._generate_slow_db_transactions_section,
                self._generate_external_services_section,
                self._generate_baselines_section,
                self._generate_logs_section,
                self._generate_alerts_section,
                self._generate_trends_section,
                self._generate_deployments_section,
            ]:
                section_content = section_gen(metrics)
                if section_content:
                    report_sections.append(section_content)
        
        # Findings and recommendations sections
        findings = health_data.get('findings', [])
        report_sections.append(self._generate_findings_section(findings))
        report_sections.append(self._generate_recommendations_section())
        
        # Combine all sections
        report = "\n\n".join(report_sections)
        
        logger.info("[INFO] [report_generator] Health report generated successfully")
        logger.debug(f"[DEBUG] [report_generator] Report length: {len(report)} characters")
        
        return report
    
    def _validate_inputs(self, health_data: Dict[str, Any], config: Dict[str, Any]) -> None:
        """
        Validate that required fields are present in inputs.
        
        Args:
            health_data: Health scoring results dictionary
            config: Configuration dictionary
        
        Raises:
            ValueError: If required fields are missing
        """
        # Validate health_data
        required_health_fields = ["overall_score", "status", "status_emoji", "findings"]
        missing_fields = [f for f in required_health_fields if f not in health_data]
        if missing_fields:
            raise ValueError(f"Missing required health_data fields: {missing_fields}")
        
        # Validate config
        if "days" not in config:
            raise ValueError("Missing required config field: days")
        
        logger.debug("[DEBUG] [report_generator] Input validation passed")
    
    def _generate_header(self, app_id: str) -> str:
        """
        Generate report header with application name.
        
        Args:
            app_id: Application identifier
        
        Returns:
            Markdown header string
        """
        header = f"# Health Assessment: {app_id}"
        logger.debug(f"[DEBUG] [report_generator] Generated header for app: {app_id}")
        return header
    
    def _generate_executive_summary(
        self,
        health_data: Dict[str, Any],
        config: Dict[str, Any],
        collection_start: Optional[datetime],
        collection_end: Optional[datetime]
    ) -> str:
        """
        Generate executive summary section with key health metrics.
        
        Args:
            health_data: Health scoring results
            config: Configuration with assessment period
            collection_start: Data collection start time
            collection_end: Data collection end time
        
        Returns:
            Markdown-formatted executive summary
        """
        logger.debug("[DEBUG] [report_generator] Generating executive summary")
        
        overall_score = health_data["overall_score"]
        status = health_data["status"]
        status_emoji = health_data["status_emoji"]
        findings = health_data["findings"]
        days = config.get("days", 7)
        
        # Count critical issues
        critical_count = sum(1 for f in findings if f.get("severity") == "Critical")
        
        # Format assessment period
        if collection_start and collection_end:
            start_date = collection_start.strftime("%Y-%m-%d")
            end_date = collection_end.strftime("%Y-%m-%d")
            period_text = f"{days} days ({start_date} to {end_date})"
        else:
            period_text = f"{days} days"
        
        # Build executive summary
        summary_lines = [
            "## Executive Summary",
            "",
            f"**Overall Health Score:** {overall_score}/100 {status_emoji} {status}",
            "",
            f"**Assessment Period:** {period_text}",
            "",
            f"**Critical Issues Found:** {critical_count}"
        ]
        
        summary = "\n".join(summary_lines)
        logger.debug(f"[DEBUG] [report_generator] Executive summary: Score={overall_score}, Status={status}, Critical={critical_count}")
        
        return summary
    
    def _generate_metadata_section(
        self,
        app_id: str,
        config: Dict[str, Any],
        collection_start: Optional[datetime],
        collection_end: Optional[datetime],
        cache_age: Optional[int]
    ) -> str:
        """
        Generate report metadata section with assessment details.
        
        Args:
            app_id: Application identifier
            config: Configuration dictionary
            collection_start: Data collection start time
            collection_end: Data collection end time
            cache_age: Age of cached data in seconds (None = fresh)
        
        Returns:
            Markdown-formatted metadata section
        """
        logger.debug("[DEBUG] [report_generator] Generating metadata section")
        
        # Get configuration values — support both flat and nested account_id
        account_id = (
            config.get("new_relic", {}).get("account_id")
            or config.get("account_id", "N/A")
        )
        
        # Generate assessment timestamp (current time)
        assessment_timestamp = datetime.now(_EST).strftime("%Y-%m-%dT%H:%M:%S %Z")
        
        # Calculate data collection duration
        if collection_start and collection_end:
            duration_seconds = (collection_end - collection_start).total_seconds()
            duration_minutes = int(duration_seconds / 60)
            duration_text = f"{duration_minutes} minutes" if duration_minutes > 0 else f"{int(duration_seconds)} seconds"
        else:
            duration_text = "N/A"
        
        # Determine cache status
        if cache_age is None:
            cache_status = "Fresh data (collected on-demand)"
        elif cache_age < 60:
            cache_status = f"Cached data ({cache_age} seconds old)"
        elif cache_age < 3600:
            cache_minutes = int(cache_age / 60)
            cache_status = f"Cached data ({cache_minutes} minutes old)"
        else:
            cache_hours = int(cache_age / 3600)
            cache_status = f"Cached data ({cache_hours} hours old)"
        
        # Build metadata section
        metadata_lines = [
            "## Assessment Metadata",
            "",
            f"- **New Relic Account ID:** {account_id}",
            f"- **Application ID:** {app_id}",
            f"- **Assessment Timestamp:** {assessment_timestamp}",
            f"- **Data Collection Duration:** {duration_text}",
            f"- **Cache Status:** {cache_status}"
        ]
        
        metadata = "\n".join(metadata_lines)
        logger.debug(f"[DEBUG] [report_generator] Metadata: account={account_id}, app={app_id}, duration={duration_text}")
        
        return metadata
    
    def _generate_performance_section(
        self,
        metrics: Dict[str, Any],
        category_scores: Dict[str, int]
    ) -> str:
        """
        Generate performance metrics section.
        
        Args:
            metrics: Raw metrics dictionary from ApiClient
            category_scores: Category scores from health_data
        
        Returns:
            Markdown-formatted performance section
        """
        logger.debug("[DEBUG] [report_generator] Generating performance section")
        
        # Get performance score and emoji
        score = category_scores.get('performance', 0)
        emoji = self._get_score_emoji(score)
        
        # Get performance metrics
        perf = metrics.get('performance', {})
        if isinstance(perf, dict) and 'performance' in perf:
            perf = perf['performance']
        response_time = perf.get('response_time')
        p50 = perf.get('p50_ms')
        p90 = perf.get('p90_ms')
        p95 = perf.get('p95_ms')
        p99 = perf.get('p99_ms')
        throughput = perf.get('throughput')
        total_requests = perf.get('total_requests')
        apdex = perf.get('apdex_score')
        apdex_satisfied = perf.get('apdex_satisfied')
        apdex_tolerating = perf.get('apdex_tolerating')
        apdex_frustrated = perf.get('apdex_frustrated')
        availability = perf.get('availability')
        instance_count = perf.get('instance_count')
        db_time = perf.get('db_time_ms')
        ext_time = perf.get('ext_time_ms')
        app_time = perf.get('app_time_ms')
        queue_time = perf.get('queue_time_ms')
        
        # Build section
        section = f"## Performance Metrics (Score: {score}/100 {emoji})\n\n"

        # Availability / SLA
        if availability is not None:
            avail_indicator = "🟢" if availability >= 99.9 else "🟡" if availability >= 99 else "🔴"
            section += f"- **Availability:** {availability:.3f}% {avail_indicator}\n"

        # Instance count
        if instance_count is not None:
            section += f"- **Instances:** {instance_count}\n"
        
        # Response time with percentiles
        if response_time is not None:
            rt_indicator = "🟢" if response_time < 500 else "🟠" if response_time < 1000 else "🔴"
            section += f"- **Average Response Time:** {response_time:.0f} ms {rt_indicator}\n"
            if p50 is not None:
                section += f"- **P50 Response Time:** {p50:.0f} ms\n"
            if p90 is not None:
                p90_indicator = "🟢" if p90 < 500 else "🟠" if p90 < 1500 else "🔴"
                section += f"- **P90 Response Time:** {p90:.0f} ms {p90_indicator}\n"
            if p95 is not None:
                p95_indicator = "🟢" if p95 < 1000 else "🟠" if p95 < 2000 else "🔴"
                section += f"- **P95 Response Time:** {p95:.0f} ms {p95_indicator}\n"
            if p99 is not None:
                section += f"- **P99 Response Time:** {p99:.0f} ms\n"
        else:
            section += "- **Response Time:** N/A\n"
        
        # Throughput
        if throughput is not None:
            section += f"- **Throughput:** {throughput:.1f} rpm"
            if total_requests is not None:
                section += f" ({total_requests:,} total requests)"
            section += "\n"
        else:
            section += "- **Throughput:** N/A\n"
        
        # Apdex score with breakdown
        if apdex is not None:
            apdex_indicator = "🟢" if apdex >= 0.8 else "🟡" if apdex >= 0.5 else "🔴"
            if apdex_satisfied:
                label = f"- **Apdex Score:** {apdex:.2f} {apdex_indicator} (target: >0.8)\n"
                label += f"  - Satisfied: {apdex_satisfied:,} | Tolerating: {apdex_tolerating or 0:,} | Frustrated: {apdex_frustrated or 0:,}\n"
            else:
                label = f"- **Apdex Score:** {apdex:.2f} {apdex_indicator} (estimated, T=0.5s; target: >0.8)\n"
            section += label
        else:
            section += "- **Apdex Score:** N/A\n"

        # Transaction time breakdown — where response time is spent
        if response_time and (db_time is not None or ext_time is not None):
            section += "\n### Response Time Breakdown\n\n"
            section += "| Component | Avg Time (ms) | % of Total |\n"
            section += "|---|---|---|\n"
            components = [
                ("Application Code", app_time),
                ("Database", db_time),
                ("External Services", ext_time),
                ("Request Queue", queue_time),
            ]
            # Use sum of components as denominator so percentages always add to 100%
            comp_total = sum(v for _, v in components if v is not None and v > 0)
            denom = comp_total if comp_total > 0 else 1
            for name, val in components:
                if val is not None:
                    pct = val / denom * 100
                    section += f"| {name} | {val:.0f} | {pct:.0f}% |\n"
        
        return section
    
    def _generate_error_section(
        self,
        metrics: Dict[str, Any],
        category_scores: Dict[str, int]
    ) -> str:
        """
        Generate error metrics section.
        
        Args:
            metrics: Raw metrics dictionary from ApiClient
            category_scores: Category scores from health_data
        
        Returns:
            Markdown-formatted error section
        """
        logger.debug("[DEBUG] [report_generator] Generating error section")
        
        # Get error score and emoji
        score = category_scores.get('errors', 0)
        emoji = self._get_score_emoji(score)
        
        # Get error metrics
        errors = metrics.get('errors', {})
        if isinstance(errors, dict) and 'errors' in errors:
            errors = errors['errors']
        error_rate = errors.get('error_rate')
        error_count = errors.get('error_count')
        total_transactions = errors.get('total_transactions')
        error_types = errors.get('error_types')
        
        # Build section
        section = f"## Error Metrics (Score: {score}/100 {emoji})\n\n"
        
        # Error rate
        if error_rate is not None:
            error_rate_pct = error_rate * 100
            rate_indicator = "🟢" if error_rate < 0.01 else "🟡" if error_rate < 0.05 else "🔴"
            section += f"- **Error Rate:** {error_rate_pct:.2f}% {rate_indicator} (threshold: <1%)\n"
        else:
            section += "- **Error Rate:** N/A\n"
        
        # Total errors
        if error_count is not None:
            section += f"- **Total Errors:** {error_count:,}"
            if total_transactions is not None:
                section += f" out of {total_transactions:,} transactions"
            section += "\n"
        else:
            section += "- **Total Errors:** N/A\n"
        
        # Error types
        if error_types and len(error_types) > 0:
            section += "- **Error Classes:**\n"
            for error_type in error_types[:10]:
                section += f"  - `{error_type}`\n"
        
        # Error details with stack traces (from error_details data)
        error_details = metrics.get('error_details', {})
        if isinstance(error_details, dict):
            error_details = error_details.get('error_details', [])
        if error_details:
            section += "\n### Error Breakdown (by class)\n\n"
            section += "| Error Class | Count | Message |\n"
            section += "|---|---|---|\n"
            for detail in error_details[:15]:
                cls = detail.get('error_class', 'Unknown')
                cnt = detail.get('count', 0)
                msg = detail.get('message', '')
                if msg and len(msg) > 80:
                    msg = msg[:77] + "..."
                section += f"| `{cls}` | {cnt} | {msg} |\n"
            
            # Stack traces for top errors
            top_with_stacks = [d for d in error_details[:5] if d.get('stack_trace')]
            if top_with_stacks:
                section += "\n### Top Error Stack Traces\n\n"
                for detail in top_with_stacks[:3]:
                    section += f"**{detail.get('error_class', 'Unknown')}** ({detail.get('count', 0)} occurrences)\n"
                    section += f"```\n{detail.get('stack_trace', '')[:1500]}\n```\n\n"
        
        return section
    
    def _generate_infrastructure_section(
        self,
        metrics: Dict[str, Any],
        category_scores: Dict[str, int]
    ) -> str:
        """
        Generate infrastructure metrics section.
        
        Args:
            metrics: Raw metrics dictionary from ApiClient
            category_scores: Category scores from health_data
        
        Returns:
            Markdown-formatted infrastructure section
        """
        logger.debug("[DEBUG] [report_generator] Generating infrastructure section")
        
        # Get infrastructure score and emoji
        score = category_scores.get('infrastructure', 0)
        emoji = self._get_score_emoji(score)
        
        # Get infrastructure metrics (unwrap nested fetch response)
        infra = metrics.get('infrastructure', {})
        if isinstance(infra, dict) and 'infrastructure' in infra:
            infra = infra['infrastructure']

        cpu_pct      = infra.get('cpu_percent')
        mem_pct      = infra.get('memory_percent')
        mem_used_gb  = infra.get('memory_used_gb')
        mem_total_gb = infra.get('memory_total_gb')
        disk_pct     = infra.get('disk_percent')
        hostname     = infra.get('host_name')
        instances    = infra.get('instance_count')
        
        # Build section
        section = f"## Infrastructure Metrics (Score: {score}/100 {emoji})\n\n"
        
        # Host info
        if hostname:
            section += f"- **Host:** {hostname}"
            if instances and instances > 1:
                section += f" (+{instances - 1} more)"
            section += "\n"

        # CPU usage (0-100%)
        if cpu_pct is not None:
            cpu_indicator = "🟢" if cpu_pct < 60 else "🟡" if cpu_pct < 80 else "🔴"
            section += f"- **CPU Usage:** {cpu_pct:.1f}% {cpu_indicator} (threshold: <60%)\n"
        else:
            section += "- **CPU Usage:** N/A\n"
        
        # Memory usage (percentage + absolute)
        if mem_pct is not None:
            mem_indicator = "🟢" if mem_pct < 70 else "🟡" if mem_pct < 85 else "🔴"
            mem_detail = f" ({mem_used_gb:.1f} / {mem_total_gb:.1f} GB)" if mem_used_gb and mem_total_gb else ""
            section += f"- **Memory Usage:** {mem_pct:.1f}%{mem_detail} {mem_indicator} (threshold: <70%)\n"
        elif mem_used_gb is not None:
            section += f"- **Memory (Used):** {mem_used_gb:.1f} GB\n"
        else:
            section += "- **Memory Usage:** N/A\n"
        
        # Disk utilization (0-100%)
        if disk_pct is not None:
            disk_indicator = "🟢" if disk_pct < 50 else "🟡" if disk_pct < 80 else "🔴"
            section += f"- **Disk Utilization:** {disk_pct:.1f}% {disk_indicator} (threshold: <50%)\n"
        else:
            section += "- **Disk Utilization:** N/A\n"
        
        return section
    
    def _generate_database_section(
        self,
        metrics: Dict[str, Any],
        category_scores: Dict[str, int]
    ) -> str:
        """
        Generate database metrics section.
        
        Args:
            metrics: Raw metrics dictionary from ApiClient
            category_scores: Category scores from health_data
        
        Returns:
            Markdown-formatted database section
        """
        logger.debug("[DEBUG] [report_generator] Generating database section")
        
        # Get database score and emoji
        score = category_scores.get('database', 0)
        emoji = self._get_score_emoji(score)
        
        # Get database metrics (unwrap nested dict if full fetch response was passed)
        db = metrics.get('database', {})
        if isinstance(db, dict) and 'database' in db:
            db = db['database']
        query_time = db.get('query_time')
        slow_queries = db.get('slow_queries')
        pool_usage = db.get('connection_pool_usage')
        db_calls = db.get('database_calls')
        
        # Build section
        section = f"## Database Metrics (Score: {score}/100 {emoji})\n\n"
        
        # Query time
        if query_time is not None:
            qt_indicator = "🟢" if query_time < 100 else "🔴"
            section += f"- **Average Query Time:** {query_time:.0f} ms {qt_indicator} (threshold: <100ms)\n"
        else:
            section += "- **Average Query Time:** N/A\n"
        
        # Slow queries
        if slow_queries is not None:
            sq_indicator = "🟢" if slow_queries == 0 else "🔴"
            section += f"- **Slow Queries Count:** {slow_queries:,} {sq_indicator}\n"
        else:
            section += "- **Slow Queries Count:** N/A\n"
        
        # Connection pool usage
        if pool_usage is not None:
            pool_pct = pool_usage * 100
            pool_indicator = "🟢" if pool_usage < 0.9 else "🔴"
            section += f"- **Connection Pool Usage:** {pool_pct:.1f}% {pool_indicator} (threshold: <90%)\n"
            if pool_usage >= 0.9:
                section += "  - ⚠️ High pool usage - Consider increasing pool size or investigating connection leaks\n"
        else:
            section += "- **Connection Pool Usage:** N/A\n"
        
        # Database calls
        if db_calls is not None:
            section += f"- **Database Calls:** {db_calls:,.0f}\n"
            if db_calls > 100:
                section += "  - ⚠️ High call count suggests possible N+1 query patterns\n"
        else:
            section += "- **Database Calls:** N/A\n"
        
        # Detailed database breakdown (from database_details data)
        db_details = metrics.get('database_details', {})
        if isinstance(db_details, dict):
            db_details = db_details.get('database_details', [])
        if db_details:
            section += "\n### Top Database Operations (by total time)\n\n"
            section += "| DB | Table / Procedure | Operation | Avg (ms) | P95 (ms) | Calls | Total (s) |\n"
            section += "|---|---|---|---|---|---|---|\n"
            for detail in db_details[:20]:
                ds_type = detail.get('datastore_type', 'N/A')
                table = detail.get('table', 'N/A')
                op = detail.get('operation', 'N/A')
                avg_ms = detail.get('avg_duration_ms')
                p95 = detail.get('p95_ms')
                calls = detail.get('call_count', 0)
                total_ms = detail.get('total_time_ms')
                avg_str = f"{avg_ms:.1f}" if avg_ms is not None else "N/A"
                p95_str = f"{p95:.1f}" if p95 is not None else "N/A"
                total_str = f"{total_ms / 1000:.1f}" if total_ms is not None else "N/A"
                indicator = " 🔴" if avg_ms and avg_ms > 500 else " 🟡" if avg_ms and avg_ms > 100 else ""
                section += f"| {ds_type} | {table} | {op} | {avg_str}{indicator} | {p95_str} | {calls:,} | {total_str} |\n"
        
        return section
    
    def _generate_api_section(
        self,
        metrics: Dict[str, Any],
        category_scores: Dict[str, int]
    ) -> str:
        """
        Generate API/Transaction metrics section.
        
        Args:
            metrics: Raw metrics dictionary from ApiClient
            category_scores: Category scores from health_data
        
        Returns:
            Markdown-formatted API section
        """
        logger.debug("[DEBUG] [report_generator] Generating API/Transaction section")
        
        # Get API score and emoji
        score = category_scores.get('api', 0)
        emoji = self._get_score_emoji(score)
        
        # Get transaction metrics (unwrap nested dict if full fetch response was passed)
        trans = metrics.get('transactions', {})
        if isinstance(trans, dict) and 'transactions' in trans:
            trans = trans['transactions']
        transaction_time = trans.get('transaction_time')
        external_calls = trans.get('external_calls')
        external_latency = trans.get('external_latency')
        api_endpoints = trans.get('api_endpoints')
        web_count = trans.get('web_count')
        other_count = trans.get('other_count')
        
        # Build section
        section = f"## API/Transaction Metrics (Score: {score}/100 {emoji})\n\n"
        
        # Transaction type breakdown
        if web_count is not None or other_count is not None:
            w = web_count or 0
            o = other_count or 0
            section += f"- **Transaction Types:** {w:,} Web · {o:,} Background/Other\n"

        # Transaction time
        if transaction_time is not None:
            tt_indicator = "🟢" if transaction_time < 500 else "🔴"
            section += f"- **Average Transaction Time:** {transaction_time:.0f} ms {tt_indicator} (threshold: <500ms)\n"
        else:
            section += "- **Average Transaction Time:** N/A\n"
        
        # External calls
        if external_calls is not None:
            section += f"- **External Calls Count:** {external_calls:,}\n"
        else:
            section += "- **External Calls Count:** N/A\n"
        
        # External latency
        if external_latency is not None:
            el_indicator = "🟢" if external_latency < 200 else "🔴"
            section += f"- **External Service Latency:** {external_latency:.0f} ms {el_indicator} (threshold: <200ms)\n"
        else:
            section += "- **External Service Latency:** N/A\n"
        
        # Active transaction names (sample — all types)
        if api_endpoints and len(api_endpoints) > 0:
            section += "- **Active Transactions (sample):**\n"
            for endpoint in api_endpoints[:10]:
                section += f"  - {endpoint}\n"
        else:
            section += "- **Active Transactions:** N/A\n"
        
        return section
    
    def _generate_slow_transactions_section(self, metrics: Dict[str, Any]) -> str:
        """Generate slow transactions breakdown section."""
        slow_txns = metrics.get('slow_transactions', {})
        if isinstance(slow_txns, dict):
            slow_txns = slow_txns.get('slow_transactions', [])
        if not slow_txns:
            return ""
        
        section = "## Slow Transactions (Top Endpoints)\n\n"
        section += "| Type | Endpoint | Avg (ms) | P95 (ms) | Calls | DB Time (ms) | External (ms) |\n"
        section += "|---|---|---|---|---|---|---|\n"
        for txn in slow_txns[:20]:
            name = txn.get('name', 'Unknown')
            if len(name) > 60:
                name = "..." + name[-57:]
            txn_type = txn.get('transaction_type', 'Web')
            type_label = '🌐' if txn_type == 'Web' else '⚙️'
            avg_ms = txn.get('avg_duration_ms')
            p95 = txn.get('p95_ms')
            calls = txn.get('call_count', 0)
            db_ms = txn.get('db_time_ms')
            ext_ms = txn.get('external_time_ms')
            avg_str = f"{avg_ms:.0f}" if avg_ms is not None else "N/A"
            p95_str = f"{p95:.0f}" if p95 is not None else "N/A"
            db_str = f"{db_ms:.0f}" if db_ms is not None else "-"
            ext_str = f"{ext_ms:.0f}" if ext_ms is not None else "-"
            indicator = " 🔴" if avg_ms and avg_ms > 1000 else " 🟡" if avg_ms and avg_ms > 500 else ""
            section += f"| {type_label} | {name} | {avg_str}{indicator} | {p95_str} | {calls:,} | {db_str} | {ext_str} |\n"
        return section
    
    def _generate_slow_db_transactions_section(self, metrics: Dict[str, Any]) -> str:
        """Generate top-20 slowest transactions by database time."""
        slow_db = metrics.get('slow_db_transactions', {})
        if isinstance(slow_db, dict):
            slow_db = slow_db.get('slow_db_transactions', [])
        if not slow_db:
            return ""

        section = "## Slow Database Transactions (Top 20 by DB Time)\n\n"
        section += "| Type | Transaction | Avg DB (ms) | P95 DB (ms) | Avg Calls | Total Calls | DB% \n"
        section += "|---|---|---|---|---|---|---|\n"
        for row in slow_db[:20]:
            name = row.get('name', 'Unknown')
            if len(name) > 65:
                name = "..." + name[-62:]
            txn_type     = row.get('transaction_type', 'Web')
            type_label   = '\U0001f310' if txn_type == 'Web' else '\u2699\ufe0f'
            avg_db       = row.get('avg_db_ms')
            p95_db       = row.get('p95_db_ms')
            avg_calls    = row.get('avg_db_calls')
            call_count   = row.get('call_count', 0)
            avg_total    = row.get('avg_total_ms')
            avg_db_str   = f"{avg_db:.0f}" if avg_db is not None else "N/A"
            p95_db_str   = f"{p95_db:.0f}" if p95_db is not None else "N/A"
            calls_str    = f"{avg_calls:.1f}" if avg_calls is not None else "N/A"
            indicator    = " \U0001f534" if avg_db and avg_db > 1000 else " \U0001f7e1" if avg_db and avg_db > 500 else ""
            # DB time as % of total transaction time
            if avg_db is not None and avg_total and avg_total > 0:
                db_pct = avg_db / avg_total * 100
                pct_str = f"{db_pct:.0f}%"
            else:
                pct_str = "N/A"
            section += f"| {type_label} | {name} | {avg_db_str}{indicator} | {p95_db_str} | {calls_str} | {call_count:,} | {pct_str} |\n"
        return section

    def _generate_external_services_section(self, metrics: Dict[str, Any]) -> str:
        """Generate external services dependency section."""
        ext_svcs = metrics.get('external_services', {})
        if isinstance(ext_svcs, dict):
            ext_svcs = ext_svcs.get('external_services', [])
        if not ext_svcs:
            return ""
        
        section = "## External Service Dependencies\n\n"
        section += "| Host | Avg (ms) | P95 (ms) | Calls |\n"
        section += "|---|---|---|---|\n"
        for svc in ext_svcs[:15]:
            host = svc.get('host', 'Unknown')
            avg_ms = svc.get('avg_duration_ms')
            p95 = svc.get('p95_ms')
            calls = svc.get('call_count', 0)
            avg_str = f"{avg_ms:.0f}" if avg_ms is not None else "N/A"
            p95_str = f"{p95:.0f}" if p95 is not None else "N/A"
            indicator = " 🔴" if avg_ms and avg_ms > 500 else ""
            section += f"| {host} | {avg_str}{indicator} | {p95_str} | {calls:,} |\n"
        return section
    
    def _generate_logs_section(self, metrics: Dict[str, Any]) -> str:
        """Generate application logs section with error/warning logs and volume breakdown."""
        section = "## Application Logs\n\n"
        has_content = False
        
        # Log volume by level
        log_vol = metrics.get('log_volume', {})
        if isinstance(log_vol, dict):
            log_vol = log_vol.get('log_volume', [])
        if log_vol:
            has_content = True
            section += "### Log Volume by Level\n\n"
            section += "| Level | Count |\n"
            section += "|---|---|\n"
            for entry in log_vol:
                level = entry.get('level', 'Unknown')
                count = entry.get('count', 0)
                indicator = " 🔴" if level in ('ERROR', 'FATAL', 'SEVERE') else ""
                section += f"| {level}{indicator} | {count:,} |\n"
            section += "\n"
        
        # Application error/warning logs
        app_logs = metrics.get('application_logs', {})
        if isinstance(app_logs, dict):
            app_logs = app_logs.get('application_logs', [])
        if app_logs:
            has_content = True
            section += "### Error/Warning Logs (Recent)\n\n"
            for i, log in enumerate(app_logs[:50]):
                timestamp = log.get('timestamp', '')
                level = log.get('level', 'UNKNOWN')
                message = log.get('message', '')
                if len(message) > 200:
                    message = message[:197] + "..."
                level_icon = "🔴" if level in ('ERROR', 'FATAL', 'SEVERE') else "🟡"
                section += f"{i+1}. {level_icon} **[{level}]** {timestamp}\n"
                section += f"   > {message}\n\n"
        
        if not has_content:
            section += "_No log data available._\n"
        
        return section
    
    def _generate_alerts_section(self, metrics: Dict[str, Any]) -> str:
        """Generate alerts/incidents section."""
        alerts = metrics.get('alerts', {})
        if isinstance(alerts, dict):
            alerts = alerts.get('alerts', [])
        if not alerts:
            return ""
        
        section = "## Recent Alerts & Incidents\n\n"
        section += "| Priority | Title | State | Duration | Policy |\n"
        section += "|---|---|---|---|---|\n"
        for alert in alerts[:20]:
            priority = alert.get('priority', 'N/A')
            title = alert.get('title', 'Unknown')
            if len(title) > 50:
                title = title[:47] + "..."
            state = alert.get('state', 'N/A')
            duration = alert.get('duration_seconds')
            dur_str = f"{duration/60:.0f} min" if duration else "ongoing"
            policy = alert.get('policy_name', 'N/A')
            p_icon = "🔴" if priority == 'CRITICAL' else "🟡" if priority == 'WARNING' else "ℹ️"
            section += f"| {p_icon} {priority} | {title} | {state} | {dur_str} | {policy} |\n"
        return section
    
    def _generate_trends_section(self, metrics: Dict[str, Any]) -> str:
        """Generate hourly trends summary section."""
        trends = metrics.get('hourly_trends', {})
        if isinstance(trends, dict):
            trends = trends.get('hourly_trends', [])
        if not trends:
            return ""
        
        section = "## Hourly Performance Trends\n\n"
        section += "| Time (EST) | Response (ms) | Throughput (rpm) | Error Rate (%) |\n"
        section += "|---|---|---|---|\n"
        for point in trends:
            begin_ts = point.get('begin_time')
            ts = point.get('timestamp', '')
            if begin_ts is not None:
                try:
                    from datetime import timezone as _tz
                    dt = datetime.fromtimestamp(begin_ts, tz=_EST)
                    ts_short = dt.strftime("%m-%d %H:%M")
                except Exception:
                    ts_short = str(begin_ts)
            elif ts:
                ts_short = ts[:16] if len(ts) > 16 else ts
            else:
                ts_short = "N/A"
            resp = point.get('avg_response_ms')
            tput = point.get('throughput_rpm')
            err = point.get('error_rate')
            resp_str = f"{resp:.0f}" if resp is not None else "N/A"
            tput_str = f"{tput:.1f}" if tput is not None else "N/A"
            err_str = f"{err:.2f}%" if err is not None else "N/A"
            section += f"| {ts_short} | {resp_str} | {tput_str} | {err_str} |\n"
        return section
    
    def _generate_baselines_section(self, metrics: Dict[str, Any]) -> str:
        """Generate 7-day baseline comparison section."""
        baselines = metrics.get('baselines', {})
        if isinstance(baselines, dict):
            baselines = baselines.get('baselines', {})
        if not baselines:
            return ""
        
        section = "## 7-Day Baseline Comparison\n\n"
        
        perf = metrics.get('performance', {})
        if isinstance(perf, dict) and 'performance' in perf:
            perf = perf['performance']
        
        # Response time comparison
        baseline_rt = baselines.get('response_time_7d_avg_ms')
        current_rt = perf.get('response_time')
        if baseline_rt is not None and current_rt is not None:
            delta = ((current_rt - baseline_rt) / baseline_rt * 100) if baseline_rt > 0 else 0
            trend = "📈" if delta > 10 else "📉" if delta < -10 else "➡️"
            section += f"- **Response Time:** Current {current_rt:.0f}ms vs 7-day avg {baseline_rt:.0f}ms ({delta:+.1f}%) {trend}\n"
        
        # Throughput comparison
        baseline_tp = baselines.get('throughput_7d_avg_rpm')
        current_tp = perf.get('throughput')
        if baseline_tp is not None and current_tp is not None:
            delta = ((current_tp - baseline_tp) / baseline_tp * 100) if baseline_tp > 0 else 0
            trend = "📈" if delta > 10 else "📉" if delta < -10 else "➡️"
            section += f"- **Throughput:** Current {current_tp:.1f}rpm vs 7-day avg {baseline_tp:.1f}rpm ({delta:+.1f}%) {trend}\n"
        
        # Error rate comparison
        baseline_er = baselines.get('error_rate_7d_avg')
        errors = metrics.get('errors', {})
        if isinstance(errors, dict) and 'errors' in errors:
            errors = errors['errors']
        current_er = errors.get('error_rate')
        if baseline_er is not None and current_er is not None:
            baseline_pct = baseline_er * 100
            current_pct = current_er * 100
            delta = current_pct - baseline_pct
            trend = "📈" if delta > 1 else "📉" if delta < -1 else "➡️"
            section += f"- **Error Rate:** Current {current_pct:.2f}% vs 7-day avg {baseline_pct:.2f}% ({delta:+.2f}pp) {trend}\n"
        
        # Total requests
        baseline_reqs = baselines.get('total_requests_7d')
        if baseline_reqs is not None:
            section += f"- **Total Requests (7-day):** {baseline_reqs:,.0f}\n"
        
        return section
    
    def _generate_deployments_section(self, metrics: Dict[str, Any]) -> str:
        """Generate recent deployments section."""
        deploys = metrics.get('deployments', {})
        if isinstance(deploys, dict):
            deploys = deploys.get('deployments', [])
        if not deploys:
            return ""
        
        section = "## Recent Deployments\n\n"
        section += "| Timestamp | Revision | User | Description |\n"
        section += "|---|---|---|---|\n"
        for dep in deploys[:10]:
            ts = dep.get('timestamp', 'N/A')
            rev = dep.get('revision', 'N/A')
            user = dep.get('user', 'N/A')
            desc = dep.get('description', '')
            if len(desc) > 60:
                desc = desc[:57] + "..."
            section += f"| {ts} | {rev} | {user} | {desc} |\n"
        return section
    
    def _get_score_emoji(self, score: int) -> str:
        """
        Get emoji indicator based on score.
        
        Args:
            score: Health score (0-100)
        
        Returns:
            Emoji string (🟢🟡🟠🔴)
        """
        if score >= 80:
            return "🟢"
        elif score >= 60:
            return "🟡"
        elif score >= 40:
            return "🟠"
        else:
            return "🔴"
    
    def _generate_findings_section(self, findings: list) -> str:
        """
        Generate findings and issues section grouped by severity.
        
        Args:
            findings: List of finding dictionaries from HealthCalculator
                Expected keys: severity, category, issue, metric, value
        
        Returns:
            Markdown-formatted findings section
        """
        logger.debug("[DEBUG] [report_generator] Generating findings section")
        
        section = "## Findings & Issues\n\n"
        
        # Group findings by severity
        critical = [f for f in findings if f.get('severity') == 'Critical']
        warnings = [f for f in findings if f.get('severity') == 'Warning']
        info = [f for f in findings if f.get('severity') == 'Info']
        
        # Critical issues
        if critical:
            section += f"### 🔴 Critical Issues ({len(critical)})\n\n"
            for finding in critical:
                section += f"- **{finding.get('issue', 'Unknown Issue')}**\n"
                section += f"  - Metric: {finding.get('metric', 'N/A')}\n"
                section += f"  - Current Value: {finding.get('value', 'N/A')}\n"
                if 'threshold' in finding:
                    section += f"  - Threshold: {finding['threshold']}\n"
                if 'impact' in finding:
                    section += f"  - Impact: {finding['impact']}\n"
                section += "\n"
        else:
            section += "### 🔴 Critical Issues (0)\n\nNo critical issues detected.\n\n"
        
        # Warnings
        if warnings:
            section += f"### 🟠 Warnings ({len(warnings)})\n\n"
            for finding in warnings:
                section += f"- **{finding.get('issue', 'Unknown Issue')}**\n"
                section += f"  - Metric: {finding.get('metric', 'N/A')}\n"
                section += f"  - Current Value: {finding.get('value', 'N/A')}\n"
                if 'threshold' in finding:
                    section += f"  - Threshold: {finding['threshold']}\n"
                if 'impact' in finding:
                    section += f"  - Impact: {finding['impact']}\n"
                section += "\n"
        else:
            section += "### 🟠 Warnings (0)\n\nNo warnings.\n\n"
        
        # Info
        if info:
            section += f"### 🟢 Info ({len(info)})\n\n"
            for finding in info:
                section += f"- **{finding.get('issue', 'Unknown Issue')}**\n"
                section += f"  - Metric: {finding.get('metric', 'N/A')}\n"
                section += f"  - Current Value: {finding.get('value', 'N/A')}\n"
                if 'threshold' in finding:
                    section += f"  - Threshold: {finding['threshold']}\n"
                if 'impact' in finding:
                    section += f"  - Impact: {finding['impact']}\n"
                section += "\n"
        else:
            section += "### 🟢 Info (0)\n\nAll metrics within healthy ranges.\n"
        
        return section.rstrip()
    
    def _generate_recommendations_section(self) -> str:
        """
        Generate recommendations section with @recommend-agent placeholder.
        
        Returns:
            Markdown-formatted recommendations section
        """
        logger.debug("[DEBUG] [report_generator] Generating recommendations section")
        
        section = "## Recommendations\n\n"
        section += "Run `@recommend-agent` in GitHub Copilot Chat for AI-powered code-specific recommendations.\n\n"
        section += "### Priority Recommendations\n\n"
        section += "*(Recommendations will be added by @recommend-agent based on this assessment)*\n"
        
        return section
    
    def save_report(
        self,
        report: str,
        app_id: str,
        reports_dir: str = "reports"
    ) -> str:
        """
        Save report to file with timestamp-based naming.
        
        Args:
            report: Markdown report content
            app_id: Application ID for filename
            reports_dir: Directory to save reports (default: "reports")
        
        Returns:
            Full path to saved report file
        
        Raises:
            OSError: If directory creation or file write fails
        """
        logger.debug(f"[DEBUG] [report_generator] Saving report for app: {app_id}")
        
        # Create reports directory if it doesn't exist
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate timestamp (filesystem-safe format without colons)
        timestamp = datetime.now(_EST).strftime("%Y-%m-%d-%H%M%S")
        
        # Generate filename
        filename = f"health-report-{app_id}-{timestamp}.md"
        filepath = os.path.join(reports_dir, filename)
        
        # Write report to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Get file size for logging
        file_size = os.path.getsize(filepath)
        
        # Log success
        logger.info(f"[INFO] [report_generator] Health report saved successfully")
        logger.debug(f"[DEBUG] [report_generator] Report size: {file_size} bytes")
        
        print(f"✓ Report generated: {filepath}")
        
        return filepath
