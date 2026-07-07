"""
Pydantic schemas for all domain objects used across agents.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ATCCategory(str, Enum):
    SYNTAX = "syntax"
    PERFORMANCE = "performance"
    SECURITY = "security"
    OBSOLETE_API = "obsolete_api"
    STYLE = "style"
    ROBUSTNESS = "robustness"


class ObjectType(str, Enum):
    PROGRAM = "PROG"
    FUNCTION_MODULE = "FUGR"
    CLASS = "CLAS"
    TABLE = "TABL"
    VIEW = "VIEW"
    CDS_VIEW = "DDLS"
    ENHANCEMENT = "ENHO"
    BADI = "SXCI"
    USER_EXIT = "EXIT"
    INCLUDE = "INCL"
    FORM = "FORM"


class MigrationStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


# ─────────────────────────────────────────────────────────────────────────────
# SAP System
# ─────────────────────────────────────────────────────────────────────────────

class SAPSystem(BaseModel):
    sid: str = Field(..., description="SAP System ID, e.g. ECC")
    host: str
    sysnr: str = "00"
    client: str = "100"
    description: Optional[str] = None


class LandscapeInventory(BaseModel):
    system_id: str
    hostname: str
    sap_version: str
    kernel_version: str
    hana_version: Optional[str] = None
    installed_components: List[Dict[str, str]] = Field(default_factory=list)
    installed_addons: List[Dict[str, str]] = Field(default_factory=list)
    active_clients: List[Dict[str, str]] = Field(default_factory=list)
    transport_domains: List[str] = Field(default_factory=list)
    rfc_destinations: List[Dict[str, str]] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Custom Code
# ─────────────────────────────────────────────────────────────────────────────

class CustomObject(BaseModel):
    object_name: str
    object_type: ObjectType
    package: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    lines_of_code: int = 0
    last_changed_by: Optional[str] = None
    last_changed_date: Optional[datetime] = None
    transport_request: Optional[str] = None
    is_modified_standard: bool = False


class CustomCodeInventory(BaseModel):
    z_programs: List[CustomObject] = Field(default_factory=list)
    z_function_modules: List[CustomObject] = Field(default_factory=list)
    z_classes: List[CustomObject] = Field(default_factory=list)
    enhancements: List[CustomObject] = Field(default_factory=list)
    badis: List[CustomObject] = Field(default_factory=list)
    user_exits: List[CustomObject] = Field(default_factory=list)
    custom_tables: List[CustomObject] = Field(default_factory=list)
    cds_views: List[CustomObject] = Field(default_factory=list)
    total_objects: int = 0
    total_lines_of_code: int = 0
    collected_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# ATC Findings
# ─────────────────────────────────────────────────────────────────────────────

class ATCFinding(BaseModel):
    object_name: str
    object_type: str
    check_id: str
    check_title: str
    message: str
    category: ATCCategory
    priority: RiskLevel
    line_number: Optional[int] = None
    source_snippet: Optional[str] = None
    quick_fix_available: bool = False
    documentation_url: Optional[str] = None


class ATCReport(BaseModel):
    findings: List[ATCFinding] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    total_findings: int = 0
    objects_checked: int = 0
    run_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Simplification DB
# ─────────────────────────────────────────────────────────────────────────────

class SimplificationItem(BaseModel):
    item_id: str
    title: str
    category: str          # e.g. "REMOVED_TRANSACTION", "DEPRECATED_FM"
    object_name: str
    description: str
    impact: RiskLevel
    affected_in_system: bool = False
    migration_note: Optional[str] = None
    successor_object: Optional[str] = None


class SimplificationReport(BaseModel):
    removed_transactions: List[SimplificationItem] = Field(default_factory=list)
    deprecated_function_modules: List[SimplificationItem] = Field(default_factory=list)
    deprecated_tables: List[SimplificationItem] = Field(default_factory=list)
    compatibility_views: List[SimplificationItem] = Field(default_factory=list)
    universal_journal_impacts: List[SimplificationItem] = Field(default_factory=list)
    business_partner_items: List[SimplificationItem] = Field(default_factory=list)
    material_ledger_items: List[SimplificationItem] = Field(default_factory=list)
    total_impacts: int = 0
    critical_impacts: int = 0
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────────────────

class DependencyEdge(BaseModel):
    source: str
    target: str
    edge_type: str   # "calls", "uses_table", "implements", "triggers"
    weight: int = 1


class DependencyGraph(BaseModel):
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[DependencyEdge] = Field(default_factory=list)
    graph_png_path: Optional[str] = None
    graph_html_path: Optional[str] = None
    max_depth: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Risk Assessment
# ─────────────────────────────────────────────────────────────────────────────

class RiskScore(BaseModel):
    object_name: str
    object_type: str
    atc_score: float = 0.0
    complexity_score: float = 0.0
    deprecated_api_score: float = 0.0
    modification_score: float = 0.0
    dependency_score: float = 0.0
    performance_score: float = 0.0
    unused_score: float = 0.0
    total_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW


class MigrationReadinessScore(BaseModel):
    overall_score: float = Field(..., ge=0, le=100, description="0–100 readiness %")
    risk_level: RiskLevel
    object_scores: List[RiskScore] = Field(default_factory=list)
    critical_objects: List[str] = Field(default_factory=list)
    high_risk_objects: List[str] = Field(default_factory=list)
    estimated_effort_days: int = 0
    assessed_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Recommendations
# ─────────────────────────────────────────────────────────────────────────────

class Recommendation(BaseModel):
    finding_id: str
    object_name: str
    problem: str
    root_cause: str
    business_impact: str
    technical_impact: str
    recommended_fix: str
    estimated_effort: str
    required_consultant: str
    estimated_duration_days: int
    priority: RiskLevel
    sap_note: Optional[str] = None
    best_practice_reference: Optional[str] = None


class RecommendationReport(BaseModel):
    recommendations: List[Recommendation] = Field(default_factory=list)
    total_effort_days: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Runbook
# ─────────────────────────────────────────────────────────────────────────────

class RunbookSection(BaseModel):
    title: str
    order: int
    content: str
    tasks: List[str] = Field(default_factory=list)
    estimated_duration: Optional[str] = None
    responsible_team: Optional[str] = None


class MigrationRunbook(BaseModel):
    project_name: str
    system_id: str
    sections: List[RunbookSection] = Field(default_factory=list)
    total_estimated_duration_weeks: int = 0
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    markdown_path: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# Agent State (LangGraph)
# ─────────────────────────────────────────────────────────────────────────────

class AgentState(BaseModel):
    """Complete workflow state passed between LangGraph nodes."""
    assessment_id: str
    sap_system: SAPSystem
    status: MigrationStatus = MigrationStatus.NOT_STARTED
    landscape: Optional[LandscapeInventory] = None
    custom_code: Optional[CustomCodeInventory] = None
    atc_report: Optional[ATCReport] = None
    simplification_report: Optional[SimplificationReport] = None
    dependency_graph: Optional[DependencyGraph] = None
    readiness_score: Optional[MigrationReadinessScore] = None
    recommendation_report: Optional[RecommendationReport] = None
    runbook: Optional[MigrationRunbook] = None
    error_messages: List[str] = Field(default_factory=list)
    current_step: str = "start"
    steps_completed: List[str] = Field(default_factory=list)
    human_approved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
