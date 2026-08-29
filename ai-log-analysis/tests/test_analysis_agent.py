"""
Tests for Story 5.1: Create @analysis-agent Instruction File with Health Scoring Logic

Validates that the analysis agent instruction file exists, contains all required
sections, and matches the health scoring methodology from health_calculator.py.
"""
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestAnalysisAgentFileExists:
    """Verify agent files exist in the correct locations."""

    def test_analysis_agent_md_exists(self):
        """AC1: agents/analysis-agent.md exists."""
        assert (PROJECT_ROOT / "agents" / "analysis-agent.md").is_file()

    def test_vscode_agent_file_exists(self):
        """AC7: .github/agents/analysis-agent.agent.md exists for VS Code Copilot."""
        assert (PROJECT_ROOT / ".github" / "agents" / "analysis-agent.agent.md").is_file()


class TestAnalysisAgentRoleDefinition:
    """AC1: File includes clear role definition."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_has_role_section(self):
        assert "## Role" in self.content

    def test_role_mentions_sre(self):
        assert "SRE" in self.content or "Site Reliability" in self.content

    def test_role_mentions_health_assessment(self):
        assert "health assessment" in self.content.lower()


class TestAnalysisAgentDataInstructions:
    """AC2: Instructions for analyzing JSON data from data/ directory."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_references_data_directory(self):
        assert "data/" in self.content

    def test_references_json_structure(self):
        assert "JSON" in self.content

    def test_documents_key_data_paths(self):
        """Agent must document the nested JSON paths for key metrics."""
        for path in [
            "performance.performance.response_time",
            "errors.errors.error_rate",
            "infrastructure.infrastructure.cpu_usage",
            "database.database.query_time",
            "transactions.transactions.transaction_time",
        ]:
            assert path in self.content, f"Missing data path: {path}"

    def test_documents_enrichment_data(self):
        """Agent must reference enrichment data sections."""
        for section in ["error_details", "slow_transactions", "database_details", "hourly_trends", "baselines"]:
            assert section in self.content, f"Missing enrichment section: {section}"


class TestAnalysisAgentHealthScoring:
    """AC3: Health scoring methodology (5 categories, weighted 25/25/20/15/15)."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_five_categories_defined(self):
        for category in ["Performance", "Errors", "Infrastructure", "Database", "API"]:
            assert category in self.content, f"Missing category: {category}"

    def test_weights_defined(self):
        assert "25%" in self.content
        assert "20%" in self.content
        assert "15%" in self.content

    def test_scoring_range(self):
        """Score must be on 0-100 scale."""
        assert "0-100" in self.content or "0–100" in self.content


class TestAnalysisAgentSeverity:
    """AC4: Severity categorization rules."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_all_status_levels(self):
        for status in ["Excellent", "Good", "Warning", "Critical"]:
            assert status in self.content, f"Missing status level: {status}"

    def test_score_bands(self):
        """Must define score ranges for each status."""
        assert "90" in self.content  # Excellent threshold
        assert "70" in self.content  # Good threshold
        assert "50" in self.content  # Warning threshold

    def test_emoji_indicators(self):
        for emoji in ["🟢", "🟡", "🟠", "🔴"]:
            assert emoji in self.content, f"Missing emoji indicator: {emoji}"


