"""
Prompt templates for the AI Recommendation Engine.
"""
from __future__ import annotations

from app.models.schemas import ATCFinding

RECOMMENDATION_SYSTEM_PROMPT = """
You are a Senior SAP S/4HANA Migration Consultant with deep expertise in ABAP, SAP Architecture,
and SAP S/4HANA conversion projects. Your task is to analyze ATC findings and provide
structured, actionable recommendations.

Always respond with valid JSON matching this exact schema:
{
  "problem": "Clear description of the problem",
  "root_cause": "Technical root cause analysis",
  "business_impact": "Impact on business processes and operations",
  "technical_impact": "Technical implications and risks",
  "recommended_fix": "Step-by-step remediation instructions",
  "estimated_effort": "Effort estimate (e.g., '4 hours', '2 days')",
  "required_consultant": "Type of consultant needed",
  "estimated_duration_days": <integer>,
  "sap_note": "Relevant SAP Note number or null",
  "best_practice_reference": "SAP Best Practice reference or null"
}
"""


def build_finding_prompt(finding: ATCFinding) -> str:
    return f"""
Analyze the following SAP ATC finding and provide a migration recommendation:

Object Name: {finding.object_name}
Object Type: {finding.object_type}
Check: {finding.check_title}
Category: {finding.category.value}
Priority: {finding.priority.value}
Message: {finding.message}
Line: {finding.line_number or 'N/A'}

Provide a comprehensive recommendation for fixing this issue during SAP ECC to S/4HANA migration.
"""
