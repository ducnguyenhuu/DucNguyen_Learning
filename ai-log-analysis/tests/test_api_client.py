"""
Comprehensive tests for New Relic API client module.

Tests cover:
- ApiClient initialization
- Successful API requests
- Retry logic for transient errors
- Fail-fast behavior for rate limits and auth errors
- Request configuration (headers, timeout, URL, method)
"""

import unittest
from unittest.mock import patch, Mock, call
import requests
from modules.api_client import ApiClient


class TestApiClientInitialization(unittest.TestCase):
    """Test ApiClient class initialization."""
    
    def test_init_with_required_params(self):
        """Test ApiClient initialization with required parameters."""
        client = ApiClient(api_key="test-key", account_id="12345")
        
        self.assertEqual(client._api_key, "test-key")
        self.assertEqual(client._account_id, "12345")
        self.assertEqual(client._timeout, 30)  # Default
        self.assertEqual(client._max_retries, 2)  # Default
        self.assertEqual(client._retry_delay, 5)  # Default
        self.assertEqual(client._endpoint, "https://api.newrelic.com/graphql")
    
    def test_init_with_custom_params(self):
        """Test ApiClient initialization with custom configuration."""
        client = ApiClient(
            api_key="custom-key",
            account_id="67890",
            timeout=60,
            max_retries=3,
            retry_delay=10
        )
        
        self.assertEqual(client._api_key, "custom-key")
        self.assertEqual(client._account_id, "67890")
        self.assertEqual(client._timeout, 60)
        self.assertEqual(client._max_retries, 3)
        self.assertEqual(client._retry_delay, 10)
    
    def test_init_creates_logger(self):
        """Test that ApiClient creates logger instance."""
        client = ApiClient(api_key="test-key", account_id="12345")
        
        self.assertIsNotNone(client._logger)
        self.assertEqual(client._logger.name, 'api_client')