class TestAnalysisAgentPatternDetection:
    """AC5: Pattern detection rules for specific issue types."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_error_rate_thresholds(self):
        assert "5%" in self.content  # Error rate warning
        assert "error_rate" in self.content

    def test_response_time_thresholds(self):
        assert "500ms" in self.content
        assert "1000ms" in self.content

    def test_infrastructure_thresholds(self):
        assert "85%" in self.content  # CPU critical
        assert "90%" in self.content  # Memory critical

    def test_database_thresholds(self):
        assert "100ms" in self.content  # Query time warning
        assert "200ms" in self.content  # Query time critical

    def test_n_plus_1_pattern(self):
        assert "N+1" in self.content or "N\\+1" in self.content

    def test_connection_pool_detection(self):
        assert "connection pool" in self.content.lower() or "connection_pool" in self.content

    def test_external_latency_threshold(self):
        assert "external" in self.content.lower()
        assert "latency" in self.content.lower()


class TestAnalysisAgentOutputFormat:
    """AC6: Output format specification."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_output_has_executive_summary(self):
        assert "Executive Summary" in self.content

    def test_output_has_score_breakdown(self):
        assert "Health Score Breakdown" in self.content or "Score Breakdown" in self.content

    def test_output_has_critical_issues_section(self):
        assert "Critical Issues" in self.content

    def test_output_has_warnings_section(self):
        assert "Warning" in self.content

    def test_output_has_trend_analysis(self):
        assert "Trend" in self.content

    def test_output_has_slow_endpoints(self):
        assert "Slow Endpoint" in self.content or "slow_transactions" in self.content

    def test_output_has_recommended_next_steps(self):
        assert "Next Steps" in self.content or "recommend-agent" in self.content


class TestAnalysisAgentQualityGuidelines:
    """Agent instructions include quality guidelines for specificity and evidence."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")

    def test_has_quality_section(self):
        assert "Quality" in self.content or "Guidelines" in self.content

    def test_be_specific_guidance(self):
        assert "Specific" in self.content or "specific" in self.content

    def test_show_evidence_guidance(self):
        assert "evidence" in self.content.lower() or "Evidence" in self.content


class TestAnalysisAgentThresholdConsistency:
    """Verify agent thresholds match health_calculator.py."""

    @pytest.fixture(autouse=True)
    def load_files(self):
        self.agent = (PROJECT_ROOT / "agents" / "analysis-agent.md").read_text(encoding="utf-8")
        # Import the actual thresholds from health_calculator
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "health_calculator",
            PROJECT_ROOT / "modules" / "health_calculator.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.calc = mod.HealthCalculator()

    def test_response_time_thresholds_match(self):
        """Agent's response_time bands must match health_calculator."""
        # health_calculator: (200, 100), (500, 70), (1000, 40)
        assert "< 200ms" in self.agent or "200ms" in self.agent
        assert "500ms" in self.agent
        assert "1000ms" in self.agent

    def test_error_rate_thresholds_match(self):
        """Agent's error_rate bands must match health_calculator."""
        # health_calculator: (0.01, 100) = <1%, (0.03, 70) = 1-3%, (0.05, 40) = 3-5%
        assert "1%" in self.agent
        assert "3%" in self.agent
        assert "5%" in self.agent

    def test_cpu_thresholds_match(self):
        """Agent's cpu_usage bands must match health_calculator."""
        # health_calculator: (0.60, 100), (0.75, 70), (0.85, 40)
        assert "60%" in self.agent
        assert "75%" in self.agent
        assert "85%" in self.agent

    def test_category_weights_match(self):
        """Agent's category weights must match health_calculator CATEGORY_WEIGHTS."""
        weights = self.calc.CATEGORY_WEIGHTS
        assert weights["performance"] == 0.25
        assert weights["errors"] == 0.25
        assert weights["infrastructure"] == 0.20
        assert weights["database"] == 0.15
        assert weights["api"] == 0.15
        # And agent doc includes them
        assert "25%" in self.agent
        assert "20%" in self.agent
        assert "15%" in self.agent


class TestVSCodeAgentFile:
    """Validate the VS Code .agent.md file format."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / ".github" / "agents" / "analysis-agent.agent.md").read_text(encoding="utf-8")

    def test_has_yaml_frontmatter(self):
        assert self.content.startswith("---")
        assert self.content.count("---") >= 2

    def test_has_description(self):
        assert "description:" in self.content

    def test_references_main_agent_file(self):
        assert "agents/analysis-agent.md" in self.content

    def test_has_tools(self):
        assert "tools:" in self.content
