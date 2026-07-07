"""
Prompt for runbook generation.
"""

RUNBOOK_SYSTEM_PROMPT = """
You are a Senior SAP S/4HANA Conversion Project Manager and BASIS Consultant.
Generate a detailed, enterprise-grade migration runbook based on the assessment data provided.
The runbook must be practical, sequenced correctly, and ready for immediate use by a project team.
"""

RUNBOOK_USER_TEMPLATE = """
Generate a complete SAP ECC to S/4HANA Migration Runbook for the following system:

System ID: {system_id}
Overall Readiness Score: {readiness_score}%
Risk Level: {risk_level}
Total Custom Objects: {total_objects}
Total ATC Findings: {total_findings}
Critical Findings: {critical_count}
Estimated Effort: {effort_days} days
Key Risks: {key_risks}

The runbook must include these sections:
1. Executive Summary
2. Project Preparation & Planning
3. System & Technical Pre-checks
4. Custom Code Adaptation Plan
5. Data Cleansing & Migration
6. Business Partner Conversion
7. Material Ledger Activation
8. Universal Journal Migration
9. Integration & Interface Testing
10. User Acceptance Testing
11. Cutover Planning & Execution
12. Rollback Plan
13. Post Go-Live Activities & Hypercare

For each section provide:
- Clear title
- Detailed tasks (minimum 5 tasks per section)
- Estimated duration
- Responsible team

Format as JSON with this structure:
{
  "sections": [
    {
      "title": "Section Title",
      "order": 1,
      "content": "Detailed section description",
      "tasks": ["Task 1", "Task 2", ...],
      "estimated_duration": "X weeks",
      "responsible_team": "Team Name"
    }
  ],
  "total_estimated_duration_weeks": <integer>
}
"""
