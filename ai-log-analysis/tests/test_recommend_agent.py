"""
Tests for Story 5.2: Create @recommend-agent Instruction File with Code-Specific Fixes

Validates that the recommend agent instruction file exists, contains all required
sections, and covers the complete recommendation methodology.
"""
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestRecommendAgentFileExists:
    """Verify agent files exist in the correct locations."""

    def test_recommend_agent_md_exists(self):
        """AC1: agents/recommend-agent.md exists."""
        assert (PROJECT_ROOT / "agents" / "recommend-agent.md").is_file()

    def test_vscode_agent_file_exists(self):
        """AC7: .github/agents/recommend-agent.agent.md exists for VS Code Copilot."""
        assert (PROJECT_ROOT / ".github" / "agents" / "recommend-agent.agent.md").is_file()


class TestRecommendAgentRoleDefinition:
    """AC1: File includes clear role definition."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_has_role_section(self):
        assert "## Role" in self.content

    def test_role_mentions_software_engineer(self):
        assert "software engineer" in self.content.lower()

    def test_role_mentions_root_cause(self):
        assert "root cause" in self.content.lower()

    def test_role_mentions_actionable(self):
        assert "actionable" in self.content.lower()


class TestRecommendAgentInputInstructions:
    """AC2: Instructions for reading assessment files from reports/."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_references_reports_directory(self):
        assert "reports/" in self.content

    def test_references_assessment_files(self):
        assert "assessment" in self.content.lower()

    def test_references_workspace_code(self):
        assert "workspace" in self.content.lower()

    def test_references_critical_issues(self):
        assert "Critical Issues" in self.content

    def test_references_warnings(self):
        assert "Warning" in self.content

    def test_references_codebase_access(self):
        """Agent should reference workspace code access."""
        assert "workspace" in self.content.lower() or "codebase" in self.content.lower()

    def test_references_analysis_agent(self):
        """Agent should reference @analysis-agent for generating assessments."""
        assert "analysis-agent" in self.content


class TestRecommendAgentRootCauseAnalysis:
    """AC3: Root cause analysis methodology."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_has_root_cause_section(self):
        assert "Root Cause" in self.content

    def test_find_affected_code(self):
        assert "Find Affected Code" in self.content or "find affected code" in self.content.lower()

    def test_analyze_problem(self):
        assert "Analyze the Problem" in self.content or "Analyze" in self.content

    def test_design_solution(self):
        assert "Design Solution" in self.content or "design solution" in self.content.lower()

    def test_common_patterns_documented(self):
        """Agent must document common root cause patterns."""
        patterns = ["N+1", "connection pool", "caching", "error handling"]
        found = sum(1 for p in patterns if p.lower() in self.content.lower())
        assert found >= 3, f"Only {found}/4 common patterns documented"

    def test_stack_trace_usage(self):
        assert "stack trace" in self.content.lower()


class TestRecommendAgentOutputFormat:
    """AC4: Output format with file paths, code, impact estimates."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_output_has_summary(self):
        assert "## Summary" in self.content or "Summary" in self.content

    def test_output_has_critical_section(self):
        assert "Critical Issues" in self.content or "Immediate Action" in self.content

    def test_output_has_warnings_section(self):
        assert "Warning" in self.content and "Improvement" in self.content

    def test_output_has_current_code_block(self):
        assert "Current Code" in self.content

    def test_output_has_recommended_fix_block(self):
        assert "Recommended Fix" in self.content

    def test_output_has_file_path_format(self):
        """Output template must show file:line format."""
        assert "path/file.ext" in self.content or "file.ext" in self.content

    def test_output_has_explanation(self):
        assert "Explanation" in self.content

    def test_output_has_impact_estimate(self):
        assert "Impact Estimate" in self.content or "Impact" in self.content

    def test_output_has_effort_estimate(self):
        assert "Effort" in self.content

    def test_output_has_risk_assessment(self):
        assert "Risk" in self.content

    def test_output_has_testing_strategy(self):
        assert "Testing" in self.content

    def test_output_has_rollback(self):
        assert "Rollback" in self.content

    def test_output_has_dependencies(self):
        assert "Dependencies" in self.content


