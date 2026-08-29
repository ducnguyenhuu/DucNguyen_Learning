"""
New Relic GraphQL API client with retry logic and error handling.

This module provides a robust API client for New Relic's NerdGraph API,
handling authentication, request retries for transient errors, and fail-fast
behavior for rate limits and authorization failures.
"""

import requests
import time
import logging
import json
import os
import glob
from datetime import datetime, timedelta, timezone
try:
    from zoneinfo import ZoneInfo
    _EST = ZoneInfo("America/New_York")
except Exception:
    # Fallback when tzdata is not installed (Windows without tzdata package)
    _EST = timezone(timedelta(hours=-5))
from typing import Dict, Any, Optional


class ApiClient:
    """
    New Relic GraphQL API client with retry logic and error handling.
    
    Handles authentication, request retries for transient errors,
    and fail-fast behavior for rate limits and authorization failures.
    """
    
    def __init__(
        self, 
        api_key: str, 
        account_id: str, 
        timeout: int = 30, 
        max_retries: int = 2, 
        retry_delay: int = 5
    ):
        """
        Initialize API client with credentials and configuration.
        
        Args:
            api_key: New Relic User API Key (NRAK-...)
            account_id: New Relic account ID
            timeout: Request timeout in seconds (default: 30)
            max_retries: Maximum retry attempts (default: 2)
            retry_delay: Delay between retries in seconds (default: 5)
        """
        self._api_key = api_key
        self._account_id = account_id
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._endpoint = "https://api.newrelic.com/graphql"
        self._logger = logging.getLogger('api_client')
    
    def _safe_float(self, value):
        """Convert value to float, return None if conversion fails or value is None."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value):
        """Convert value to int, return None if conversion fails or value is None."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _make_request(
        self, 
        query: str, 
        variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute GraphQL query against New Relic API with retry logic.
        
        Args:
            query: GraphQL query string
            variables: Optional query variables
            
        Returns:
            Parsed JSON response from API
            
        Raises:
            requests.exceptions.HTTPError: For 4xx/5xx errors after retries
            requests.exceptions.Timeout: After exhausting retries
            ValueError: For rate limit (429) errors, authentication failures, or GraphQL errors
        """
        # Validate input
        if not query or not query.strip():
            raise ValueError("GraphQL query cannot be empty")
        
        headers = {
            'Api-Key': self._api_key,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': query
        }
        if variables:
            payload['variables'] = variables
        
        # Retry loop for transient errors
        last_error = None
        for attempt in range(self._max_retries + 1):  # +1 for initial attempt
            try:
                start_time = time.time()
                
                response = requests.post(
                    self._endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout
                )
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Handle rate limiting (fail fast, no retry)
                if response.status_code == 429:
                    reset_time = response.headers.get('X-RateLimit-Reset', 'unknown')
                    error_msg = f"New Relic API rate limit exceeded. Reset time: {reset_time}. Wait before making more requests."
                    self._logger.error(f"[ERROR] [api_client] {error_msg}")
                    raise ValueError(error_msg)
                
                # Handle authentication errors (fail fast, no retry)
                if response.status_code in (401, 403):
                    error_msg = "Invalid New Relic API key or insufficient permissions. Verify api_key in configuration."
                    self._logger.error(f"[ERROR] [api_client] {error_msg}")
                    raise ValueError(error_msg)
                
                # Raise for other 4xx/5xx errors (will retry on 5xx)
                response.raise_for_status()
                
                # Success - log and validate response
                self._logger.info(f"[INFO] [api_client] Request completed in {duration_ms}ms")
                self._logger.debug(
                    f"[DEBUG] [api_client] Response status: {response.status_code}, "
                    f"Response size: {len(response.content)} bytes"
                )
                
                # Parse and validate GraphQL response
                json_response = response.json()
                
                # Check for GraphQL errors (can occur even with HTTP 200)
                if 'errors' in json_response and json_response['errors']:
                    errors = json_response['errors']
                    error_msg = f"GraphQL errors: {errors}"
                    self._logger.error(f"[ERROR] [api_client] {error_msg}")
                    raise ValueError(error_msg)
                
                return json_response
                
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Transient network errors - retry
                last_error = e
                if attempt < self._max_retries:
                    self._logger.warning(
                        f"[WARNING] [api_client] Retry {attempt + 1}/{self._max_retries} "
                        f"after error: {type(e).__name__}: {str(e)}"
                    )
                    time.sleep(self._retry_delay)
                    continue
                    
            except requests.exceptions.HTTPError as e:
                # HTTP errors
                if e.response.status_code >= 500:
                    # Server errors - retry
                    last_error = e
                    if attempt < self._max_retries:
                        self._logger.warning(
                            f"[WARNING] [api_client] Retry {attempt + 1}/{self._max_retries} "
                            f"after error: HTTP {e.response.status_code}"
                        )
                        time.sleep(self._retry_delay)
                        continue
                # Client errors (4xx) - fail fast, no retry
                error_msg = f"API request failed with HTTP {e.response.status_code}: {str(e)}"
                self._logger.error(f"[ERROR] [api_client] {error_msg}")
                raise
        
        # Retries exhausted
        error_msg = (
            f"API request failed after {self._max_retries} retries. "
            f"Last error: {type(last_error).__name__}: {str(last_error)}. "
            f"Check logs for details or try again later."
        )
        self._logger.error(f"[ERROR] [api_client] {error_msg}")
        
        # Create HTTPError with proper response context
        http_error = requests.exceptions.HTTPError(error_msg)
        # Attach the last error for debugging context
        http_error.__cause__ = last_error
        raise http_error
    
    def fetch_performance_metrics(
        self, 
        app_id: str, 
        days: int
    ) -> Dict[str, Any]:
        """
        Fetch performance metrics for a specific application.
        
        Retrieves response time (ms), throughput (rpm), and Apdex score
        for the specified time window.
        
        Args:
            app_id: New Relic application ID
            days: Time window in days (must be 3, 7, 14, or 30)
            
        Returns:
            Dictionary with structure:
            {
                "app_id": str,
                "timestamp": str (ISO 8601),
                "performance": {
                    "response_time": float or None (milliseconds),
                    "throughput": float or None (requests per minute),
                    "apdex_score": float or None (0.0 to 1.0)
                }
            }
            
        Raises:
            ValueError: If app_id is empty or days not in [3, 7, 14, 30]
            requests.exceptions.*: For API request failures
        """
        from datetime import datetime, timedelta
        
        # Validate app_id
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        # Validate days parameter
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        # Calculate time window (since timestamp)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.strftime('%Y-%m-%d %H:%M:%S')
        
        # Construct NerdGraph NRQL query for performance metrics
        # Note: NRQL string must have values injected via f-string, not GraphQL variables
        # Includes manual Apdex fallback counters (T=0.5s) for apps without configured Apdex thresholds
        nrql_query = f"SELECT average(duration) * 1000 as 'avg_response_ms', percentile(duration, 50) * 1000 as 'p50_ms', percentile(duration, 90) * 1000 as 'p90_ms', percentile(duration, 95) * 1000 as 'p95_ms', percentile(duration, 99) * 1000 as 'p99_ms', rate(count(*), 1 minute) as 'throughput_rpm', count(*) as 'total_requests', apdex(duration, t:0.5) as 'apdex_score', filter(count(*), WHERE apdexPerfZone = 'S') as 'apdex_satisfied', filter(count(*), WHERE apdexPerfZone = 'T') as 'apdex_tolerating', filter(count(*), WHERE apdexPerfZone = 'F') as 'apdex_frustrated', filter(count(*), WHERE duration < 0.5) as 'manual_satisfied', filter(count(*), WHERE duration >= 0.5 AND duration < 2.0) as 'manual_tolerating', percentage(count(*), WHERE error IS false) as 'availability', uniqueCount(host) as 'instance_count', average(databaseDuration) * 1000 as 'db_time_ms', average(externalDuration) * 1000 as 'ext_time_ms', average(duration - databaseDuration - externalDuration) * 1000 as 'app_time_ms', average(queueDuration) * 1000 as 'queue_time_ms' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}'"
        
        query = f"""
        query($accountId: Int!) {{
          actor {{
            account(id: $accountId) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'accountId': int(self._account_id)
        }
        
        try:
            # Make API request
            self._logger.debug(
                f"[DEBUG] [api_client] Fetching performance metrics: "
                f"app_id={app_id}, days={days}, since={since_iso}"
            )
            
            response = self._make_request(query, variables)
            
            # Extract metrics from response
            results = response.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
            
            if not results:
                # No data available
                metrics = {
                    'response_time': None,
                    'p50_ms': None,
                    'p90_ms': None,
                    'p95_ms': None,
                    'p99_ms': None,
                    'throughput': None,
                    'total_requests': None,
                    'apdex_score': None,
                    'apdex_satisfied': None,
                    'apdex_tolerating': None,
                    'apdex_frustrated': None,
                    'availability': None,
                    'instance_count': None,
                    'db_time_ms': None,
                    'ext_time_ms': None,
                    'app_time_ms': None,
                    'queue_time_ms': None,
                }
            else:
                result = results[0]
                apdex_score = self._safe_float(result.get('apdex_score'))

                # Fallback: compute Apdex manually when the apdex() function returns null
                # (happens when Apdex thresholds are not configured for the app in New Relic)
                # Formula: (satisfied + tolerating/2) / total  using T=0.5s
                if apdex_score is None:
                    total = self._safe_int(result.get('total_requests')) or 0
                    sat   = self._safe_int(result.get('manual_satisfied')) or 0
                    tol   = self._safe_int(result.get('manual_tolerating')) or 0
                    if total > 0:
                        apdex_score = round((sat + tol / 2.0) / total, 4)

                metrics = {
                    'response_time': self._safe_float(result.get('avg_response_ms')),  # milliseconds
                    'p50_ms': self._safe_float(result.get('p50_ms')),
                    'p90_ms': self._safe_float(result.get('p90_ms')),
                    'p95_ms': self._safe_float(result.get('p95_ms')),
                    'p99_ms': self._safe_float(result.get('p99_ms')),
                    'throughput': self._safe_float(result.get('throughput_rpm')),  # requests per minute
                    'total_requests': self._safe_int(result.get('total_requests')),
                    'apdex_score': apdex_score,  # 0.0 to 1.0
                    'apdex_satisfied': self._safe_int(result.get('apdex_satisfied')),
                    'apdex_tolerating': self._safe_int(result.get('apdex_tolerating')),
                    'apdex_frustrated': self._safe_int(result.get('apdex_frustrated')),
                    'availability': self._safe_float(result.get('availability')),
                    'instance_count': self._safe_int(result.get('instance_count')),
                    'db_time_ms': self._safe_float(result.get('db_time_ms')),
                    'ext_time_ms': self._safe_float(result.get('ext_time_ms')),
                    'app_time_ms': self._safe_float(result.get('app_time_ms')),
                    'queue_time_ms': self._safe_float(result.get('queue_time_ms')),
                }
            
            # Generate current timestamp with UTC indicator
            timestamp = datetime.now(_EST).isoformat()
            
            # Build response dictionary
            response_dict = {
                'app_id': app_id,
                'timestamp': timestamp,
                'performance': metrics
            }
            
            # Log success
            self._logger.info(
                f"[INFO] [api_client] Fetched performance metrics for app_id={app_id}, days={days}"
            )
            
            return response_dict
            
        except Exception as e:
            # Log error with context
            error_msg = f"Failed to fetch performance metrics: {type(e).__name__}: {str(e)}"
            self._logger.error(
                f"[ERROR] [api_client] {error_msg}. app_id={app_id}, days={days}"
            )
            # Re-raise original exception
            raise
    
    def fetch_error_metrics(
        self, 
        app_id: str, 
        days: int
    ) -> Dict[str, Any]:
        """
        Fetch error metrics for a specific application.
        
        Retrieves error rate (as decimal), error count, and error types
        for the specified time window.
        
        Args:
            app_id: New Relic application ID
            days: Time window in days (must be 3, 7, 14, or 30)
            
        Returns:
            Dictionary with structure:
            {
                "app_id": str,
                "timestamp": str (ISO 8601),
                "errors": {
                    "error_rate": float or None (0.0 to 1.0, decimal not percentage),
                    "error_count": int or None,
                    "error_types": list of str or None
                }
            }
            
        Raises:
            ValueError: If app_id is empty or days not in [3, 7, 14, 30]
            requests.exceptions.*: For API request failures
        """
        from datetime import datetime, timedelta
        
        # Validate app_id
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        # Validate days parameter
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        # Calculate time window (since timestamp)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.strftime('%Y-%m-%d %H:%M:%S')
        
        # Construct NerdGraph NRQL query for error metrics
        # Note: NRQL string must have values injected via f-string, not GraphQL variables
        nrql_query = f"SELECT percentage(count(*), WHERE error IS true) as 'error.rate', filter(count(*), WHERE error IS true) as 'error.count', count(*) as 'total.transactions', uniques(error.class) as 'error.types' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}'"
        
        query = f"""
        query($accountId: Int!) {{
          actor {{
            account(id: $accountId) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'accountId': int(self._account_id)
        }
        
        try:
            # Make API request
            self._logger.debug(
                f"[DEBUG] [api_client] Fetching error metrics: "
                f"app_id={app_id}, days={days}, since={since_iso}"
            )
            
            response = self._make_request(query, variables)
            
            # Extract metrics from response
            results = response.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
            
            if not results:
                # No data available
                metrics = {
                    'error_rate': None,
                    'error_count': None,
                    'total_transactions': None,
                    'error_types': None
                }
            else:
                result = results[0]
                
                # Convert error rate from percentage to decimal (5.0 -> 0.05)
                error_rate_pct = self._safe_float(result.get('error.rate'))
                error_rate = (error_rate_pct / 100.0) if error_rate_pct is not None else None
                
                # Convert error count to int
                error_count = self._safe_int(result.get('error.count'))
                
                # Parse error types (may be array or comma-separated string)
                error_types_raw = result.get('error.types')
                if error_types_raw is None:
                    error_types = None
                elif isinstance(error_types_raw, list):
                    error_types = [str(t) for t in error_types_raw if t]
                elif isinstance(error_types_raw, str):
                    # Handle comma-separated string
                    error_types = [t.strip() for t in error_types_raw.split(',') if t.strip()]
                else:
                    error_types = None
                
                total_transactions = self._safe_int(result.get('total.transactions'))
                
                metrics = {
                    'error_rate': error_rate,
                    'error_count': error_count,
                    'total_transactions': total_transactions,
                    'error_types': error_types
                }
            
            # Generate current timestamp with UTC indicator
            timestamp = datetime.now(_EST).isoformat()
            
            # Build response dictionary
            response_dict = {
                'app_id': app_id,
                'timestamp': timestamp,
                'errors': metrics
            }
            
            # Log success
            self._logger.info(
                f"[INFO] [api_client] Fetched error metrics for app_id={app_id}, days={days}"
            )
            
            return response_dict
            
        except Exception as e:
            # Log error with context
            error_msg = f"Failed to fetch error metrics: {type(e).__name__}: {str(e)}"
            self._logger.error(
                f"[ERROR] [api_client] {error_msg}. app_id={app_id}, days={days}"
            )
            # Re-raise original exception
            raise
    
    def fetch_infrastructure_metrics(
        self, 
        app_id: str, 
        days: int,
        app_name: str = None
    ) -> Dict[str, Any]:
        """
        Fetch infrastructure metrics for the host running the application.

        Strategy:
        1. Discover the app's hostname from Transaction events.
        2. Query SystemSample for that host (Infrastructure agent) — gives
           proper 0-100 % CPU, memory %, disk %, plus absolute memory values.
        3. Fall back to APM timeslice Metric events if SystemSample is empty.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")

        since_iso = self._since_iso(days)

        try:
            self._logger.debug(
                f"[DEBUG] [api_client] Fetching infrastructure metrics: "
                f"app_id={app_id}, days={days}"
            )

            # ── Step 1: Discover hostname ────────────────────────────────
            host_nrql = (
                f"SELECT uniques(host) FROM Transaction "
                f"WHERE appId = '{app_id}' SINCE '{since_iso}'"
            )
            host_results = self._nrql_request(host_nrql, "host_discovery")
            hosts = []
            for r in host_results:
                h = r.get('uniques.host', [])
                if isinstance(h, list):
                    hosts.extend(h)
            hostname = hosts[0] if hosts else None

            metrics = {
                'cpu_percent': None,
                'memory_percent': None,
                'memory_used_gb': None,
                'memory_total_gb': None,
                'disk_percent': None,
                'host_name': hostname,
                'instance_count': len(hosts) if hosts else None,
            }

            # ── Step 2: SystemSample (Infrastructure agent) ──────────────
            if hostname:
                sys_nrql = (
                    f"SELECT average(cpuPercent) as 'cpu_pct', "
                    f"average(memoryUsedPercent) as 'mem_pct', "
                    f"average(memoryUsedBytes)/1073741824 as 'used_gb', "
                    f"average(memoryTotalBytes)/1073741824 as 'total_gb', "
                    f"average(diskUtilizationPercent) as 'disk_pct' "
                    f"FROM SystemSample WHERE hostname = '{hostname}' "
                    f"SINCE '{since_iso}'"
                )
                sys_results = self._nrql_request(sys_nrql, "system_sample")
                if sys_results:
                    row = sys_results[0]
                    metrics['cpu_percent']    = self._safe_float(row.get('cpu_pct'))
                    metrics['memory_percent'] = self._safe_float(row.get('mem_pct'))
                    metrics['memory_used_gb'] = self._safe_float(row.get('used_gb'))
                    metrics['memory_total_gb']= self._safe_float(row.get('total_gb'))
                    metrics['disk_percent']   = self._safe_float(row.get('disk_pct'))

            # ── Step 3: Fallback to APM timeslice Metric ─────────────────
            if metrics['cpu_percent'] is None:
                self._logger.debug(
                    "[DEBUG] [api_client] No SystemSample data, falling back to APM timeslice"
                )
                util_nrql = (
                    f"SELECT average(newrelic.timeslice.value)*100 as 'cpu_pct' "
                    f"FROM Metric WHERE appId = '{app_id}' "
                    f"AND metricTimesliceName = 'CPU/User/Utilization' "
                    f"SINCE '{since_iso}'"
                )
                util_results = self._nrql_request(util_nrql, "cpu_utilization_fallback")
                if util_results:
                    metrics['cpu_percent'] = self._safe_float(
                        util_results[0].get('cpu_pct')
                    )

            if metrics['memory_used_gb'] is None:
                mem_nrql = (
                    f"SELECT average(newrelic.timeslice.value) as 'mem_mb' "
                    f"FROM Metric WHERE appId = '{app_id}' "
                    f"AND metricTimesliceName = 'Memory/Physical' "
                    f"SINCE '{since_iso}'"
                )
                mem_results = self._nrql_request(mem_nrql, "memory_fallback")
                if mem_results:
                    mb = self._safe_float(mem_results[0].get('mem_mb'))
                    if mb is not None:
                        metrics['memory_used_gb'] = round(mb / 1024, 2)

            # ── Legacy compatibility keys ────────────────────────────────
            # Health calculator expects 'cpu_usage' as 0.0-1.0 and
            # 'memory_usage' as 0.0-1.0
            cpu_pct = metrics['cpu_percent']
            mem_pct = metrics['memory_percent']
            metrics['cpu_usage'] = round(cpu_pct / 100, 4) if cpu_pct is not None else None
            metrics['memory_usage'] = round(mem_pct / 100, 4) if mem_pct is not None else None
            metrics['memory_physical_mb'] = (
                round(metrics['memory_used_gb'] * 1024, 1)
                if metrics['memory_used_gb'] is not None else None
            )
            metrics['disk_io'] = None  # not available as MB/s

            timestamp = datetime.now(_EST).isoformat()
            response_dict = {
                'app_id': app_id,
                'timestamp': timestamp,
                'infrastructure': metrics
            }
            self._logger.info(
                f"[INFO] [api_client] Fetched infrastructure metrics for "
                f"app_id={app_id}, host={hostname}"
            )
            return response_dict

        except Exception as e:
            error_msg = f"Failed to fetch infrastructure metrics: {type(e).__name__}: {str(e)}"
            self._logger.error(
                f"[ERROR] [api_client] {error_msg}. app_id={app_id}, days={days}"
            )
            raise
    
    def fetch_database_metrics(
        self, 
        app_id: str, 
        days: int
    ) -> Dict[str, Any]:
        """
        Fetch database metrics for a specific application.
        
        Retrieves query time, slow queries, connection pool usage, and database calls
        for the specified time window.
        
        Args:
            app_id: New Relic application ID
            days: Time window in days (must be 3, 7, 14, or 30)
            
        Returns:
            Dictionary with structure:
            {
                "app_id": str,
                "timestamp": str (ISO 8601),
                "database": {
                    "query_time": float or None (milliseconds),
                    "slow_queries": int or None,
                    "connection_pool_usage": float or None (0.0 to 1.0),
                    "database_calls": int or None
                }
            }
            
        Raises:
            ValueError: If app_id is empty or days not in [3, 7, 14, 30]
            requests.exceptions.*: For API request failures
        """
        from datetime import datetime, timedelta
        
        # Validate app_id
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        # Validate days parameter
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        # Calculate time window (since timestamp)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.strftime('%Y-%m-%d %H:%M:%S')
        
        # Construct NerdGraph NRQL query for database metrics
        # Note: NRQL string must have values injected via f-string, not GraphQL variables
        nrql_query = f"SELECT average(databaseDuration) * 1000 as 'query.time', filter(count(*), WHERE databaseDuration > 1.0) as 'slow.queries', average(databaseCallCount) as 'db.calls', percentage(count(*), WHERE databaseCallCount > 10) as 'pool.usage' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}'"
        
        query = f"""
        query($accountId: Int!) {{
          actor {{
            account(id: $accountId) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'accountId': int(self._account_id)
        }
        
        try:
            # Make API request
            self._logger.debug(
                f"[DEBUG] [api_client] Fetching database metrics: "
                f"app_id={app_id}, days={days}, since={since_iso}"
            )
            
            response = self._make_request(query, variables)
            
            # Extract metrics from response
            results = response.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
            
            if not results:
                # No data available
                metrics = {
                    'query_time': None,
                    'slow_queries': None,
                    'connection_pool_usage': None,
                    'database_calls': None
                }
            else:
                result = results[0]
                
                # query_time already in milliseconds from NRQL (* 1000)
                query_time = self._safe_float(result.get('query.time'))
                
                # slow_queries as integer
                slow_queries = self._safe_int(result.get('slow.queries'))
                
                # database_calls as integer
                database_calls = self._safe_int(result.get('db.calls'))
                
                # Convert pool usage from percentage to decimal
                pool_pct = self._safe_float(result.get('pool.usage'))
                connection_pool_usage = (pool_pct / 100.0) if pool_pct is not None else None
                
                metrics = {
                    'query_time': query_time,
                    'slow_queries': slow_queries,
                    'connection_pool_usage': connection_pool_usage,
                    'database_calls': database_calls
                }
            
            # Generate current timestamp with UTC indicator
            timestamp = datetime.now(_EST).isoformat()
            
            # Build response dictionary
            response_dict = {
                'app_id': app_id,
                'timestamp': timestamp,
                'database': metrics
            }
            
            # Log success
            self._logger.info(
                f"[INFO] [api_client] Fetched database metrics for app_id={app_id}, days={days}"
            )
            
            return response_dict
            
        except Exception as e:
            # Log error with context
            error_msg = f"Failed to fetch database metrics: {type(e).__name__}: {str(e)}"
            self._logger.error(
                f"[ERROR] [api_client] {error_msg}. app_id={app_id}, days={days}"
            )
            # Re-raise original exception
            raise
    
    def fetch_transaction_metrics(
        self, 
        app_id: str, 
        days: int
    ) -> Dict[str, Any]:
        """
        Fetch transaction/API metrics for a specific application.
        
        Retrieves transaction time, external calls, and API endpoint performance
        for the specified time window.
        
        Args:
            app_id: New Relic application ID
            days: Time window in days (must be 3, 7, 14, or 30)
            
        Returns:
            Dictionary with structure:
            {
                "app_id": str,
                "timestamp": str (ISO 8601),
                "transactions": {
                    "transaction_time": float or None (milliseconds),
                    "external_calls": int or None,
                    "external_latency": float or None (milliseconds),
                    "api_endpoints": list or None (top endpoints with performance)
                }
            }
            
        Raises:
            ValueError: If app_id is empty or days not in [3, 7, 14, 30]
            requests.exceptions.*: For API request failures
        """
        from datetime import datetime, timedelta
        
        # Validate app_id
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        # Validate days parameter
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        # Calculate time window (since timestamp)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.strftime('%Y-%m-%d %H:%M:%S')
        
        # Construct NerdGraph NRQL query for transaction metrics
        # Covers ALL transaction types (Web + Background/OtherTransaction)
        # Note: NRQL string must have values injected via f-string, not GraphQL variables
        nrql_query = f"SELECT average(duration) * 1000 as 'transaction.time', filter(count(*), WHERE externalDuration > 0) as 'external.calls', average(externalDuration) * 1000 as 'external.latency', filter(count(*), WHERE transactionType = 'Web') as 'web.count', filter(count(*), WHERE transactionType != 'Web') as 'other.count', uniques(name, 10) as 'api.endpoints' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}'"
        
        query = f"""
        query($accountId: Int!) {{
          actor {{
            account(id: $accountId) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}
        """
        
        variables = {
            'accountId': int(self._account_id)
        }
        
        try:
            # Make API request
            self._logger.debug(
                f"[DEBUG] [api_client] Fetching transaction metrics: "
                f"app_id={app_id}, days={days}, since={since_iso}"
            )
            
            response = self._make_request(query, variables)
            
            # Extract metrics from response
            results = response.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
            
            if not results:
                # No data available
                metrics = {
                    'transaction_time': None,
                    'external_calls': None,
                    'external_latency': None,
                    'api_endpoints': None
                }
            else:
                result = results[0]
                
                # Transaction time in milliseconds (already converted in NRQL)
                transaction_time = self._safe_float(result.get('transaction.time'))
                
                # External calls count
                external_calls = self._safe_int(result.get('external.calls'))
                
                # External latency in milliseconds (already converted in NRQL)
                external_latency = self._safe_float(result.get('external.latency'))

                # Transaction type breakdown
                web_count   = self._safe_int(result.get('web.count'))
                other_count = self._safe_int(result.get('other.count'))
                
                # Parse transaction names (may be array or comma-separated string)
                api_endpoints_raw = result.get('api.endpoints')
                if api_endpoints_raw is None:
                    api_endpoints = None
                elif isinstance(api_endpoints_raw, list):
                    api_endpoints = [str(e) for e in api_endpoints_raw if e]
                elif isinstance(api_endpoints_raw, str):
                    # Handle comma-separated string
                    api_endpoints = [e.strip() for e in api_endpoints_raw.split(',') if e.strip()]
                else:
                    api_endpoints = None
                
                metrics = {
                    'transaction_time': transaction_time,
                    'external_calls': external_calls,
                    'external_latency': external_latency,
                    'web_count': web_count,
                    'other_count': other_count,
                    'api_endpoints': api_endpoints
                }
            
            # Generate current timestamp with UTC indicator
            timestamp = datetime.now(_EST).isoformat()
            
            # Build response dictionary
            response_dict = {
                'app_id': app_id,
                'timestamp': timestamp,
                'transactions': metrics
            }
            
            # Log success
            self._logger.info(
                f"[INFO] [api_client] Fetched transaction metrics for app_id={app_id}, days={days}"
            )
            
            return response_dict
            
        except Exception as e:
            # Log error with context
            error_msg = f"Failed to fetch transaction metrics: {type(e).__name__}: {str(e)}"
            self._logger.error(
                f"[ERROR] [api_client] {error_msg}. app_id={app_id}, days={days}"
            )
            # Re-raise original exception
            raise
    
    def _nrql_request(self, nrql_query: str, label: str = "NRQL") -> list:
        """Helper to execute a NRQL query and return the results list."""
        query = f"""
        query($accountId: Int!) {{
          actor {{
            account(id: $accountId) {{
              nrql(query: "{nrql_query}") {{
                results
              }}
            }}
          }}
        }}
        """
        variables = {'accountId': int(self._account_id)}
        response = self._make_request(query, variables)
        return response.get('data', {}).get('actor', {}).get('account', {}).get('nrql', {}).get('results', [])
    
    def _since_iso(self, days: int) -> str:
        """Calculate ISO-formatted SINCE timestamp for NRQL queries."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return since.strftime('%Y-%m-%d %H:%M:%S')
    
    def fetch_error_details(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch detailed error breakdown with stack traces from TransactionError events.
        
        Returns error class, count, message, and stack trace for root cause analysis.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        nrql_query = f"SELECT count(*) as 'count', latest(error.message) as 'message', latest(stack_trace) as 'stack_trace' FROM TransactionError WHERE appId = '{app_id}' SINCE '{since_iso}' FACET error.class LIMIT 50"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching error details: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "error_details")
            
            error_details = []
            for result in results:
                error_details.append({
                    'error_class': str(result.get('error.class', 'Unknown')),
                    'count': self._safe_int(result.get('count')),
                    'message': str(result.get('message', '')) if result.get('message') else None,
                    'stack_trace': str(result.get('stack_trace', '')) if result.get('stack_trace') else None
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(error_details)} error classes for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'error_details': error_details}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch error details: {e}. app_id={app_id}")
            raise
    
    def fetch_slow_transactions(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch per-endpoint performance breakdown (top 20 slowest transactions).
        
        Includes average duration, P95, call count, database time, and external time per endpoint.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        # Fetch top 50 slowest transactions across ALL types (Web + Background/OtherTransaction)
        nrql_query = f"SELECT average(duration) * 1000 as 'avg_duration_ms', percentile(duration, 95) * 1000 as 'p95_ms', count(*) as 'call_count', average(databaseDuration) * 1000 as 'db_time_ms', average(databaseCallCount) as 'db_call_count', average(externalDuration) * 1000 as 'external_time_ms', average(externalCallCount) as 'external_call_count', latest(transactionType) as 'transaction_type' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}' FACET name LIMIT 50"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching slow transactions: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "slow_transactions")
            
            slow_transactions = []
            for result in results:
                slow_transactions.append({
                    'name': str(result.get('name', 'Unknown')),
                    'transaction_type': str(result.get('transaction_type', 'Web')),
                    'avg_duration_ms': self._safe_float(result.get('avg_duration_ms')),
                    'p95_ms': self._safe_float(result.get('p95_ms')),
                    'call_count': self._safe_int(result.get('call_count')),
                    'db_time_ms': self._safe_float(result.get('db_time_ms')),
                    'db_call_count': self._safe_int(result.get('db_call_count')),
                    'external_time_ms': self._safe_float(result.get('external_time_ms')),
                    'external_call_count': self._safe_int(result.get('external_call_count'))
                })
            
            # Sort client-side by avg duration descending (slowest first)
            slow_transactions.sort(key=lambda x: x['avg_duration_ms'] or 0, reverse=True)
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(slow_transactions)} slow transactions for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'slow_transactions': slow_transactions}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch slow transactions: {e}. app_id={app_id}")
            raise
    
    def fetch_database_details(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch detailed database segment breakdown (top queries by table/operation).
        
        Uses DatastoreSegment events to identify specific slow queries and tables.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        # Use Span events with db.system (works for .NET / Java / Node agents).
        # DatastoreSegment events are absent for many agent versions.
        nrql_query = (
            f"SELECT average(duration) * 1000 as 'avg_duration_ms', "
            f"percentile(duration, 95) * 1000 as 'p95_ms', "
            f"count(*) as 'call_count', "
            f"sum(duration) * 1000 as 'total_time_ms' "
            f"FROM Span "
            f"WHERE appId = '{app_id}' AND db.system IS NOT NULL "
            f"SINCE '{since_iso}' "
            f"FACET db.system, db.operation, db.collection "
            f"LIMIT 20"
        )
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching database details: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "database_details")
            
            db_details = []
            for result in results:
                facet = result.get('facet', [])
                db_details.append({
                    'datastore_type': str(facet[0]) if len(facet) > 0 else 'Unknown',
                    'operation': str(facet[1]) if len(facet) > 1 else 'Unknown',
                    'table': str(facet[2]) if len(facet) > 2 else 'Unknown',
                    'avg_duration_ms': self._safe_float(result.get('avg_duration_ms')),
                    'p95_ms': self._safe_float(result.get('p95_ms')),
                    'call_count': self._safe_int(result.get('call_count')),
                    'total_time_ms': self._safe_float(result.get('total_time_ms'))
                })
            
            # Sort by total_time_ms descending — most expensive operations first
            db_details.sort(key=lambda x: x['total_time_ms'] or 0, reverse=True)
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(db_details)} database segments for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'database_details': db_details}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch database details: {e}. app_id={app_id}")
            raise
    
    def fetch_slow_db_transactions(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch top 20 transactions ranked by average database time.

        Identifies which endpoints are spending the most time waiting on the database,
        which is the primary target for query optimisation work.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")

        since_iso = self._since_iso(days)
        # Only include transactions that actually performed DB work
        nrql_query = (
            f"SELECT average(databaseDuration) * 1000 as 'avg_db_ms', "
            f"percentile(databaseDuration, 95) * 1000 as 'p95_db_ms', "
            f"average(databaseCallCount) as 'avg_db_calls', "
            f"count(*) as 'call_count', "
            f"average(duration) * 1000 as 'avg_total_ms', "
            f"latest(transactionType) as 'transaction_type' "
            f"FROM Transaction "
            f"WHERE appId = '{app_id}' AND databaseDuration > 0 "
            f"SINCE '{since_iso}' "
            f"FACET name LIMIT 50"
        )

        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching slow DB transactions: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "slow_db_transactions")

            rows = []
            for result in results:
                rows.append({
                    'name':             str(result.get('name', 'Unknown')),
                    'transaction_type': str(result.get('transaction_type', 'Web')),
                    'avg_db_ms':        self._safe_float(result.get('avg_db_ms')),
                    'p95_db_ms':        self._safe_float(result.get('p95_db_ms')),
                    'avg_db_calls':     self._safe_float(result.get('avg_db_calls')),
                    'call_count':       self._safe_int(result.get('call_count')),
                    'avg_total_ms':     self._safe_float(result.get('avg_total_ms')),
                })

            # Sort by avg_db_ms descending — worst DB offenders first
            rows.sort(key=lambda x: x['avg_db_ms'] or 0, reverse=True)

            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(
                f"[INFO] [api_client] Fetched {len(rows)} slow-DB transactions for app_id={app_id}"
            )
            return {'app_id': app_id, 'timestamp': timestamp, 'slow_db_transactions': rows}
        except Exception as e:
            self._logger.error(
                f"[ERROR] [api_client] Failed to fetch slow DB transactions: {e}. app_id={app_id}"
            )
            raise

    def fetch_external_services(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch external service dependency breakdown by host.
        
        Identifies which downstream services are slow or high-volume.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        nrql_query = f"SELECT average(duration) * 1000 as 'avg_duration_ms', count(*) as 'call_count', percentile(duration, 95) * 1000 as 'p95_ms' FROM ExternalSegment WHERE appId = '{app_id}' SINCE '{since_iso}' FACET host LIMIT 15"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching external services: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "external_services")
            
            external_services = []
            for result in results:
                external_services.append({
                    'host': str(result.get('host', 'Unknown')),
                    'avg_duration_ms': self._safe_float(result.get('avg_duration_ms')),
                    'call_count': self._safe_int(result.get('call_count')),
                    'p95_ms': self._safe_float(result.get('p95_ms'))
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(external_services)} external services for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'external_services': external_services}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch external services: {e}. app_id={app_id}")
            raise
    
    def fetch_application_logs(self, app_id: str, days: int, app_name: str = None) -> Dict[str, Any]:
        """
        Fetch application error/warning logs that may indicate issues.
        
        Downloads ERROR, WARN, and FATAL level logs plus messages containing
        exception/error/fail/timeout keywords for comprehensive issue analysis.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)

        # Compute entity.guid deterministically: base64(accountId|APM|APPLICATION|appId)
        # This reliably links to APM-forwarded logs regardless of how entity.name is stored
        import base64 as _b64
        entity_guid = _b64.b64encode(
            f"{self._account_id}|APM|APPLICATION|{app_id}".encode()
        ).decode()

        # Fetch all log levels — some apps only emit INFO with error details in the message.
        # Prioritise ERROR/WARN entries but also capture INFO lines that mention exceptions/failures.
        nrql_query = (
            f"SELECT message, level, timestamp, error.class, error.message, error.stack "
            f"FROM Log "
            f"WHERE entity.guid = '{entity_guid}' "
            f"AND ("
            f"level IN ('ERROR', 'WARN', 'WARNING', 'FATAL', 'error', 'warn', 'fatal') "
            f"OR message LIKE '%exception%' OR message LIKE '%Exception%' "
            f"OR message LIKE '%timeout%'   OR message LIKE '%Timeout%' "
            f"OR message LIKE '%fail%'      OR message LIKE '%Fail%' "
            f"OR message LIKE '%error%'     OR message LIKE '%Error%'"
            f") "
            f"SINCE '{since_iso}' LIMIT 500"
        )
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching application logs: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "application_logs")
            
            logs = []
            for result in results:
                message = str(result.get('message', ''))[:2000]
                # Strip base64-encoded blobs (e.g. PDF labels) that add noise
                if '"labelImage":"' in message:
                    message = message[:message.index('"labelImage":"')] + '"labelImage":"[base64 removed]"}'
                logs.append({
                    'timestamp': str(result.get('timestamp', '')),
                    'level': str(result.get('level', 'UNKNOWN')),
                    'message': message,
                    'error_class': str(result.get('error.class', '')) if result.get('error.class') else None,
                    'error_message': str(result.get('error.message', '')) if result.get('error.message') else None,
                    'error_stack': str(result.get('error.stack', ''))[:3000] if result.get('error.stack') else None
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(logs)} log entries for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'application_logs': logs}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch application logs: {e}. app_id={app_id}")
            raise
    
    def fetch_log_volume(self, app_id: str, days: int, app_name: str = None) -> Dict[str, Any]:
        """
        Fetch log volume counts grouped by log level.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        import base64 as _b64
        entity_guid = _b64.b64encode(f"{self._account_id}|APM|APPLICATION|{app_id}".encode()).decode()
        nrql_query = f"SELECT count(*) as 'count' FROM Log WHERE entity.guid = '{entity_guid}' SINCE '{since_iso}' FACET level LIMIT 20"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching log volume: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "log_volume")
            
            log_volume = []
            for result in results:
                level = str(result.get('level', 'UNKNOWN'))
                count = self._safe_int(result.get('count')) or 0
                log_volume.append({'level': level, 'count': count})
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched log volume for app_id={app_id}: {log_volume}")
            return {'app_id': app_id, 'timestamp': timestamp, 'log_volume': log_volume}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch log volume: {e}. app_id={app_id}")
            raise
    
    def fetch_alerts(self, app_id: str, days: int, app_name: str = None) -> Dict[str, Any]:
        """
        Fetch alert/incident history from NrAiIncident events.
        
        These represent New Relic's own automated health analysis — the most
        direct signal of application health issues.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        import base64 as _b64
        entity_guid = _b64.b64encode(f"{self._account_id}|APM|APPLICATION|{app_id}".encode()).decode()
        nrql_query = f"SELECT title, priority, state, conditionName, policyName, openTime, closeTime, durationSeconds FROM NrAiIncident WHERE entity.guid = '{entity_guid}' SINCE '{since_iso}' LIMIT 50"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching alerts: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "alerts")
            
            alerts = []
            for result in results:
                alerts.append({
                    'title': str(result.get('title', '')),
                    'priority': str(result.get('priority', 'UNKNOWN')),
                    'state': str(result.get('state', 'UNKNOWN')),
                    'condition_name': str(result.get('conditionName', '')) if result.get('conditionName') else None,
                    'policy_name': str(result.get('policyName', '')) if result.get('policyName') else None,
                    'open_time': result.get('openTime'),
                    'close_time': result.get('closeTime'),
                    'duration_seconds': self._safe_int(result.get('durationSeconds'))
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(alerts)} alerts for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'alerts': alerts}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch alerts: {e}. app_id={app_id}")
            raise
    
    def fetch_hourly_trends(self, app_id: str, days: int) -> Dict[str, Any]:
        """
        Fetch hourly performance trends using TIMESERIES.
        
        Provides time-series data for trend analysis (is it getting better or worse?).
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        nrql_query = f"SELECT average(duration) * 1000 as 'avg_response_ms', rate(count(*), 1 minute) as 'throughput_rpm', percentage(count(*), WHERE error IS true) / 100 as 'error_rate' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}' TIMESERIES 1 hour"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching hourly trends: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "hourly_trends")
            
            trends = []
            for result in results:
                trends.append({
                    'begin_time': result.get('beginTimeSeconds'),
                    'end_time': result.get('endTimeSeconds'),
                    'avg_response_ms': self._safe_float(result.get('avg_response_ms')),
                    'throughput_rpm': self._safe_float(result.get('throughput_rpm')),
                    'error_rate': self._safe_float(result.get('error_rate'))
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(trends)} hourly trend points for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'hourly_trends': trends}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch hourly trends: {e}. app_id={app_id}")
            raise
    
    def fetch_deployments(self, app_id: str, days: int, app_name: str = None) -> Dict[str, Any]:
        """
        Fetch deployment markers to correlate issues with releases.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        since_iso = self._since_iso(days)
        entity_filter = f"entity.name = '{app_name}'" if app_name else f"entity.guid LIKE '%{app_id}%'"
        nrql_query = f"SELECT timestamp, revision, description, user, changelog FROM Deployment WHERE {entity_filter} SINCE '{since_iso}' LIMIT 20"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching deployments: app_id={app_id}, days={days}")
            results = self._nrql_request(nrql_query, "deployments")
            
            deployments = []
            for result in results:
                deployments.append({
                    'timestamp': result.get('timestamp'),
                    'revision': str(result.get('revision', '')) if result.get('revision') else None,
                    'description': str(result.get('description', '')) if result.get('description') else None,
                    'user': str(result.get('user', '')) if result.get('user') else None,
                    'changelog': str(result.get('changelog', '')) if result.get('changelog') else None
                })
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched {len(deployments)} deployments for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'deployments': deployments}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch deployments: {e}. app_id={app_id}")
            raise
    
    def fetch_baselines(self, app_id: str) -> Dict[str, Any]:
        """
        Fetch 7-day rolling baseline averages for anomaly detection.
        
        Always queries last 7 days regardless of the assessment period,
        providing a stable reference point for comparison.
        """
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        since_iso = self._since_iso(7)  # Always 7-day baseline
        nrql_query = f"SELECT average(duration) * 1000 as 'baseline_response_ms', rate(count(*), 1 minute) as 'baseline_throughput_rpm', percentage(count(*), WHERE error IS true) / 100 as 'baseline_error_rate', count(*) as 'baseline_total_requests' FROM Transaction WHERE appId = '{app_id}' SINCE '{since_iso}'"
        
        try:
            self._logger.debug(f"[DEBUG] [api_client] Fetching baselines: app_id={app_id}")
            results = self._nrql_request(nrql_query, "baselines")
            
            if not results:
                baselines = {
                    'response_time_7d_avg_ms': None,
                    'throughput_7d_avg_rpm': None,
                    'error_rate_7d_avg': None,
                    'total_requests_7d': None
                }
            else:
                result = results[0]
                baselines = {
                    'response_time_7d_avg_ms': self._safe_float(result.get('baseline_response_ms')),
                    'throughput_7d_avg_rpm': self._safe_float(result.get('baseline_throughput_rpm')),
                    'error_rate_7d_avg': self._safe_float(result.get('baseline_error_rate')),
                    'total_requests_7d': self._safe_int(result.get('baseline_total_requests'))
                }
            
            timestamp = datetime.now(_EST).isoformat()
            self._logger.info(f"[INFO] [api_client] Fetched baselines for app_id={app_id}")
            return {'app_id': app_id, 'timestamp': timestamp, 'baselines': baselines}
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to fetch baselines: {e}. app_id={app_id}")
            raise
    
    def collect_all_metrics(
        self,
        app_id: str,
        days: int,
        app_name: str = "app",
        use_cache: bool = True,
        cache_ttl: int = 3600
    ) -> Dict[str, Any]:
        """
        Collect all metric categories with caching and progress indicators.
        
        Args:
            app_id: New Relic application ID
            days: Time window in days (must be 3, 7, 14, or 30)
            app_name: Application name for cache file naming
            use_cache: Whether to use cached data if available
            cache_ttl: Cache time-to-live in seconds (default: 3600)
            
        Returns:
            Dictionary with all metric categories
        """
        # Validate inputs early (fail-fast)
        if not app_id or not app_id.strip():
            raise ValueError("app_id cannot be empty")
        
        ALLOWED_DAYS = [1, 3, 7, 14, 30]
        if days not in ALLOWED_DAYS:
            raise ValueError(f"days must be one of {ALLOWED_DAYS}, got {days}")
        
        # Check for cached data
        if use_cache:
            cached_data = self.load_from_cache(app_name, cache_ttl)
            if cached_data:
                return cached_data
        
        # Collect all metrics with progress indicators
        print(f"Collecting metrics for {app_name}...")
        
        all_metrics = {
            'app_id': app_id,
            'app_name': app_name,
            'collection_timestamp': datetime.now(_EST).isoformat(),
            'time_window_days': days
        }
        
        total_steps = 14
        step = 0
        
        # Core metrics (existing 5 categories)
        step += 1
        print(f"Fetching performance metrics... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['performance'] = self.fetch_performance_metrics(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Performance metrics collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching error metrics... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['errors'] = self.fetch_error_metrics(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Error metrics collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching infrastructure metrics... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['infrastructure'] = self.fetch_infrastructure_metrics(app_id, days, app_name=app_name)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Infrastructure metrics collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching database metrics... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['database'] = self.fetch_database_metrics(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Database metrics collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching transaction metrics... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['transactions'] = self.fetch_transaction_metrics(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Transaction metrics collected in {duration_ms}ms")
        
        # Detailed breakdowns (new)
        step += 1
        print(f"Fetching error details with stack traces... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['error_details'] = self.fetch_error_details(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Error details collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching slow transaction breakdown... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['slow_transactions'] = self.fetch_slow_transactions(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Slow transactions collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching database query details... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['database_details'] = self.fetch_database_details(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Database details collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching external service breakdown... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['external_services'] = self.fetch_external_services(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] External services collected in {duration_ms}ms")
        
        # Logs
        step += 1
        print(f"Fetching application logs (errors/warnings)... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['application_logs'] = self.fetch_application_logs(app_id, days, app_name=app_name)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Application logs collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching log volume by level... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['log_volume'] = self.fetch_log_volume(app_id, days, app_name=app_name)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Log volume collected in {duration_ms}ms")
        
        # Context data
        step += 1
        print(f"Fetching alert/incident history... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['alerts'] = self.fetch_alerts(app_id, days, app_name=app_name)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Alerts collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching hourly performance trends... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['hourly_trends'] = self.fetch_hourly_trends(app_id, days)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Hourly trends collected in {duration_ms}ms")
        
        step += 1
        print(f"Fetching baselines & deployments... ({step}/{total_steps})")
        start_time = time.time()
        all_metrics['baselines'] = self.fetch_baselines(app_id)
        all_metrics['deployments'] = self.fetch_deployments(app_id, days, app_name=app_name)
        duration_ms = int((time.time() - start_time) * 1000)
        self._logger.info(f"[INFO] [api_client] Baselines & deployments collected in {duration_ms}ms")
        
        print("✓ Data collection complete")
        
        # Save to cache
        if use_cache:
            cache_file = self.save_to_cache(all_metrics, app_name)
            print(f"Data saved to: {cache_file}")
        
        return all_metrics
    
    def save_to_cache(self, data: Dict[str, Any], app_name: str) -> str:
        """
        Save collected metrics to cache file.
        
        Args:
            data: Metrics dictionary to cache
            app_name: Application name for file naming
            
        Returns:
            Path to saved cache file
        """
        # Create data directory if it doesn't exist
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp_str = datetime.now(_EST).strftime("%Y-%m-%d-%H%M%S")
        filename = f"{app_name}-{timestamp_str}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Write JSON with indentation
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self._logger.info(f"[INFO] [api_client] Saved metrics to cache: {filepath}")
        
        return filepath
    
    def load_from_cache(self, app_name: str, cache_ttl: int = 3600) -> Optional[Dict[str, Any]]:
        """
        Load cached metrics if available and fresh.
        
        Args:
            app_name: Application name to find cache file
            cache_ttl: Cache time-to-live in seconds
            
        Returns:
            Cached data if fresh, None otherwise
        """
        data_dir = "data"
        if not os.path.exists(data_dir):
            return None
        
        # Find most recent cache file for this app (by modification time)
        pattern = os.path.join(data_dir, f"{app_name}-*.json")
        cache_files = glob.glob(pattern)
        
        if not cache_files:
            return None
        
        # Get newest file by modification time
        latest_cache = max(cache_files, key=os.path.getmtime)
        
        # Check file age
        file_mtime = os.path.getmtime(latest_cache)
        age_seconds = time.time() - file_mtime
        
        if age_seconds > cache_ttl:
            age_minutes = int(age_seconds / 60)
            self._logger.info(f"[INFO] [api_client] Cache stale (age: {age_minutes} minutes), fetching fresh data")
            return None
        
        # Load and return cached data
        try:
            with open(latest_cache, 'r') as f:
                data = json.load(f)
            
            age_minutes = int(age_seconds / 60)
            self._logger.info(f"[INFO] [api_client] Using cached data from {latest_cache}")
            print(f"Using cached data (age: {age_minutes} minutes)")
            
            return data
        except Exception as e:
            self._logger.error(f"[ERROR] [api_client] Failed to load cache: {e}")
            return None
    
    def cleanup_old_cache(self, retention_days: int = 30) -> int:
        """
        Remove cache files older than retention period.
        
        Args:
            retention_days: Number of days to retain cache files
            
        Returns:
            Number of files deleted
        """
        data_dir = "data"
        if not os.path.exists(data_dir):
            return 0
        
        # Find all JSON files
        pattern = os.path.join(data_dir, "*.json")
        cache_files = glob.glob(pattern)
        
        retention_seconds = retention_days * 24 * 60 * 60
        current_time = time.time()
        deleted_count = 0
        
        for filepath in cache_files:
            file_age = current_time - os.path.getmtime(filepath)
            
            if file_age > retention_seconds:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    self._logger.debug(f"[DEBUG] [api_client] Deleted old cache file: {filepath}")
                except Exception as e:
                    self._logger.error(f"[ERROR] [api_client] Failed to delete {filepath}: {e}")
        
        if deleted_count > 0:
            self._logger.info(f"[INFO] [api_client] Cleaned up {deleted_count} old cache files")
        
        return deleted_count
