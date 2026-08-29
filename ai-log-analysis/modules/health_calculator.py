"""
Health Score Calculator Module

This module provides health scoring functionality for application metrics,
calculating normalized scores across five categories: performance, errors,
infrastructure, database, and API.
"""

import logging

# Configure module logger
logger = logging.getLogger('health_calculator')


class HealthCalculator:
    """
    Calculates health scores for application metrics using weighted algorithms.
    
    This class implements a deterministic scoring system that normalizes metrics
    across five categories and produces an overall health score from 0-100.
    """
    
    # Status emoji indicators for visual reporting
    STATUS_EMOJIS = {
        "Excellent": "🟢",
        "Good": "🟡",
        "Warning": "🟠",
        "Critical": "🔴"
    }
    
    # Category weights for overall score calculation
    CATEGORY_WEIGHTS = {
        "performance": 0.25,
        "errors": 0.25,
        "infrastructure": 0.20,
        "database": 0.15,
        "api": 0.15
    }
    
    # Threshold bands for metric normalization (lower is better for most metrics)
    THRESHOLDS = {
        # Performance metrics (milliseconds)
        "response_time": [
            (200, 100),    # < 200ms = 100 points
            (500, 70),     # 200-500ms = 70 points
            (1000, 40),    # 500-1000ms = 40 points
            (float('inf'), 20)  # > 1000ms = 20 points
        ],
        # Throughput (requests/minute, higher is better)
        "throughput": [
            (1000, 100),   # >= 1000 rpm = 100 points
            (500, 70),     # >= 500 rpm = 70 points
            (100, 40),     # >= 100 rpm = 40 points
            (0, 20)        # < 100 rpm = 20 points
        ],
        # Apdex score (0.0-1.0, higher is better) - just multiply by 100
        "apdex_score": "direct_percentage",
        
        # Error metrics (percentages as decimals, lower is better)
        "error_rate": [
            (0.01, 100),   # < 1% = 100 points
            (0.03, 70),    # 1-3% = 70 points
            (0.05, 40),    # 3-5% = 40 points
            (float('inf'), 20)  # > 5% = 20 points
        ],
        # Error count (absolute, lower is better)
        "error_count": [
            (10, 100),     # < 10 errors = 100 points
            (50, 70),      # 10-50 errors = 70 points
            (100, 40),     # 50-100 errors = 40 points
            (float('inf'), 20)  # > 100 errors = 20 points
        ],
        
        # Infrastructure metrics (percentages as decimals, lower is better for cpu/memory)
        "cpu_usage": [
            (0.60, 100),   # < 60% = 100 points
            (0.75, 70),    # 60-75% = 70 points
            (0.85, 40),    # 75-85% = 40 points
            (float('inf'), 20)  # > 85% = 20 points
        ],
        "memory_usage": [
            (0.70, 100),   # < 70% = 100 points
            (0.80, 70),    # 70-80% = 70 points
            (0.90, 40),    # 80-90% = 40 points
            (float('inf'), 20)  # > 90% = 20 points
        ],
        # Disk I/O (MB/s, lower is better)
        "disk_io": [
            (50, 100),     # < 50 MB/s = 100 points
            (100, 70),     # 50-100 MB/s = 70 points
            (200, 40),     # 100-200 MB/s = 40 points
            (float('inf'), 20)  # > 200 MB/s = 20 points
        ],
        
        # Database metrics (milliseconds, lower is better)
        "query_time": [
            (50, 100),     # < 50ms = 100 points
            (100, 70),     # 50-100ms = 70 points
            (200, 40),     # 100-200ms = 40 points
            (float('inf'), 20)  # > 200ms = 20 points
        ],
        "slow_queries": [
            (5, 100),      # < 5 slow queries = 100 points
            (20, 70),      # 5-20 slow queries = 70 points
            (50, 40),      # 20-50 slow queries = 40 points
            (float('inf'), 20)  # > 50 slow queries = 20 points
        ],
        # Connection pool usage (percentage as decimal, lower is better)
        "connection_pool_usage": [
            (0.60, 100),   # < 60% = 100 points
            (0.75, 70),    # 60-75% = 70 points
            (0.85, 40),    # 75-85% = 40 points
            (float('inf'), 20)  # > 85% = 20 points
        ],
        "database_calls": [
            (100, 100),    # < 100 calls = 100 points
            (500, 70),     # 100-500 calls = 70 points
            (1000, 40),    # 500-1000 calls = 40 points
            (float('inf'), 20)  # > 1000 calls = 20 points
        ],
        
        # API/Transaction metrics (milliseconds, lower is better)
        "transaction_time": [
            (200, 100),    # < 200ms = 100 points
            (500, 70),     # 200-500ms = 70 points
            (1000, 40),    # 500-1000ms = 40 points
            (float('inf'), 20)  # > 1000ms = 20 points
        ],
        "external_calls": [
            (5, 100),      # < 5 calls = 100 points
            (10, 70),      # 5-10 calls = 70 points
            (20, 40),      # 10-20 calls = 40 points
            (float('inf'), 20)  # > 20 calls = 20 points
        ],
        "external_latency": [
            (100, 100),    # < 100ms = 100 points
            (300, 70),     # 100-300ms = 70 points
            (500, 40),     # 300-500ms = 40 points
            (float('inf'), 20)  # > 500ms = 20 points
        ]
    }
    
    # P95 response time thresholds (milliseconds, lower is better)
    THRESHOLDS["p95_ms"] = [
        (500, 100),    # < 500ms = 100 points
        (1000, 70),    # 500-1000ms = 70 points
        (2000, 40),    # 1000-2000ms = 40 points
        (float('inf'), 20)  # > 2000ms = 20 points
    ]
    
    # Category to metric mapping
    CATEGORY_METRICS = {
        "performance": ["response_time", "p95_ms", "throughput", "apdex_score"],
        "errors": ["error_rate", "error_count"],
        "infrastructure": ["cpu_usage", "memory_usage", "disk_io"],
        "database": ["query_time", "slow_queries", "connection_pool_usage", "database_calls"],
        "api": ["transaction_time", "external_calls", "external_latency"]
    }
    
    # Severity order for sorting findings
    SEVERITY_ORDER = {"Critical": 0, "Warning": 1, "Info": 2}
    
    # Category order for sorting findings within same severity
    CATEGORY_ORDER = {"performance": 0, "errors": 1, "infrastructure": 2, "database": 3, "api": 4, "overall": 5}
    
    def __init__(self):
        """Initialize the HealthCalculator."""
        logger.debug("[DEBUG] [health_calculator] HealthCalculator initialized")
    
    def _normalize_metric(self, metric_name: str, value: float) -> int:
        """
        Normalize a metric value to a 0-100 score using threshold bands.
        
        Args:
            metric_name: Name of the metric to normalize
            value: Raw metric value
            
        Returns:
            Normalized score (0-100)
        """
        if value is None:
            logger.warning(f"[WARNING] [health_calculator] Missing data for {metric_name}, using default score")
            return 50  # Neutral score for missing data
        
        threshold_config = self.THRESHOLDS.get(metric_name)
        
        if threshold_config is None:
            logger.warning(f"[WARNING] [health_calculator] No threshold defined for {metric_name}, using default score")
            return 50
        
        # Handle direct percentage conversion (e.g., apdex_score)
        if threshold_config == "direct_percentage":
            return int(value * 100)
        
        # Handle threshold bands
        # For most metrics, lower is better (response time, error rate, etc.)
        # For throughput, higher is better (inverted logic)
        is_higher_better = metric_name in ["throughput"]
        
        if is_higher_better:
            # For "higher is better" metrics, traverse thresholds from high to low
            for threshold, score in threshold_config:
                if value >= threshold:
                    return score
            return threshold_config[-1][1]  # Return lowest score if below all thresholds
        else:
            # For "lower is better" metrics, traverse thresholds from low to high
            for threshold, score in threshold_config:
                if value < threshold:
                    return score
            return threshold_config[-1][1]  # Return lowest score if above all thresholds
    
    def _calculate_category_score(self, category: str, metrics: dict) -> int:
        """
        Calculate the score for a specific category.
        
        Args:
            category: Category name (performance, errors, infrastructure, database, api)
            metrics: Dictionary of all metrics
            
        Returns:
            Category score (0-100)
        """
        metric_names = self.CATEGORY_METRICS.get(category, [])
        
        if not metric_names:
            logger.warning(f"[WARNING] [health_calculator] Unknown category {category}, using default score")
            return 50
        
        # Normalize each metric in the category
        scores = []
        for metric_name in metric_names:
            metric_value = metrics.get(metric_name)
            normalized_score = self._normalize_metric(metric_name, metric_value)
            scores.append(normalized_score)
        
        # Calculate weighted average (equal weight for each metric in category)
        if scores:
            category_score = sum(scores) / len(scores)
            return int(round(category_score))
        else:
            return 50  # Neutral score if no metrics available
    
    def calculate_health_score(self, metrics: dict) -> dict:
        """
        Calculate overall health score and category breakdowns.
        
        Args:
            metrics: Dictionary containing all metric values from ApiClient
            
        Returns:
            Dictionary with structure:
            {
                "overall_score": int (0-100),
                "status": str,
                "category_scores": {
                    "performance": int,
                    "errors": int,
                    "infrastructure": int,
                    "database": int,
                    "api": int
                },
                "findings": []
            }
        """
        # Calculate scores for each category
        category_scores = {}
        for category in self.CATEGORY_WEIGHTS.keys():
            category_scores[category] = self._calculate_category_score(category, metrics)
        
        # Calculate overall score using category weights
        overall_score = 0
        for category, weight in self.CATEGORY_WEIGHTS.items():
            overall_score += category_scores[category] * weight
        
        overall_score = int(round(overall_score))
        
        # Log the calculated scores
        logger.debug(f"[DEBUG] [health_calculator] Calculated scores: {category_scores}")
        
        # Determine status with logging
        status = self._get_status(overall_score)
        status_emoji = self.STATUS_EMOJIS.get(status, "⚪")
        
        # Identify findings (Story 3.3)
        findings = self.identify_findings(metrics, category_scores)
        
        return {
            "overall_score": overall_score,
            "status": status,
            "status_emoji": status_emoji,
            "category_scores": category_scores,
            "findings": findings
        }
    
    def _get_status(self, overall_score: int) -> str:
        """
        Get health status based on overall score with INFO logging.
        
        Args:
            overall_score: Overall health score (0-100)
            
        Returns:
            Status string (Excellent, Good, Warning, Critical)
        """
        if overall_score >= 90:
            status = "Excellent"
        elif overall_score >= 70:
            status = "Good"
        elif overall_score >= 50:
            status = "Warning"
        else:
            status = "Critical"
        
        # Log status determination with emoji indicator
        emoji = self.STATUS_EMOJIS.get(status, "⚪")
        logger.info(f"[INFO] [health_calculator] Health status: {status} ({overall_score}) {emoji}")
        
        return status
    
    def identify_findings(self, metrics: dict, category_scores: dict) -> list:
        """
        Identify issues and findings based on metric threshold violations.
        
        Args:
            metrics: Dictionary containing all metric values
            category_scores: Dictionary of category scores (0-100)
            
        Returns:
            Sorted list of finding dictionaries with structure:
            {
                "category": str,
                "severity": str (Critical/Warning/Info),
                "issue": str,
                "metric": str,
                "value": float/int,
                "description": str
            }
            Sorted by severity (Critical > Warning > Info), then by category importance.
        """
        findings = []
        
        # Performance findings
        response_time = metrics.get("response_time")
        if response_time is not None:
            if response_time > 1000:
                findings.append({
                    "category": "performance",
                    "severity": "Critical",
                    "issue": "High response time",
                    "metric": "response_time",
                    "value": response_time,
                    "description": f"Response time at {response_time:.0f}ms exceeds 1000ms threshold"
                })
            elif response_time > 500:
                findings.append({
                    "category": "performance",
                    "severity": "Warning",
                    "issue": "Elevated response time",
                    "metric": "response_time",
                    "value": response_time,
                    "description": f"Response time at {response_time:.0f}ms exceeds 500ms threshold"
                })
        
        throughput = metrics.get("throughput")
        if throughput is not None:
            if throughput < 100:
                findings.append({
                    "category": "performance",
                    "severity": "Critical",
                    "issue": "Very low throughput",
                    "metric": "throughput",
                    "value": throughput,
                    "description": f"Throughput at {throughput:.0f} rpm is critically low (threshold: 100 rpm)"
                })
            elif throughput < 500:
                findings.append({
                    "category": "performance",
                    "severity": "Warning",
                    "issue": "Low throughput",
                    "metric": "throughput",
                    "value": throughput,
                    "description": f"Throughput at {throughput:.0f} rpm below optimal (threshold: 500 rpm)"
                })
        
        apdex_score = metrics.get("apdex_score")
        if apdex_score is not None and apdex_score < 0.5:
            findings.append({
                "category": "performance",
                "severity": "Critical",
                "issue": "Poor user experience (Apdex)",
                "metric": "apdex_score",
                "value": apdex_score,
                "description": f"Apdex score at {apdex_score:.2f} indicates poor user satisfaction (threshold: 0.5)"
            })
        
        # P95 response time findings
        p95_ms = metrics.get("p95_ms")
        if p95_ms is not None:
            if p95_ms > 2000:
                findings.append({
                    "category": "performance",
                    "severity": "Critical",
                    "issue": "Very high P95 response time",
                    "metric": "p95_ms",
                    "value": p95_ms,
                    "description": f"P95 response time at {p95_ms:.0f}ms - 5% of requests take over 2 seconds"
                })
            elif p95_ms > 1000:
                findings.append({
                    "category": "performance",
                    "severity": "Warning",
                    "issue": "Elevated P95 response time",
                    "metric": "p95_ms",
                    "value": p95_ms,
                    "description": f"P95 response time at {p95_ms:.0f}ms exceeds 1000ms threshold"
                })
        
        # High variance detection (P95 >> average)
        if p95_ms is not None and response_time is not None and response_time > 0:
            variance_ratio = p95_ms / response_time
            if variance_ratio > 5:
                findings.append({
                    "category": "performance",
                    "severity": "Warning",
                    "issue": "High response time variance",
                    "metric": "p95_ms",
                    "value": variance_ratio,
                    "description": f"P95 ({p95_ms:.0f}ms) is {variance_ratio:.1f}x the average ({response_time:.0f}ms) - indicates inconsistent performance"
                })
        
        # Error findings
        error_rate = metrics.get("error_rate")
        if error_rate is not None:
            if error_rate > 0.05:  # 5%
                findings.append({
                    "category": "errors",
                    "severity": "Warning",
                    "issue": "Elevated error rate",
                    "metric": "error_rate",
                    "value": error_rate,
                    "description": f"Error rate at {error_rate*100:.1f}% (threshold: 5%)"
                })
            elif error_rate > 0.03:  # 3%
                findings.append({
                    "category": "errors",
                    "severity": "Info",
                    "issue": "Error rate above optimal",
                    "metric": "error_rate",
                    "value": error_rate,
                    "description": f"Error rate at {error_rate*100:.1f}% above optimal (threshold: 3%)"
                })
        
        error_count = metrics.get("error_count")
        if error_count is not None and error_count > 100:
            findings.append({
                "category": "errors",
                "severity": "Warning",
                "issue": "High error count",
                "metric": "error_count",
                "value": error_count,
                "description": f"Error count at {error_count:.0f} errors (threshold: 100)"
            })
        
        # Infrastructure findings
        # cpu_usage is 0.0-1.0 (fraction), e.g. 0.08 = 8%
        cpu_usage = metrics.get("cpu_usage")
        if cpu_usage is not None:
            if cpu_usage > 0.85:
                findings.append({
                    "category": "infrastructure",
                    "severity": "Critical",
                    "issue": "Very high CPU utilization",
                    "metric": "cpu_usage",
                    "value": cpu_usage,
                    "description": f"CPU at {cpu_usage*100:.1f}% (threshold: 85%)"
                })
            elif cpu_usage > 0.60:
                findings.append({
                    "category": "infrastructure",
                    "severity": "Warning",
                    "issue": "Elevated CPU utilization",
                    "metric": "cpu_usage",
                    "value": cpu_usage,
                    "description": f"CPU at {cpu_usage*100:.1f}% (threshold: 60%)"
                })
        
        memory_usage = metrics.get("memory_usage")
        if memory_usage is not None:
            if memory_usage > 0.90:  # 90%
                findings.append({
                    "category": "infrastructure",
                    "severity": "Critical",
                    "issue": "Memory near exhaustion",
                    "metric": "memory_usage",
                    "value": memory_usage,
                    "description": f"Memory at {memory_usage*100:.0f}% (threshold: 90%)"
                })
            elif memory_usage > 0.80:  # 80%
                findings.append({
                    "category": "infrastructure",
                    "severity": "Warning",
                    "issue": "High memory utilization",
                    "metric": "memory_usage",
                    "value": memory_usage,
                    "description": f"Memory at {memory_usage*100:.0f}% (threshold: 80%)"
                })
        
        disk_io = metrics.get("disk_io")
        if disk_io is not None and disk_io > 200:
            findings.append({
                "category": "infrastructure",
                "severity": "Warning",
                "issue": "High disk I/O",
                "metric": "disk_io",
                "value": disk_io,
                "description": f"Disk I/O at {disk_io:.0f} MB/s (threshold: 200 MB/s)"
            })
        
        # Database findings
        query_time = metrics.get("query_time")
        if query_time is not None:
            if query_time > 200:
                findings.append({
                    "category": "database",
                    "severity": "Critical",
                    "issue": "Very slow database queries",
                    "metric": "query_time",
                    "value": query_time,
                    "description": f"Query time at {query_time:.0f}ms exceeds 200ms threshold"
                })
            elif query_time > 100:
                findings.append({
                    "category": "database",
                    "severity": "Warning",
                    "issue": "Slow database queries",
                    "metric": "query_time",
                    "value": query_time,
                    "description": f"Query time at {query_time:.0f}ms exceeds 100ms threshold"
                })
        
        slow_queries = metrics.get("slow_queries")
        if slow_queries is not None and slow_queries > 50:
            findings.append({
                "category": "database",
                "severity": "Warning",
                "issue": "High slow query count",
                "metric": "slow_queries",
                "value": slow_queries,
                "description": f"Slow query count at {slow_queries:.0f} (threshold: 50)"
            })
        
        connection_pool_usage = metrics.get("connection_pool_usage")
        if connection_pool_usage is not None:
            if connection_pool_usage > 0.90:  # 90%
                findings.append({
                    "category": "database",
                    "severity": "Critical",
                    "issue": "Connection pool near exhaustion",
                    "metric": "connection_pool_usage",
                    "value": connection_pool_usage,
                    "description": f"Connection pool at {connection_pool_usage*100:.0f}% (threshold: 90%). Increase pool size or investigate connection leaks"
                })
            elif connection_pool_usage > 0.75:  # 75%
                findings.append({
                    "category": "database",
                    "severity": "Warning",
                    "issue": "High connection pool usage",
                    "metric": "connection_pool_usage",
                    "value": connection_pool_usage,
                    "description": f"Connection pool at {connection_pool_usage*100:.0f}% (threshold: 75%)"
                })
        
        # Check for N+1 query pattern (high database calls + low throughput)
        database_calls = metrics.get("database_calls")
        if database_calls is not None and throughput is not None:
            if database_calls > 1000 and throughput < 500:
                findings.append({
                    "category": "database",
                    "severity": "Warning",
                    "issue": "Possible N+1 query pattern",
                    "metric": "database_calls",
                    "value": database_calls,
                    "description": f"High database call count ({database_calls:.0f}) with low throughput ({throughput:.0f} rpm) suggests N+1 queries"
                })
        
        # API/Transaction findings
        transaction_time = metrics.get("transaction_time")
        if transaction_time is not None:
            if transaction_time > 1000:
                findings.append({
                    "category": "api",
                    "severity": "Critical",
                    "issue": "Very slow transaction time",
                    "metric": "transaction_time",
                    "value": transaction_time,
                    "description": f"Transaction time at {transaction_time:.0f}ms exceeds 1000ms threshold"
                })
            elif transaction_time > 500:
                findings.append({
                    "category": "api",
                    "severity": "Warning",
                    "issue": "Slow transaction time",
                    "metric": "transaction_time",
                    "value": transaction_time,
                    "description": f"Transaction time at {transaction_time:.0f}ms exceeds 500ms threshold"
                })
        
        external_latency = metrics.get("external_latency")
        if external_latency is not None and external_latency > 500:
            findings.append({
                "category": "api",
                "severity": "Warning",
                "issue": "High external API latency",
                "metric": "external_latency",
                "value": external_latency,
                "description": f"External API latency at {external_latency:.0f}ms (threshold: 500ms)"
            })
        
        # If no findings, add Info finding
        if not findings:
            logger.info("[INFO] [health_calculator] No critical issues detected")
            findings.append({
                "category": "overall",
                "severity": "Info",
                "issue": "All metrics within healthy ranges",
                "metric": "overall",
                "value": None,
                "description": "No threshold violations detected. All metrics are within acceptable ranges."
            })
        
        # Sort findings: Critical > Warning > Info, then by category importance
        findings.sort(key=lambda f: (self.SEVERITY_ORDER.get(f["severity"], 999), 
                                     self.CATEGORY_ORDER.get(f["category"], 999)))
        
        logger.debug(f"[DEBUG] [health_calculator] Identified {len(findings)} finding(s)")
        
        return findings