class TestApiClientSuccessfulRequests(unittest.TestCase):
    """Test successful API request scenarios."""
    
    def setUp(self):
        """Set up test client."""
        self.client = ApiClient(api_key="test-key", account_id="12345")
    
    @patch('modules.api_client.requests.post')
    def test_successful_request_basic(self, mock_post):
        """Test successful API request with basic query."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"result": "success"}}
        mock_response.content = b'{"data": {"result": "success"}}'
        mock_post.return_value = mock_response
        
        # Execute request
        result = self.client._make_request("query { test }")
        
        # Verify result
        self.assertEqual(result, {"data": {"result": "success"}})
        
        # Verify request was made once
        mock_post.assert_called_once()
    
    @patch('modules.api_client.requests.post')
    def test_request_headers_correct(self, mock_post):
        """Test that request includes correct authentication headers."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.content = b'{"data": "success"}'
        mock_post.return_value = mock_response
        
        # Execute request
        self.client._make_request("query { test }")
        
        # Verify headers
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        self.assertEqual(headers['Api-Key'], 'test-key')
        self.assertEqual(headers['Content-Type'], 'application/json')
    
    @patch('modules.api_client.requests.post')
    def test_request_url_and_method(self, mock_post):
        """Test that request uses correct URL and POST method."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.content = b'{"data": "success"}'
        mock_post.return_value = mock_response
        
        # Execute request
        self.client._make_request("query { test }")
        
        # Verify URL
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api.newrelic.com/graphql")
    
    @patch('modules.api_client.requests.post')
    def test_request_timeout_configured(self, mock_post):
        """Test that request timeout is properly configured."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.content = b'{"data": "success"}'
        mock_post.return_value = mock_response
        
        # Execute request
        self.client._make_request("query { test }")
        
        # Verify timeout
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['timeout'], 30)
    
    @patch('modules.api_client.requests.post')
    def test_request_with_variables(self, mock_post):
        """Test request with GraphQL variables."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.content = b'{"data": "success"}'
        mock_post.return_value = mock_response
        
        # Execute request with variables
        variables = {"appId": "123", "since": "2024-01-01"}
        self.client._make_request("query($appId: ID!) { test }", variables)
        
        # Verify payload includes variables
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['variables'], variables)
        self.assertIn('query', payload)
    
    @patch('modules.api_client.requests.post')
    def test_graphql_error_in_response(self, mock_post):
        """Test GraphQL error in successful HTTP response."""
        # Mock HTTP 200 with GraphQL errors
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid app ID", "locations": [{"line": 1}]}],
            "data": None
        }
        mock_response.content = b'{"errors": [{"message": "Invalid app ID"}]}'
        mock_post.return_value = mock_response
        
        # Execute request and expect ValueError
        with self.assertRaises(ValueError) as context:
            self.client._make_request("query { test }")
        
        # Verify error message
        self.assertIn("GraphQL errors", str(context.exception))
        self.assertIn("Invalid app ID", str(context.exception))
    
    @patch('modules.api_client.requests.post')
    def test_empty_query_validation(self, mock_post):
        """Test that empty query raises ValueError."""
        # Empty string
        with self.assertRaises(ValueError) as context:
            self.client._make_request("")
        self.assertIn("query cannot be empty", str(context.exception).lower())
        
        # Whitespace only
        with self.assertRaises(ValueError) as context:
            self.client._make_request("   ")
        self.assertIn("query cannot be empty", str(context.exception).lower())
        
        # Verify no API calls were made
        mock_post.assert_not_called()


class TestApiClientRetryLogic(unittest.TestCase):
    """Test retry logic for transient errors."""
    
    def setUp(self):
        """Set up test client."""
        self.client = ApiClient(api_key="test-key", account_id="12345")
    
    @patch('modules.api_client.time.sleep')  # Mock sleep to speed up tests
    @patch('modules.api_client.requests.post')
    def test_retry_on_timeout_then_success(self, mock_post, mock_sleep):
        """Test retry on timeout then success on second attempt."""
        # First call: timeout, second call: success
        mock_post.side_effect = [
            requests.exceptions.Timeout("Connection timeout"),
            Mock(
                status_code=200, 
                json=lambda: {"data": "success"},
                content=b'{"data": "success"}'
            )
        ]
        
        # Execute request
        result = self.client._make_request("query { test }")
        
        # Verify retry happened
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(5)  # retry_delay
        self.assertEqual(result, {"data": "success"})
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_retry_on_connection_error_then_success(self, mock_post, mock_sleep):
        """Test retry on connection error then success."""
        # First call: connection error, second call: success
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Network error"),
            Mock(
                status_code=200, 
                json=lambda: {"data": "success"},
                content=b'{"data": "success"}'
            )
        ]
        
        # Execute request
        result = self.client._make_request("query { test }")
        
        # Verify retry happened
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(5)
        self.assertEqual(result, {"data": "success"})
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_retry_on_500_error_then_success(self, mock_post, mock_sleep):
        """Test retry on 500 server error then success."""
        # First call: 500 error, second call: success
        mock_error_response = Mock()
        mock_error_response.status_code = 500
        mock_error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_error_response
        )
        
        mock_success_response = Mock()
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": "success"}
        mock_success_response.content = b'{"data": "success"}'
        
        mock_post.side_effect = [mock_error_response, mock_success_response]
        
        # Execute request
        result = self.client._make_request("query { test }")
        
        # Verify retry happened
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(5)
        self.assertEqual(result, {"data": "success"})
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_retry_exhaustion_after_max_retries(self, mock_post, mock_sleep):
        """Test that retries are exhausted after max_retries attempts."""
        # All attempts fail with timeout
        mock_post.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        # Execute request and expect exception
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.client._make_request("query { test }")
        
        # Verify all retries were attempted (initial + 2 retries = 3 total)
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleep between retries
        
        # Verify error message
        self.assertIn("failed after 2 retries", str(context.exception))
        self.assertIn("Timeout", str(context.exception))
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_multiple_retries_before_success(self, mock_post, mock_sleep):
        """Test multiple retries before eventual success."""
        # Fail twice, succeed on third attempt
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout 1"),
            requests.exceptions.Timeout("Timeout 2"),
            Mock(
                status_code=200,
                json=lambda: {"data": "success"},
                content=b'{"data": "success"}'
            )
        ]
        
        # Execute request
        result = self.client._make_request("query { test }")
        
        # Verify retries
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        self.assertEqual(result, {"data": "success"})


class TestApiClientFailFastBehavior(unittest.TestCase):
    """Test fail-fast behavior for rate limits and auth errors."""
    
    def setUp(self):
        """Set up test client."""
        self.client = ApiClient(api_key="test-key", account_id="12345")
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_rate_limit_fails_fast_no_retry(self, mock_post, mock_sleep):
        """Test that rate limit (429) fails immediately without retry."""
        # Mock 429 response
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {'X-RateLimit-Reset': '2026-02-17T10:45:00'}
        mock_post.return_value = mock_response
        
        # Execute request and expect ValueError
        with self.assertRaises(ValueError) as context:
            self.client._make_request("query { test }")
        
        # Verify no retries happened
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()
        
        # Verify error message
        self.assertIn("rate limit exceeded", str(context.exception).lower())
        self.assertIn("2026-02-17T10:45:00", str(context.exception))
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_auth_error_401_fails_fast(self, mock_post, mock_sleep):
        """Test that 401 auth error fails immediately without retry."""
        # Mock 401 response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        # Execute request and expect ValueError
        with self.assertRaises(ValueError) as context:
            self.client._make_request("query { test }")
        
        # Verify no retries
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()
        
        # Verify error message
        self.assertIn("Invalid New Relic API key", str(context.exception))
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_auth_error_403_fails_fast(self, mock_post, mock_sleep):
        """Test that 403 auth error fails immediately without retry."""
        # Mock 403 response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_post.return_value = mock_response
        
        # Execute request and expect ValueError
        with self.assertRaises(ValueError) as context:
            self.client._make_request("query { test }")
        
        # Verify no retries
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()
        
        # Verify error message
        self.assertIn("Invalid New Relic API key", str(context.exception))
    
    @patch('modules.api_client.time.sleep')
    @patch('modules.api_client.requests.post')
    def test_client_error_400_fails_fast(self, mock_post, mock_sleep):
        """Test that 400 client error fails immediately without retry."""
        # Mock 400 response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Bad Request", response=mock_response
        )
        mock_post.return_value = mock_response
        
        # Execute request and expect HTTPError
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.client._make_request("query { test }")
        
        # Verify no retries
        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()


class TestApiClientConfigurationIntegration(unittest.TestCase):
    """Test integration with configuration system from Epic 1."""
    
    @patch('modules.config_loader._load_profile_config')
    @patch('modules.config_loader._load_yaml_defaults')
    @patch('modules.api_client.requests.post')
    def test_integration_with_config_loader(self, mock_post, mock_yaml, mock_profile):
        """Test ApiClient can be initialized with config from config_loader."""
        from modules.config_loader import load_config
        
        # Mock configuration data
        mock_yaml.return_value = {
            'api': {
                'timeout': 30,
                'max_retries': 2,
                'retry_delay': 5
            },
            'cache': {
                'staleness': 3600,
                'retention_days': 30
            },
            'defaults': {
                'time_period_days': 30
            },
            'logging_level': 'INFO',
            'days': 30  # Add required days field
        }
        
        mock_profile.return_value = {
            'api_key': 'test-api-key',
            'account_id': '12345',
            'app_ids': ['app1', 'app2']
        }
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "success"}
        mock_response.content = b'{"data": "success"}'
        mock_post.return_value = mock_response
        
        # Load configuration
        config = load_config(profile='dev')
        
        # Initialize client with config values
        client = ApiClient(
            api_key=config['api_key'],
            account_id=config['account_id'],
            timeout=config['api']['timeout'],
            max_retries=config['api']['max_retries'],
            retry_delay=config['api']['retry_delay']
        )
        
        # Verify client was initialized with config values
        self.assertEqual(client._timeout, 30)
        self.assertEqual(client._max_retries, 2)
        self.assertEqual(client._retry_delay, 5)
        self.assertEqual(client._api_key, 'test-api-key')
        self.assertEqual(client._account_id, '12345')
        
        # Verify client can make requests
        result = client._make_request("query { test }")
        self.assertEqual(result, {"data": "success"})


class TestPerformanceMetrics(unittest.TestCase):
    """Test fetch_performance_metrics method."""
    
    @patch.object(ApiClient, '_make_request')
    def test_fetch_performance_metrics_success(self, mock_request):
        """Test successful performance metrics fetch with valid data."""
        # Mock successful GraphQL response
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "avg_response_ms": 245.7,
                                    "p50_ms": 200.0,
                                    "p95_ms": 400.0,
                                    "p99_ms": 600.0,
                                    "throughput_rpm": 1234.5,
                                    "total_requests": 50000,
                                    "apdex_score": 0.87,
                                    "apdex_satisfied": 42500,
                                    "apdex_tolerating": 5000,
                                    "apdex_frustrated": 2500
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_performance_metrics(app_id="9876543", days=30)
        
        # Verify structure
        self.assertIn("app_id", result)
        self.assertEqual(result["app_id"], "9876543")
        self.assertIn("timestamp", result)
        self.assertIn("performance", result)
        
        # Verify performance metrics
        perf = result["performance"]
        self.assertIn("response_time", perf)
        self.assertIn("throughput", perf)
        self.assertIn("apdex_score", perf)
        
        # Verify data types
        self.assertIsInstance(perf["response_time"], float)
        self.assertIsInstance(perf["throughput"], float)
        self.assertIsInstance(perf["apdex_score"], float)
        
        # Verify values
        self.assertEqual(perf["response_time"], 245.7)
        self.assertEqual(perf["throughput"], 1234.5)
        self.assertEqual(perf["apdex_score"], 0.87)
        self.assertEqual(perf["p95_ms"], 400.0)
        self.assertEqual(perf["total_requests"], 50000)
        
        # Verify timestamp is ISO 8601 format
        self.assertRegex(result["timestamp"], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    def test_days_validation_valid_values(self):
        """Test days parameter validation with valid values."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Valid values: 1, 3, 7, 14, 30
        valid_days = [1, 3, 7, 14, 30]
        
        for days in valid_days:
            with patch.object(ApiClient, '_make_request') as mock_request:
                mock_request.return_value = {
                    "data": {
                        "actor": {
                            "account": {
                                "nrql": {
                                    "results": [{"avg_response_ms": 100.0, "throughput_rpm": 50.0, "apdex_score": 0.9}]
                                }
                            }
                        }
                    }
                }
                # Should not raise ValueError
                result = client.fetch_performance_metrics(app_id="123", days=days)
                self.assertIsNotNone(result)
    
    def test_days_validation_invalid_values(self):
        """Test days parameter validation with invalid values."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Invalid values (1 is now valid)
        invalid_days = [0, 2, 5, 15, 60, -1, 100]
        
        for days in invalid_days:
            with self.assertRaises(ValueError) as context:
                client.fetch_performance_metrics(app_id="123", days=days)
            
            self.assertIn("days must be one of", str(context.exception))
    
    def test_app_id_validation_empty(self):
        """Test app_id validation with empty string."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_performance_metrics(app_id="", days=30)
        
        self.assertIn("app_id cannot be empty", str(context.exception))
    
    def test_app_id_validation_whitespace(self):
        """Test app_id validation with whitespace only."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_performance_metrics(app_id="   ", days=30)
        
        self.assertIn("app_id cannot be empty", str(context.exception))
    
    @patch.object(ApiClient, '_make_request')
    def test_missing_data_uses_none(self, mock_request):
        """Test that missing metrics use None instead of empty strings or zero."""
        # Mock response with missing data
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "avg_response_ms": None,
                                    "throughput_rpm": 100.0,
                                    "apdex_score": None
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_performance_metrics(app_id="123", days=7)
        
        perf = result["performance"]
        self.assertIsNone(perf["response_time"])
        self.assertEqual(perf["throughput"], 100.0)
        self.assertIsNone(perf["apdex_score"])
    
    @patch.object(ApiClient, '_make_request')
    def test_numeric_values_converted_from_strings(self, mock_request):
        """Test that string numeric values are converted to float."""
        # Mock response with string values (some APIs return numbers as strings)
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "avg_response_ms": "245.7",  # String!
                                    "throughput_rpm": "1234.5",  # String!
                                    "apdex_score": "0.87"  # String!
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_performance_metrics(app_id="123", days=30)
        
        perf = result["performance"]
        
        # Should convert strings to float
        self.assertIsInstance(perf["response_time"], float)
        self.assertIsInstance(perf["throughput"], float)
        self.assertIsInstance(perf["apdex_score"], float)
        
        # Verify correct values after conversion
        self.assertEqual(perf["response_time"], 245.7)
        self.assertEqual(perf["throughput"], 1234.5)
        self.assertEqual(perf["apdex_score"], 0.87)
    
    @patch.object(ApiClient, '_make_request')
    def test_apdex_score_range_validation(self, mock_request):
        """Test that apdex_score is within 0.0 to 1.0 range."""
        # Mock response with various apdex scores
        test_cases = [0.0, 0.5, 0.87, 1.0]
        
        for apdex in test_cases:
            mock_request.return_value = {
                "data": {
                    "actor": {
                        "account": {
                            "nrql": {
                                "results": [
                                    {
                                        "avg_response_ms": 100.0,
                                        "throughput_rpm": 50.0,
                                        "apdex_score": apdex
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            
            client = ApiClient(api_key="test-key", account_id="123456")
            result = client.fetch_performance_metrics(app_id="123", days=30)
            
            score = result["performance"]["apdex_score"]
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
    
    @patch.object(ApiClient, '_make_request')
    def test_logging_on_success(self, mock_request):
        """Test that INFO log is generated on successful fetch."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {"avg_response_ms": 100.0, "throughput_rpm": 50.0, "apdex_score": 0.9}
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertLogs('api_client', level='INFO') as log:
            client.fetch_performance_metrics(app_id="9876543", days=30)
            
            # Check for success log message
            self.assertTrue(
                any("Fetched performance metrics for app_id=9876543" in message for message in log.output),
                f"Expected success log not found. Logs: {log.output}"
            )
    
    @patch.object(ApiClient, '_make_request')
    def test_logging_on_error(self, mock_request):
        """Test that ERROR log is generated on failure."""
        # Mock network error
        mock_request.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertLogs('api_client', level='ERROR') as log:
            with self.assertRaises(requests.exceptions.Timeout):
                client.fetch_performance_metrics(app_id="9876543", days=7)
            
            # Check for error log with context
            self.assertTrue(
                any("Failed to fetch performance metrics" in message for message in log.output),
                f"Expected error log not found. Logs: {log.output}"
            )
            self.assertTrue(
                any("app_id=9876543" in message for message in log.output),
                f"app_id not logged in error. Logs: {log.output}"
            )
            self.assertTrue(
                any("days=7" in message for message in log.output),
                f"days not logged in error. Logs: {log.output}"
            )
    
    @patch.object(ApiClient, '_make_request')
    def test_error_handling_network_error(self, mock_request):
        """Test error handling for network errors."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(requests.exceptions.ConnectionError):
            client.fetch_performance_metrics(app_id="123", days=30)
    
    @patch.object(ApiClient, '_make_request')
    def test_error_handling_graphql_error(self, mock_request):
        """Test error handling for GraphQL errors."""
        mock_request.side_effect = ValueError("GraphQL errors: Application not found")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_performance_metrics(app_id="invalid-app", days=30)
        
        self.assertIn("GraphQL errors", str(context.exception))
    
    @patch.object(ApiClient, '_make_request')
    def test_time_window_calculation(self, mock_request):
        """Test that time window (since parameter) is calculated correctly for different days."""
        from datetime import datetime, timedelta
        
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {"avg_response_ms": 100.0, "throughput_rpm": 50.0, "apdex_score": 0.9}
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Test with days=30
        result = client.fetch_performance_metrics(app_id="123", days=30)
        
        # Verify _make_request was called
        self.assertTrue(mock_request.called)
        
        # Get the query that was passed
        call_args = mock_request.call_args
        query = call_args[0][0] if call_args[0] else call_args[1].get('query')
        
        # Verify query contains NRQL with SINCE clause
        self.assertIn("SINCE", query)
        
        # Extract the since timestamp from query (it's embedded in NRQL string)
        # Query format: "... SINCE '2026-01-18T...Z'"
        import re
        since_match = re.search(r"SINCE '([^']+)'", query)
        self.assertIsNotNone(since_match, "SINCE timestamp not found in query")
        
        since_str = since_match.group(1)
        
        # Verify since is roughly 30 days ago (allowing some time variance for test execution)
        # Parse ISO 8601 timestamp
        since_dt = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
        expected_since = datetime.utcnow() - timedelta(days=30)
        
        # Allow 1 minute variance
        delta = abs((since_dt.replace(tzinfo=None) - expected_since).total_seconds())
        self.assertLess(delta, 60, f"Since timestamp {since_str} is not within 1 minute of expected 30 days ago")


class TestErrorMetrics(unittest.TestCase):
    """Test fetch_error_metrics method."""
    
    @patch.object(ApiClient, '_make_request')
    def test_fetch_error_metrics_success(self, mock_request):
        """Test successful error metrics fetch with valid data."""
        # Mock successful GraphQL response
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": 5.0,  # 5% as percentage
                                    "error.count": 127,
                                    "error.types": ["NullPointerException", "TimeoutError", "DatabaseConnectionError"]
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="9876543", days=30)
        
        # Verify structure
        self.assertIn("app_id", result)
        self.assertEqual(result["app_id"], "9876543")
        self.assertIn("timestamp", result)
        self.assertIn("errors", result)
        
        # Verify error metrics
        errors = result["errors"]
        self.assertIn("error_rate", errors)
        self.assertIn("error_count", errors)
        self.assertIn("error_types", errors)
        
        # Verify data types
        self.assertIsInstance(errors["error_rate"], float)
        self.assertIsInstance(errors["error_count"], int)
        self.assertIsInstance(errors["error_types"], list)
        
        # Verify error_rate is decimal (not percentage)
        self.assertEqual(errors["error_rate"], 0.05)  # 5% = 0.05
        self.assertEqual(errors["error_count"], 127)
        self.assertEqual(len(errors["error_types"]), 3)
        
        # Verify timestamp is ISO 8601 format with timezone offset
        self.assertRegex(result["timestamp"], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
    
    def test_days_validation_valid_values(self):
        """Test days parameter validation with valid values."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Valid values: 1, 3, 7, 14, 30
        valid_days = [1, 3, 7, 14, 30]
        
        for days in valid_days:
            with patch.object(ApiClient, '_make_request') as mock_request:
                mock_request.return_value = {
                    "data": {
                        "actor": {
                            "account": {
                                "nrql": {
                                    "results": [{"error.rate": 2.0, "error.count": 10, "error.types": []}]
                                }
                            }
                        }
                    }
                }
                # Should not raise ValueError
                result = client.fetch_error_metrics(app_id="123", days=days)
                self.assertIsNotNone(result)
    
    def test_days_validation_invalid_values(self):
        """Test days parameter validation with invalid values."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Invalid values (1 is now valid)
        invalid_days = [0, 2, 5, 15, 60, -1, 100]
        
        for days in invalid_days:
            with self.assertRaises(ValueError) as context:
                client.fetch_error_metrics(app_id="123", days=days)
            
            self.assertIn("days must be one of", str(context.exception))
    
    def test_app_id_validation_empty(self):
        """Test app_id validation with empty string."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_error_metrics(app_id="", days=30)
        
        self.assertIn("app_id cannot be empty", str(context.exception))
    
    def test_app_id_validation_whitespace(self):
        """Test app_id validation with whitespace only."""
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_error_metrics(app_id="   ", days=30)
        
        self.assertIn("app_id cannot be empty", str(context.exception))
    
    @patch.object(ApiClient, '_make_request')
    def test_missing_data_uses_none(self, mock_request):
        """Test that missing metrics use None instead of empty strings or zero."""
        # Mock response with missing data
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": None,
                                    "error.count": None,
                                    "error.types": None
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="123", days=7)
        
        errors = result["errors"]
        self.assertIsNone(errors["error_rate"])
        self.assertIsNone(errors["error_count"])
        self.assertIsNone(errors["error_types"])
    
    @patch.object(ApiClient, '_make_request')
    def test_error_rate_percentage_to_decimal_conversion(self, mock_request):
        """Test that error rate is converted from percentage to decimal."""
        # Test various percentages
        test_cases = [
            (0.0, 0.0),    # 0%
            (1.0, 0.01),   # 1%
            (5.0, 0.05),   # 5%
            (50.0, 0.5),   # 50%
            (100.0, 1.0),  # 100%
        ]
        
        for percentage, expected_decimal in test_cases:
            mock_request.return_value = {
                "data": {
                    "actor": {
                        "account": {
                            "nrql": {
                                "results": [
                                    {
                                        "error.rate": percentage,
                                        "error.count": 100,
                                        "error.types": []
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            
            client = ApiClient(api_key="test-key", account_id="123456")
            result = client.fetch_error_metrics(app_id="123", days=30)
            
            self.assertAlmostEqual(
                result["errors"]["error_rate"], 
                expected_decimal, 
                places=4,
                msg=f"Failed for {percentage}% -> {expected_decimal}"
            )
    
    @patch.object(ApiClient, '_make_request')
    def test_numeric_values_converted_from_strings(self, mock_request):
        """Test that string numeric values are converted to proper types."""
        # Mock response with string values (some APIs return numbers as strings)
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": "5.0",  # String!
                                    "error.count": "127",  # String!
                                    "error.types": ["Error1", "Error2"]
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="123", days=30)
        
        errors = result["errors"]
        
        # Should convert strings to appropriate types
        self.assertIsInstance(errors["error_rate"], float)
        self.assertIsInstance(errors["error_count"], int)
        
        # Verify correct values after conversion
        self.assertEqual(errors["error_rate"], 0.05)  # 5% -> 0.05
        self.assertEqual(errors["error_count"], 127)
    
    @patch.object(ApiClient, '_make_request')
    def test_error_types_as_list(self, mock_request):
        """Test that error_types is returned as list when API provides list."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": 2.0,
                                    "error.count": 50,
                                    "error.types": ["NullPointerException", "TimeoutError"]
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="123", days=30)
        
        error_types = result["errors"]["error_types"]
        self.assertIsInstance(error_types, list)
        self.assertEqual(len(error_types), 2)
        self.assertIn("NullPointerException", error_types)
        self.assertIn("TimeoutError", error_types)
    
    @patch.object(ApiClient, '_make_request')
    def test_error_types_comma_separated_string(self, mock_request):
        """Test that error_types is parsed from comma-separated string."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": 3.0,
                                    "error.count": 75,
                                    "error.types": "Error1, Error2, Error3"  # Comma-separated string!
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="123", days=30)
        
        error_types = result["errors"]["error_types"]
        self.assertIsInstance(error_types, list)
        self.assertEqual(len(error_types), 3)
        self.assertEqual(error_types, ["Error1", "Error2", "Error3"])
    
    @patch.object(ApiClient, '_make_request')
    def test_error_types_empty_list(self, mock_request):
        """Test that empty error_types is handled as None."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "error.rate": 0.0,
                                    "error.count": 0,
                                    "error.types": []  # Empty list
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_error_metrics(app_id="123", days=30)
        
        # Empty list should remain as list (not None)
        error_types = result["errors"]["error_types"]
        self.assertIsInstance(error_types, list)
        self.assertEqual(len(error_types), 0)
    
    @patch.object(ApiClient, '_make_request')
    def test_logging_on_success(self, mock_request):
        """Test that INFO log is generated on successful fetch."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {"error.rate": 2.0, "error.count": 10, "error.types": []}
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertLogs('api_client', level='INFO') as log:
            client.fetch_error_metrics(app_id="9876543", days=30)
            
            # Check for success log message
            self.assertTrue(
                any("Fetched error metrics for app_id=9876543" in message for message in log.output),
                f"Expected success log not found. Logs: {log.output}"
            )
    
    @patch.object(ApiClient, '_make_request')
    def test_logging_on_error(self, mock_request):
        """Test that ERROR log is generated on failure."""
        # Mock network error
        mock_request.side_effect = requests.exceptions.Timeout("Connection timeout")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertLogs('api_client', level='ERROR') as log:
            with self.assertRaises(requests.exceptions.Timeout):
                client.fetch_error_metrics(app_id="9876543", days=7)
            
            # Check for error log with context
            self.assertTrue(
                any("Failed to fetch error metrics" in message for message in log.output),
                f"Expected error log not found. Logs: {log.output}"
            )
            self.assertTrue(
                any("app_id=9876543" in message for message in log.output),
                f"app_id not logged in error. Logs: {log.output}"
            )
            self.assertTrue(
                any("days=7" in message for message in log.output),
                f"days not logged in error. Logs: {log.output}"
            )
    
    @patch.object(ApiClient, '_make_request')
    def test_error_handling_network_error(self, mock_request):
        """Test error handling for network errors."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Network unreachable")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(requests.exceptions.ConnectionError):
            client.fetch_error_metrics(app_id="123", days=30)
    
    @patch.object(ApiClient, '_make_request')
    def test_error_handling_graphql_error(self, mock_request):
        """Test error handling for GraphQL errors."""
        mock_request.side_effect = ValueError("GraphQL errors: Application not found")
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        with self.assertRaises(ValueError) as context:
            client.fetch_error_metrics(app_id="invalid-app", days=30)
        
        self.assertIn("GraphQL errors", str(context.exception))
    
    @patch.object(ApiClient, '_make_request')
    def test_time_window_calculation(self, mock_request):
        """Test that time window (since parameter) is calculated correctly for different days."""
        from datetime import datetime, timedelta
        
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {"error.rate": 1.0, "error.count": 5, "error.types": []}
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        
        # Test with days=14
        result = client.fetch_error_metrics(app_id="123", days=14)
        
        # Verify _make_request was called
        self.assertTrue(mock_request.called)
        
        # Get the query that was passed
        call_args = mock_request.call_args
        query = call_args[0][0] if call_args[0] else call_args[1].get('query')
        
        # Verify query contains NRQL with SINCE clause
        self.assertIn("SINCE", query)
        
        # Extract the since timestamp from query (it's embedded in NRQL string)
        import re
        since_match = re.search(r"SINCE '([^']+)'", query)
        self.assertIsNotNone(since_match, "SINCE timestamp not found in query")
        
        since_str = since_match.group(1)
        
        # Verify since is roughly 14 days ago (allowing some time variance for test execution)
        since_dt = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
        expected_since = datetime.utcnow() - timedelta(days=14)
        
        # Allow 1 minute variance
        delta = abs((since_dt.replace(tzinfo=None) - expected_since).total_seconds())
        self.assertLess(delta, 60, f"Since timestamp {since_str} is not within 1 minute of expected 14 days ago")
from modules.api_client import ApiClient


class TestInfrastructureMetrics(unittest.TestCase):
    """Test fetch_infrastructure_metrics method."""
    
    @patch.object(ApiClient, '_nrql_request')
    def test_fetch_infrastructure_metrics_success(self, mock_nrql):
        """Test successful infrastructure metrics fetch with SystemSample data."""
        # Three NRQL calls: host discovery, SystemSample, (no fallbacks needed)
        mock_nrql.side_effect = [
            # 1) host discovery
            [{"uniques.host": ["WEBHOST01"]}],
            # 2) SystemSample
            [{"cpu_pct": 28.5, "mem_pct": 32.8, "used_gb": 5.25, "total_gb": 16.0, "disk_pct": 0.7}],
        ]
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_infrastructure_metrics(app_id="9876543", days=30, app_name="test-app")
        
        infra = result["infrastructure"]
        self.assertAlmostEqual(infra["cpu_percent"], 28.5, places=1)
        self.assertAlmostEqual(infra["memory_percent"], 32.8, places=1)
        self.assertAlmostEqual(infra["memory_used_gb"], 5.25, places=2)
        self.assertAlmostEqual(infra["memory_total_gb"], 16.0, places=1)
        self.assertAlmostEqual(infra["disk_percent"], 0.7, places=1)
        self.assertEqual(infra["host_name"], "WEBHOST01")
        # Legacy keys for health calculator
        self.assertAlmostEqual(infra["cpu_usage"], 0.285, places=3)
        self.assertAlmostEqual(infra["memory_usage"], 0.328, places=3)
    
    @patch.object(ApiClient, '_nrql_request')
    def test_missing_data_uses_none(self, mock_nrql):
        """Test that missing metrics use None when no host or SystemSample found."""
        mock_nrql.side_effect = [
            # 1) host discovery — empty
            [{"uniques.host": []}],
            # 2) CPU fallback — empty
            [],
            # 3) Memory fallback — empty
            [],
        ]
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_infrastructure_metrics(app_id="123", days=7)
        
        infra = result["infrastructure"]
        self.assertIsNone(infra["cpu_usage"])
        self.assertIsNone(infra["memory_usage"])
        self.assertIsNone(infra["cpu_percent"])


class TestDatabaseMetrics(unittest.TestCase):
    """Test fetch_database_metrics method."""
    
    @patch.object(ApiClient, '_make_request')
    def test_fetch_database_metrics_success(self, mock_request):
        """Test successful database metrics fetch with valid data."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "query.time": 125.5,
                                    "slow.queries": 15,
                                    "db.calls": 450,
                                    "pool.usage": 80.0
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_database_metrics(app_id="9876543", days=30)
        
        db = result["database"]
        self.assertEqual(db["query_time"], 125.5)
        self.assertEqual(db["slow_queries"], 15)
        self.assertEqual(db["database_calls"], 450)
        self.assertAlmostEqual(db["connection_pool_usage"], 0.8, places=3)
    
    @patch.object(ApiClient, '_make_request')
    def test_string_to_numeric_conversion(self, mock_request):
        """Test that string values are converted to proper types."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "query.time": "125.5",
                                    "slow.queries": "15",
                                    "db.calls": " 450",
                                    "pool.usage": "80.0"
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_database_metrics(app_id="123", days=30)
        
        db = result["database"]
        self.assertIsInstance(db["query_time"], float)
        self.assertIsInstance(db["slow_queries"], int)
        self.assertIsInstance(db["database_calls"], int)
        self.assertIsInstance(db["connection_pool_usage"], float)


class TestTransactionMetrics(unittest.TestCase):
    """Test fetch_transaction_metrics method."""
    
    @patch.object(ApiClient, '_make_request')
    def test_fetch_transaction_metrics_success(self, mock_request):
        """Test successful transaction metrics fetch with valid data."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "transaction.time": 235.8,
                                    "external.calls": 50,
                                    "external.latency": 150.2,
                                    "api.endpoints": ["/api/users", "/api/orders", "/api/products"]
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_transaction_metrics(app_id="9876543", days=30)
        
        txn = result["transactions"]
        self.assertEqual(txn["transaction_time"], 235.8)
        self.assertEqual(txn["external_calls"], 50)
        self.assertEqual(txn["external_latency"], 150.2)
        self.assertIsInstance(txn["api_endpoints"], list)
        self.assertEqual( len(txn["api_endpoints"]), 3)
    
    @patch.object(ApiClient, '_make_request')
    def test_api_endpoints_comma_separated_string(self, mock_request):
        """Test that API endpoints can be parsed from comma-separated string."""
        mock_request.return_value = {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": [
                                {
                                    "transaction.time": 200.0,
                                    "external.calls": 10,
                                    "external.latency": 100.0,
                                    "api.endpoints": "/api/users, /api/orders"
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        client = ApiClient(api_key="test-key", account_id="123456")
        result = client.fetch_transaction_metrics(app_id="123", days=30)
        
        endpoints = result["transactions"]["api_endpoints"]
        self.assertIsInstance(endpoints, list)
        self.assertEqual(len(endpoints), 2)
        self.assertEqual(endpoints, ["/api/users", "/api/orders"])


class TestSlowDbTransactions(unittest.TestCase):
    """Test fetch_slow_db_transactions method."""

    def _make_client(self):
        return ApiClient(api_key="test-key", account_id="123456")

    def _nrql_response(self, results):
        return {
            "data": {
                "actor": {
                    "account": {
                        "nrql": {
                            "results": results
                        }
                    }
                }
            }
        }

    @patch.object(ApiClient, '_make_request')
    def test_fetch_slow_db_transactions_success(self, mock_request):
        """Returns sorted list of transactions with expected fields."""
        mock_request.return_value = self._nrql_response([
            {
                "name": "WebTransaction/Controller/orders#show",
                "transaction_type": "Web",
                "avg_db_ms": 850.0,
                "p95_db_ms": 1200.0,
                "avg_db_calls": 12.5,
                "call_count": 200,
                "avg_total_ms": 950.0,
            },
            {
                "name": "OtherTransaction/Background/workers/ProcessJob",
                "transaction_type": "Other",
                "avg_db_ms": 1500.0,
                "p95_db_ms": 2200.0,
                "avg_db_calls": 30.0,
                "call_count": 50,
                "avg_total_ms": 1600.0,
            },
        ])

        client = self._make_client()
        result = client.fetch_slow_db_transactions(app_id="999", days=1)

        self.assertIn("slow_db_transactions", result)
        rows = result["slow_db_transactions"]
        self.assertEqual(len(rows), 2)
        # Should be sorted descending by avg_db_ms
        self.assertGreater(rows[0]["avg_db_ms"], rows[1]["avg_db_ms"])
        # First row is the background transaction (highest avg_db_ms)
        self.assertAlmostEqual(rows[0]["avg_db_ms"], 1500.0)

    @patch.object(ApiClient, '_make_request')
    def test_fetch_slow_db_transactions_empty(self, mock_request):
        """Returns empty list when no transactions have databaseDuration > 0."""
        mock_request.return_value = self._nrql_response([])

        client = self._make_client()
        result = client.fetch_slow_db_transactions(app_id="999", days=1)

        self.assertEqual(result["slow_db_transactions"], [])

    def test_invalid_app_id_raises(self):
        """Empty app_id raises ValueError."""
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.fetch_slow_db_transactions(app_id="", days=1)

    def test_invalid_days_raises(self):
        """days value not in allowed list raises ValueError."""
        client = self._make_client()
        with self.assertRaises(ValueError):
            client.fetch_slow_db_transactions(app_id="999", days=99)


class TestSafeConversionEdgeCases(unittest.TestCase):
    """Test _safe_float and _safe_int with non-convertible values."""

    def setUp(self):
        self.client = ApiClient(api_key="k", account_id="1")

    def test_safe_float_invalid_string(self):
        self.assertIsNone(self.client._safe_float("abc"))

    def test_safe_int_invalid_string(self):
        self.assertIsNone(self.client._safe_int("abc"))

    def test_safe_float_none(self):
        self.assertIsNone(self.client._safe_float(None))

    def test_safe_int_none(self):
        self.assertIsNone(self.client._safe_int(None))


class TestNrqlRequestHelper(unittest.TestCase):
    """Test _nrql_request helper and _since_iso."""

    def setUp(self):
        self.client = ApiClient(api_key="k", account_id="1")

    @patch.object(ApiClient, '_make_request')
    def test_nrql_request_returns_results(self, mock_req):
        mock_req.return_value = {
            "data": {"actor": {"account": {"nrql": {"results": [{"count": 5}]}}}}
        }
        results = self.client._nrql_request("SELECT count(*) FROM Transaction", "test")
        self.assertEqual(results, [{"count": 5}])

    @patch.object(ApiClient, '_make_request')
    def test_nrql_request_empty_response(self, mock_req):
        mock_req.return_value = {"data": {}}
        results = self.client._nrql_request("SELECT 1", "test")
        self.assertEqual(results, [])

    def test_since_iso_format(self):
        result = self.client._since_iso(7)
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')


class TestFetchErrorDetails(unittest.TestCase):
    """Test fetch_error_details method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_error_details_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"error.class": "NullReferenceException", "count": 42, "message": "Object ref", "stack_trace": "at Foo.Bar()"}
        ])
        result = self._make_client().fetch_error_details("123", 1)
        self.assertIn("error_details", result)
        self.assertEqual(len(result["error_details"]), 1)
        self.assertEqual(result["error_details"][0]["error_class"], "NullReferenceException")
        self.assertEqual(result["error_details"][0]["count"], 42)

    @patch.object(ApiClient, '_make_request')
    def test_fetch_error_details_empty(self, mock_req):
        mock_req.return_value = self._nrql_response([])
        result = self._make_client().fetch_error_details("123", 1)
        self.assertEqual(result["error_details"], [])

    def test_fetch_error_details_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_error_details("", 1)

    def test_fetch_error_details_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_error_details("123", 5)

    @patch.object(ApiClient, '_make_request', side_effect=Exception("API fail"))
    def test_fetch_error_details_propagates_exception(self, mock_req):
        with self.assertRaises(Exception):
            self._make_client().fetch_error_details("123", 1)


class TestFetchSlowTransactions(unittest.TestCase):
    """Test fetch_slow_transactions method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_slow_transactions_sorted(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"name": "fast", "transaction_type": "Web", "avg_duration_ms": 100, "p95_ms": 200, "call_count": 10, "db_time_ms": 5, "db_call_count": 2, "external_time_ms": 10, "external_call_count": 1},
            {"name": "slow", "transaction_type": "Web", "avg_duration_ms": 500, "p95_ms": 900, "call_count": 5, "db_time_ms": 200, "db_call_count": 10, "external_time_ms": 50, "external_call_count": 3},
        ])
        result = self._make_client().fetch_slow_transactions("123", 1)
        txns = result["slow_transactions"]
        self.assertEqual(len(txns), 2)
        self.assertGreater(txns[0]["avg_duration_ms"], txns[1]["avg_duration_ms"])

    def test_fetch_slow_transactions_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_slow_transactions("", 1)

    def test_fetch_slow_transactions_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_slow_transactions("123", 2)


class TestFetchDatabaseDetails(unittest.TestCase):
    """Test fetch_database_details method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_database_details_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"facet": ["MSSQL", "SELECT", "Users"], "avg_duration_ms": 50, "p95_ms": 120, "call_count": 1000, "total_time_ms": 50000}
        ])
        result = self._make_client().fetch_database_details("123", 1)
        self.assertEqual(len(result["database_details"]), 1)
        self.assertEqual(result["database_details"][0]["datastore_type"], "MSSQL")
        self.assertEqual(result["database_details"][0]["operation"], "SELECT")

    @patch.object(ApiClient, '_make_request')
    def test_fetch_database_details_empty_facet(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"facet": [], "avg_duration_ms": 10, "p95_ms": 20, "call_count": 5, "total_time_ms": 50}
        ])
        result = self._make_client().fetch_database_details("123", 1)
        self.assertEqual(result["database_details"][0]["datastore_type"], "Unknown")

    def test_fetch_database_details_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_database_details("  ", 1)


class TestFetchExternalServices(unittest.TestCase):
    """Test fetch_external_services method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_external_services_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"host": "api.example.com", "avg_duration_ms": 120.5, "call_count": 500, "p95_ms": 350.0}
        ])
        result = self._make_client().fetch_external_services("123", 1)
        self.assertEqual(len(result["external_services"]), 1)
        self.assertEqual(result["external_services"][0]["host"], "api.example.com")

    def test_fetch_external_services_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_external_services("", 1)

    def test_fetch_external_services_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_external_services("123", 99)


class TestFetchApplicationLogs(unittest.TestCase):
    """Test fetch_application_logs method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_application_logs_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"message": "NullRef at line 42", "level": "ERROR", "timestamp": "2025-01-01T00:00:00",
             "error.class": "NullRef", "error.message": "Object ref", "error.stack": "stack trace"}
        ])
        result = self._make_client().fetch_application_logs("123", 1)
        self.assertEqual(len(result["application_logs"]), 1)
        self.assertEqual(result["application_logs"][0]["level"], "ERROR")

    @patch.object(ApiClient, '_make_request')
    def test_fetch_application_logs_strips_base64_blobs(self, mock_req):
        msg = 'Processing label: {"labelImage":"' + 'A' * 500 + '"}'
        mock_req.return_value = self._nrql_response([
            {"message": msg, "level": "INFO", "timestamp": "t"}
        ])
        result = self._make_client().fetch_application_logs("123", 1)
        self.assertIn("[base64 removed]", result["application_logs"][0]["message"])

    def test_fetch_application_logs_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_application_logs("", 1)

    @patch.object(ApiClient, '_make_request', side_effect=Exception("fail"))
    def test_fetch_application_logs_propagates_exception(self, mock_req):
        with self.assertRaises(Exception):
            self._make_client().fetch_application_logs("123", 1)


class TestFetchLogVolume(unittest.TestCase):
    """Test fetch_log_volume method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_log_volume_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"level": "ERROR", "count": 100},
            {"level": "INFO", "count": 5000}
        ])
        result = self._make_client().fetch_log_volume("123", 1)
        self.assertEqual(len(result["log_volume"]), 2)

    def test_fetch_log_volume_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_log_volume("", 1)

    def test_fetch_log_volume_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_log_volume("123", 100)