class TestRecommendAgentImplementationPlan:
    """AC5: Implementation plan with priority ordering."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_has_implementation_plan(self):
        assert "Implementation Plan" in self.content

    def test_has_recommended_order(self):
        assert "Recommended Order" in self.content or "Priority" in self.content

    def test_has_success_metrics(self):
        assert "Success Metrics" in self.content

    def test_has_verification_steps(self):
        assert "Verification" in self.content

    def test_references_pytest(self):
        """Verification should include running tests."""
        assert "pytest" in self.content

    def test_references_demo_or_crawler(self):
        """Verification should include re-running data collection."""
        assert "demo.py" in self.content or "crawler.py" in self.content


class TestRecommendAgentQualityGuidelines:
    """AC6: Quality guidelines for recommendations."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_has_quality_section(self):
        assert "Quality" in self.content

    def test_must_include_section(self):
        assert "Must Include" in self.content

    def test_must_avoid_section(self):
        assert "Must Avoid" in self.content

    def test_no_generic_advice(self):
        assert "Generic advice" in self.content or "generic advice" in self.content.lower()

    def test_no_pseudo_code(self):
        assert "Pseudo-code" in self.content or "pseudo-code" in self.content.lower() or "placeholders" in self.content.lower()

    def test_exact_file_paths_required(self):
        assert "file path" in self.content.lower() or "line number" in self.content.lower()

    def test_complete_runnable_code(self):
        assert "runnable" in self.content.lower() or "complete" in self.content.lower()

    def test_pep8_reference(self):
        """Recommended code should follow PEP 8."""
        assert "PEP 8" in self.content or "pep 8" in self.content.lower()


class TestRecommendAgentFileSaving:
    """Verify agent saves recommendations to a file."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_save_to_file_instruction(self):
        assert "Save" in self.content and "File" in self.content

    def test_output_directory_defined(self):
        assert "reports/" in self.content

    def test_file_naming_convention(self):
        assert "recommendations-" in self.content

    def test_file_naming_has_app_name(self):
        assert "app_name" in self.content

    def test_file_naming_has_timestamp(self):
        assert "YYYY-MM-DD-HHMMSS" in self.content


class TestRecommendAgentAssessmentReference:
    """Verify agent documents what to extract from assessments."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / "agents" / "recommend-agent.md").read_text(encoding="utf-8")

    def test_references_executive_summary(self):
        assert "Executive Summary" in self.content

    def test_references_health_score_breakdown(self):
        assert "Health Score Breakdown" in self.content or "Score Breakdown" in self.content

    def test_references_slow_endpoints(self):
        assert "Slow Endpoint" in self.content or "slow endpoint" in self.content.lower()

    def test_references_database_deep_dive(self):
        assert "Database Deep Dive" in self.content or "database" in self.content.lower()

    def test_references_trend_analysis(self):
        assert "Trend" in self.content


class TestVSCodeRecommendAgentFile:
    """Validate the VS Code .agent.md file format."""

    @pytest.fixture(autouse=True)
    def load_agent_file(self):
        self.content = (PROJECT_ROOT / ".github" / "agents" / "recommend-agent.agent.md").read_text(encoding="utf-8")

    def test_has_yaml_frontmatter(self):
        assert self.content.startswith("---")
        assert self.content.count("---") >= 2

    def test_has_description(self):
        assert "description:" in self.content

    def test_references_main_agent_file(self):
        assert "agents/recommend-agent.md" in self.content

    def test_has_tools(self):
        assert "tools:" in self.content

    def test_mentions_assessment(self):
        assert "assessment" in self.content.lower()

    def test_mentions_recommendations(self):
        assert "recommendation" in self.content.lower()
