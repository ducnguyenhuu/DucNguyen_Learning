"""
Tests for main.py CLI orchestrator.

Tests cover argument parsing, config validation mode, offline analysis
from cached files, and the full orchestration flow with mocked modules.
"""

import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from main import parse_args, _flatten_metrics, _safe_fetch, main


class TestParseArgs(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_defaults(self):
        args = parse_args([])
        self.assertEqual(args.days, 1)
        self.assertEqual(args.profile, "dev")
        self.assertIsNone(args.from_file)
        self.assertFalse(args.no_cache)
        self.assertFalse(args.validate_config)
        self.assertFalse(args.verbose)
        self.assertEqual(args.output_dir, "reports")

    def test_days_flag(self):
        args = parse_args(["--days", "7"])
        self.assertEqual(args.days, 7)

    def test_profile_flag(self):
        args = parse_args(["--profile", "prod"])
        self.assertEqual(args.profile, "prod")

    def test_from_file_flag(self):
        args = parse_args(["--from-file", "data/test.json"])
        self.assertEqual(args.from_file, "data/test.json")

    def test_no_cache_flag(self):
        args = parse_args(["--no-cache"])
        self.assertTrue(args.no_cache)

    def test_validate_config_flag(self):
        args = parse_args(["--validate-config"])
        self.assertTrue(args.validate_config)

    def test_verbose_flag(self):
        args = parse_args(["-v"])
        self.assertTrue(args.verbose)

    def test_output_dir_flag(self):
        args = parse_args(["--output-dir", "/tmp/reports"])
        self.assertEqual(args.output_dir, "/tmp/reports")

    def test_combined_flags(self):
        args = parse_args(["--days", "14", "--profile", "prod", "--no-cache", "-v"])
        self.assertEqual(args.days, 14)
        self.assertEqual(args.profile, "prod")
        self.assertTrue(args.no_cache)
        self.assertTrue(args.verbose)


class TestFlattenMetrics(unittest.TestCase):
    """Test _flatten_metrics helper."""

    def test_flatten_simple(self):
        data = {
            "performance": {"response_time": 300, "throughput": 500},
            "errors": {"error_rate": 0.01},
        }
        flat = _flatten_metrics(data)
        self.assertEqual(flat["response_time"], 300)
        self.assertEqual(flat["error_rate"], 0.01)

    def test_flatten_nested(self):
        data = {
            "performance": {"performance": {"response_time": 200}},
            "errors": {"errors": {"error_rate": 0.02}},
        }
        flat = _flatten_metrics(data)
        self.assertEqual(flat["response_time"], 200)
        self.assertEqual(flat["error_rate"], 0.02)

    def test_flatten_empty(self):
        flat = _flatten_metrics({})
        self.assertEqual(flat, {})


class TestSafeFetch(unittest.TestCase):
    """Test _safe_fetch helper."""

    def test_success(self):
        result = _safe_fetch("test", lambda: {"data": 1}, {"data": 0})
        self.assertEqual(result, {"data": 1})

    def test_failure_returns_default(self):
        def fail():
            raise RuntimeError("boom")
        result = _safe_fetch("test", fail, {"data": 0})
        self.assertEqual(result, {"data": 0})


class TestValidateConfigMode(unittest.TestCase):
    """Test --validate-config exits cleanly."""

    @patch("main.load_config")
    def test_validate_config_exits_zero(self, mock_config):
        mock_config.return_value = {
            "api_key": "k", "account_id": "1", "app_ids": ["123"], "days": 1
        }
        with self.assertRaises(SystemExit) as cm:
            main(["--validate-config"])
        self.assertEqual(cm.exception.code, 0)


class TestFromFileMode(unittest.TestCase):
    """Test --from-file offline analysis mode."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.data_file = os.path.join(self.tmpdir, "test-data.json")
        sample = {
            "app_id": "123", "app_name": "test-app", "days": 1,
            "performance": {"response_time": 300, "throughput": 500, "apdex_score": 0.9},
            "errors": {"error_rate": 0.01, "error_count": 5},
            "infrastructure": {"cpu_usage": 0.4, "memory_usage": 0.6},
            "database": {"query_time": 50, "slow_queries": 0},
            "transactions": {"transaction_time": 200, "external_calls": 10, "external_latency": 80},
        }
        with open(self.data_file, "w") as f:
            json.dump(sample, f)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("main.load_config")
    @patch("main.ReportGenerator")
    def test_from_file_generates_report(self, mock_rg_cls, mock_config):
        mock_config.return_value = {
            "api_key": "k", "account_id": "1", "app_ids": ["123"], "days": 1
        }
        mock_rg = MagicMock()
        mock_rg.generate_report.return_value = "# Report"
        mock_rg.save_report.return_value = os.path.join(self.tmpdir, "report.md")
        mock_rg_cls.return_value = mock_rg

        out_dir = os.path.join(self.tmpdir, "reports")
        score = main(["--from-file", self.data_file, "--output-dir", out_dir])
        self.assertIsInstance(score, int)
        self.assertGreater(score, 0)
        mock_rg.generate_report.assert_called_once()


class TestFullWorkflowMocked(unittest.TestCase):
    """Test full workflow with all API calls mocked."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    @patch("main.ApiClient")
    @patch("main.load_config")
    @patch("main.ReportGenerator")
    def test_full_workflow(self, mock_rg_cls, mock_config, mock_api_cls):
        mock_config.return_value = {
            "api_key": "k", "account_id": "1", "app_ids": ["123"],
            "app_name": "test", "days": 1, "timeout": 30, "max_retries": 2,
        }

        mock_api = MagicMock()
        mock_api.fetch_performance_metrics.return_value = {"performance": {"response_time": 300, "throughput": 500, "apdex_score": 0.85}}
        mock_api.fetch_error_metrics.return_value = {"errors": {"error_rate": 0.01, "error_count": 5}}
        mock_api.fetch_infrastructure_metrics.return_value = {"infrastructure": {"cpu_usage": 0.4}}
        mock_api.fetch_database_metrics.return_value = {"database": {"query_time": 50}}
        mock_api.fetch_transaction_metrics.return_value = {"transactions": {"transaction_time": 200}}
        mock_api.fetch_error_details.return_value = {"error_details": []}
        mock_api.fetch_slow_transactions.return_value = {"slow_transactions": []}
        mock_api.fetch_database_details.return_value = {"database_details": []}
        mock_api.fetch_slow_db_transactions.return_value = {"slow_db_transactions": []}
        mock_api.fetch_external_services.return_value = {"external_services": []}
        mock_api.fetch_application_logs.return_value = {"application_logs": []}
        mock_api.fetch_log_volume.return_value = {"log_volume": []}
        mock_api.fetch_alerts.return_value = {"alerts": []}
        mock_api.fetch_hourly_trends.return_value = {"hourly_trends": []}
        mock_api.fetch_baselines.return_value = {"baselines": {}}
        mock_api.fetch_deployments.return_value = {"deployments": []}
        mock_api_cls.return_value = mock_api

        mock_rg = MagicMock()
        mock_rg.generate_report.return_value = "# Report"
        report_path = os.path.join(self.tmpdir, "report.md")
        mock_rg.save_report.return_value = report_path
        mock_rg_cls.return_value = mock_rg

        score = main(["--no-cache", "--output-dir", self.tmpdir])
        self.assertIsInstance(score, int)
        mock_api.fetch_performance_metrics.assert_called_once()
        mock_rg.generate_report.assert_called_once()

    @patch("main.load_config", side_effect=FileNotFoundError("not found"))
    def test_config_error_exits(self, mock_config):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