class TestFetchAlerts(unittest.TestCase):
    """Test fetch_alerts method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_alerts_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"title": "High CPU", "priority": "CRITICAL", "state": "closed",
             "conditionName": "cpu > 80", "policyName": "default",
             "openTime": 1000, "closeTime": 2000, "durationSeconds": 1000}
        ])
        result = self._make_client().fetch_alerts("123", 1)
        self.assertEqual(len(result["alerts"]), 1)
        self.assertEqual(result["alerts"][0]["priority"], "CRITICAL")

    def test_fetch_alerts_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_alerts("", 1)

    @patch.object(ApiClient, '_make_request', side_effect=Exception("fail"))
    def test_fetch_alerts_propagates_exception(self, mock_req):
        with self.assertRaises(Exception):
            self._make_client().fetch_alerts("123", 1)


class TestFetchHourlyTrends(unittest.TestCase):
    """Test fetch_hourly_trends method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_hourly_trends_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"beginTimeSeconds": 1710000000, "endTimeSeconds": 1710003600,
             "avg_response_ms": 250.5, "throughput_rpm": 100.0, "error_rate": 0.02}
        ])
        result = self._make_client().fetch_hourly_trends("123", 1)
        self.assertEqual(len(result["hourly_trends"]), 1)
        self.assertAlmostEqual(result["hourly_trends"][0]["avg_response_ms"], 250.5)

    def test_fetch_hourly_trends_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_hourly_trends("", 1)

    def test_fetch_hourly_trends_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_hourly_trends("123", 60)


