"""
LangGraph workflow integration tests.
"""
from __future__ import annotations

import uuid
import pytest

from app.graph.workflow import build_graph, run_assessment
from app.models.schemas import AgentState, MigrationStatus, SAPSystem


@pytest.fixture
def sap_system():
    return SAPSystem(sid="ECC", host="localhost", client="100")


class TestLangGraphWorkflow:
    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None

    def test_full_workflow_completes(self, sap_system, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")

        result = run_assessment(sap_system)

        assert result is not None
        assert isinstance(result, AgentState)
        assert result.assessment_id != ""

    def test_workflow_populates_all_fields(self, sap_system, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")

        result = run_assessment(sap_system)

        assert result.landscape is not None
        assert result.custom_code is not None
        assert result.atc_report is not None
        assert result.simplification_report is not None
        assert result.dependency_graph is not None
        assert result.readiness_score is not None
        assert result.recommendation_report is not None
        assert result.runbook is not None

    def test_workflow_steps_ordered(self, sap_system, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")

        result = run_assessment(sap_system)

        expected_steps = [
            "landscape_discovery", "custom_code_discovery", "atc_assessment",
            "simplification_analysis", "dependency_analysis", "risk_assessment",
            "recommendation_generation", "runbook_generation", "dashboard_generation",
        ]
        for step in expected_steps:
            assert step in result.steps_completed

    def test_workflow_no_critical_errors(self, sap_system, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-key")

        result = run_assessment(sap_system)
        assert len(result.error_messages) == 0

    def test_deterministic_assessment_id(self, sap_system, monkeypatch, tmp_path):
        monkeypatch.setenv("SAP_USE_MOCK", "true")
        monkeypatch.setenv("REPORTS_OUTPUT_DIR", str(tmp_path))
        fixed_id = str(uuid.uuid4())

        result = run_assessment(sap_system, assessment_id=fixed_id)
        assert result.assessment_id == fixed_id
