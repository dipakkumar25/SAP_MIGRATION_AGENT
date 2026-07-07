"""
Unit tests for all agent functions.
"""
from __future__ import annotations

import uuid
import pytest
from datetime import datetime

from app.agents import (
    run_atc_assessment,
    run_custom_code_discovery,
    run_dashboard_generation,
    run_dependency_analysis,
    run_landscape_discovery,
    run_recommendation_generation,
    run_risk_assessment,
    run_runbook_generation,
    run_simplification_analysis,
)
from app.models.schemas import AgentState, MigrationStatus, ObjectType, RiskLevel, SAPSystem


@pytest.fixture
def base_state() -> AgentState:
    """Fresh state with mock SAP system."""
    return AgentState(
        assessment_id=str(uuid.uuid4()),
        sap_system=SAPSystem(sid="ECC", host="localhost", client="100"),
        status=MigrationStatus.NOT_STARTED,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agent 1: Landscape Discovery
# ─────────────────────────────────────────────────────────────────────────────

class TestLandscapeDiscovery:
    def test_returns_landscape(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_landscape_discovery(base_state)
        assert result.landscape is not None

    def test_landscape_fields(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_landscape_discovery(base_state)
        lnd = result.landscape
        assert lnd.system_id == "ECC"
        assert "sapeccprd" in lnd.hostname
        assert lnd.sap_version != ""
        assert len(lnd.installed_components) > 0
        assert len(lnd.active_clients) > 0
        assert len(lnd.rfc_destinations) > 0

    def test_step_recorded(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_landscape_discovery(base_state)
        assert "landscape_discovery" in result.steps_completed
        assert result.current_step == "custom_code_discovery"


# ─────────────────────────────────────────────────────────────────────────────
# Agent 2: Custom Code Discovery
# ─────────────────────────────────────────────────────────────────────────────

class TestCustomCodeDiscovery:
    def test_returns_inventory(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_custom_code_discovery(base_state)
        assert result.custom_code is not None

    def test_object_counts(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_custom_code_discovery(base_state)
        cc = result.custom_code
        assert len(cc.z_programs) == 50
        assert len(cc.z_function_modules) == 30
        assert len(cc.z_classes) == 20
        assert len(cc.custom_tables) == 10
        assert cc.total_objects > 100

    def test_object_types(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_custom_code_discovery(base_state)
        for prog in result.custom_code.z_programs:
            assert prog.object_type == ObjectType.PROGRAM
        for fm in result.custom_code.z_function_modules:
            assert fm.object_type == ObjectType.FUNCTION_MODULE

    def test_lines_of_code(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_custom_code_discovery(base_state)
        assert result.custom_code.total_lines_of_code > 0


# ─────────────────────────────────────────────────────────────────────────────
# Agent 3: ATC Assessment
# ─────────────────────────────────────────────────────────────────────────────

class TestATCAssessment:
    def test_returns_report(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_atc_assessment(base_state)
        assert result.atc_report is not None

    def test_finding_counts(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_atc_assessment(base_state)
        atc = result.atc_report
        total = atc.critical_count + atc.high_count + atc.medium_count + atc.low_count
        assert total == atc.total_findings
        assert atc.total_findings > 0

    def test_has_critical_findings(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_atc_assessment(base_state)
        assert result.atc_report.critical_count > 0

    def test_finding_fields(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_atc_assessment(base_state)
        for finding in result.atc_report.findings[:5]:
            assert finding.object_name != ""
            assert finding.message != ""
            assert finding.priority in list(RiskLevel)


# ─────────────────────────────────────────────────────────────────────────────
# Agent 4: Simplification Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestSimplificationAnalysis:
    def test_returns_report(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_simplification_analysis(base_state)
        assert result.simplification_report is not None

    def test_has_all_categories(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_simplification_analysis(base_state)
        sr = result.simplification_report
        assert len(sr.deprecated_function_modules) > 0
        assert len(sr.deprecated_tables) > 0
        assert len(sr.business_partner_items) > 0
        assert len(sr.universal_journal_impacts) > 0

    def test_critical_impacts_counted(self, base_state, monkeypatch):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        result = run_simplification_analysis(base_state)
        assert result.simplification_report.critical_impacts > 0


# ─────────────────────────────────────────────────────────────────────────────
# Agent 5: Dependency Analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestDependencyAnalysis:
    def test_returns_graph(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        # Pre-populate custom code
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        result = run_dependency_analysis(state)
        assert result.dependency_graph is not None

    def test_graph_has_nodes(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        result = run_dependency_analysis(state)
        assert len(result.dependency_graph.nodes) > 0

    def test_graph_has_edges(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        result = run_dependency_analysis(state)
        assert len(result.dependency_graph.edges) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Agent 6: Risk Assessment
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskAssessment:
    @pytest.fixture
    def populated_state(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        state = run_simplification_analysis(state)
        state = run_dependency_analysis(state)
        return state

    def test_returns_score(self, populated_state):
        result = run_risk_assessment(populated_state)
        assert result.readiness_score is not None

    def test_score_in_range(self, populated_state):
        result = run_risk_assessment(populated_state)
        score = result.readiness_score.overall_score
        assert 0 <= score <= 100

    def test_risk_level_set(self, populated_state):
        result = run_risk_assessment(populated_state)
        assert result.readiness_score.risk_level in list(RiskLevel)

    def test_effort_days_positive(self, populated_state):
        result = run_risk_assessment(populated_state)
        assert result.readiness_score.estimated_effort_days > 0

    def test_critical_objects_populated(self, populated_state):
        result = run_risk_assessment(populated_state)
        # May or may not have critical objects, but list should exist
        assert isinstance(result.readiness_score.critical_objects, list)


# ─────────────────────────────────────────────────────────────────────────────
# Agent 7: Recommendations
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendations:
    @pytest.fixture
    def risk_state(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        state = run_simplification_analysis(state)
        state = run_dependency_analysis(state)
        state = run_risk_assessment(state)
        return state

    def test_returns_report(self, risk_state):
        result = run_recommendation_generation(risk_state)
        assert result.recommendation_report is not None

    def test_has_recommendations(self, risk_state):
        result = run_recommendation_generation(risk_state)
        assert len(result.recommendation_report.recommendations) > 0

    def test_recommendation_fields_complete(self, risk_state):
        result = run_recommendation_generation(risk_state)
        for rec in result.recommendation_report.recommendations[:3]:
            assert rec.object_name != ""
            assert rec.problem != ""
            assert rec.recommended_fix != ""
            assert rec.priority in list(RiskLevel)


# ─────────────────────────────────────────────────────────────────────────────
# Agent 8: Runbook
# ─────────────────────────────────────────────────────────────────────────────

class TestRunbook:
    @pytest.fixture
    def pre_runbook_state(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")
        state = run_custom_code_discovery(base_state)
        state = run_atc_assessment(state)
        state = run_simplification_analysis(state)
        state = run_dependency_analysis(state)
        state = run_risk_assessment(state)
        state = run_recommendation_generation(state)
        return state

    def test_returns_runbook(self, pre_runbook_state):
        result = run_runbook_generation(pre_runbook_state)
        assert result.runbook is not None

    def test_has_sections(self, pre_runbook_state):
        result = run_runbook_generation(pre_runbook_state)
        assert len(result.runbook.sections) >= 10

    def test_markdown_exported(self, pre_runbook_state):
        result = run_runbook_generation(pre_runbook_state)
        assert result.runbook.markdown_path
        import os
        assert os.path.exists(result.runbook.markdown_path)

    def test_sections_have_tasks(self, pre_runbook_state):
        result = run_runbook_generation(pre_runbook_state)
        for section in result.runbook.sections:
            assert len(section.tasks) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Full Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestFullPipeline:
    def test_all_steps_complete(self, base_state, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")

        state = run_landscape_discovery(base_state)
        state = run_custom_code_discovery(state)
        state = run_atc_assessment(state)
        state = run_simplification_analysis(state)
        state = run_dependency_analysis(state)
        state = run_risk_assessment(state)
        state = run_recommendation_generation(state)
        state = run_runbook_generation(state)
        state = run_dashboard_generation(state)

        assert "landscape_discovery" in state.steps_completed
        assert "custom_code_discovery" in state.steps_completed
        assert "atc_assessment" in state.steps_completed
        assert "simplification_analysis" in state.steps_completed
        assert "dependency_analysis" in state.steps_completed
        assert "risk_assessment" in state.steps_completed
        assert "recommendation_generation" in state.steps_completed
        assert "runbook_generation" in state.steps_completed
        assert "dashboard_generation" in state.steps_completed
        assert len(state.error_messages) == 0