class TestFetchDeployments(unittest.TestCase):
    """Test fetch_deployments method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_deployments_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"timestamp": 1710000000, "revision": "abc123", "description": "hotfix",
             "user": "dev", "changelog": "fix bug"}
        ])
        result = self._make_client().fetch_deployments("123", 1)
        self.assertEqual(len(result["deployments"]), 1)
        self.assertEqual(result["deployments"][0]["revision"], "abc123")

    @patch.object(ApiClient, '_make_request')
    def test_fetch_deployments_with_app_name(self, mock_req):
        mock_req.return_value = self._nrql_response([])
        result = self._make_client().fetch_deployments("123", 1, app_name="MyApp")
        self.assertEqual(result["deployments"], [])

    def test_fetch_deployments_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_deployments("", 1)


class TestFetchBaselines(unittest.TestCase):
    """Test fetch_baselines method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    def _nrql_response(self, results):
        return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}

    @patch.object(ApiClient, '_make_request')
    def test_fetch_baselines_success(self, mock_req):
        mock_req.return_value = self._nrql_response([
            {"baseline_response_ms": 300.0, "baseline_throughput_rpm": 500.0,
             "baseline_error_rate": 0.01, "baseline_total_requests": 100000}
        ])
        result = self._make_client().fetch_baselines("123")
        b = result["baselines"]
        self.assertAlmostEqual(b["response_time_7d_avg_ms"], 300.0)
        self.assertAlmostEqual(b["throughput_7d_avg_rpm"], 500.0)

    @patch.object(ApiClient, '_make_request')
    def test_fetch_baselines_no_data(self, mock_req):
        mock_req.return_value = self._nrql_response([])
        result = self._make_client().fetch_baselines("123")
        b = result["baselines"]
        self.assertIsNone(b["response_time_7d_avg_ms"])
        self.assertIsNone(b["throughput_7d_avg_rpm"])

    def test_fetch_baselines_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().fetch_baselines("")


class TestCollectAllMetrics(unittest.TestCase):
    """Test collect_all_metrics orchestrator method."""

    def _make_client(self):
        return ApiClient(api_key="k", account_id="1")

    @patch.object(ApiClient, 'save_to_cache', return_value="data/test.json")
    @patch.object(ApiClient, 'load_from_cache', return_value=None)
    @patch.object(ApiClient, 'fetch_deployments', return_value={"deployments": []})
    @patch.object(ApiClient, 'fetch_baselines', return_value={"baselines": {}})
    @patch.object(ApiClient, 'fetch_hourly_trends', return_value={"hourly_trends": []})
    @patch.object(ApiClient, 'fetch_alerts', return_value={"alerts": []})
    @patch.object(ApiClient, 'fetch_log_volume', return_value={"log_volume": []})
    @patch.object(ApiClient, 'fetch_application_logs', return_value={"application_logs": []})
    @patch.object(ApiClient, 'fetch_external_services', return_value={"external_services": []})
    @patch.object(ApiClient, 'fetch_database_details', return_value={"database_details": []})
    @patch.object(ApiClient, 'fetch_slow_transactions', return_value={"slow_transactions": []})
    @patch.object(ApiClient, 'fetch_error_details', return_value={"error_details": []})
    @patch.object(ApiClient, 'fetch_transaction_metrics', return_value={"transactions": {}})
    @patch.object(ApiClient, 'fetch_database_metrics', return_value={"database": {}})
    @patch.object(ApiClient, 'fetch_infrastructure_metrics', return_value={"infrastructure": {}})
    @patch.object(ApiClient, 'fetch_error_metrics', return_value={"errors": {}})
    @patch.object(ApiClient, 'fetch_performance_metrics', return_value={"performance": {}})
    def test_collect_all_metrics_calls_all_fetches(self, *mocks):
        result = self._make_client().collect_all_metrics("123", 1, app_name="app")
        self.assertIn("performance", result)
        self.assertIn("errors", result)
        self.assertIn("infrastructure", result)
        self.assertIn("database", result)
        self.assertIn("transactions", result)
        self.assertIn("error_details", result)
        self.assertIn("slow_transactions", result)
        self.assertIn("database_details", result)
        self.assertIn("external_services", result)
        self.assertIn("application_logs", result)
        self.assertIn("log_volume", result)
        self.assertIn("alerts", result)
        self.assertIn("hourly_trends", result)
        self.assertIn("baselines", result)
        self.assertIn("deployments", result)

    @patch.object(ApiClient, 'load_from_cache')
    def test_collect_all_metrics_uses_cache(self, mock_cache):
        cached = {"app_id": "123", "cached": True}
        mock_cache.return_value = cached
        result = self._make_client().collect_all_metrics("123", 1)
        self.assertEqual(result, cached)

    def test_collect_all_metrics_invalid_app_id(self):
        with self.assertRaises(ValueError):
            self._make_client().collect_all_metrics("", 1)

    def test_collect_all_metrics_invalid_days(self):
        with self.assertRaises(ValueError):
            self._make_client().collect_all_metrics("123", 99)


class TestCacheMethods(unittest.TestCase):
    """Test save_to_cache, load_from_cache, cleanup_old_cache."""

    def setUp(self):
        import tempfile
        self.client = ApiClient(api_key="k", account_id="1")
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch('modules.api_client.os.makedirs')
    @patch('builtins.open', unittest.mock.mock_open())
    def test_save_to_cache_returns_path(self, mock_makedirs):
        import json
        path = self.client.save_to_cache({"test": 1}, "myapp")
        self.assertIn("myapp", path)
        self.assertTrue(path.endswith(".json"))

    @patch('modules.api_client.glob.glob', return_value=[])
    def test_load_from_cache_no_files(self, mock_glob):
        result = self.client.load_from_cache("myapp")
        self.assertIsNone(result)

    @patch('modules.api_client.os.path.exists', return_value=False)
    def test_load_from_cache_no_data_dir(self, mock_exists):
        result = self.client.load_from_cache("myapp")
        self.assertIsNone(result)

    @patch('modules.api_client.os.path.exists', return_value=False)
    def test_cleanup_old_cache_no_dir(self, mock_exists):
        result = self.client.cleanup_old_cache()
        self.assertEqual(result, 0)

    @patch('modules.api_client.os.remove')
    @patch('modules.api_client.os.path.getmtime', return_value=0)
    @patch('modules.api_client.glob.glob', return_value=["data/old.json"])
    @patch('modules.api_client.os.path.exists', return_value=True)
    def test_cleanup_old_cache_removes_old_files(self, mock_exists, mock_glob, mock_mtime, mock_remove):
        result = self.client.cleanup_old_cache(retention_days=1)
        self.assertEqual(result, 1)
        mock_remove.assert_called_once()
