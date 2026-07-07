"""
SAP Migration Assessment Agent – Architecture Documentation
"""

# Architecture Overview
See README.md for the full ASCII architecture diagram.

## Sequence Diagram – Full Assessment Flow

```
User          Streamlit     FastAPI       LangGraph       SAP System
 │                │             │             │               │
 │─Start Assess──►│             │             │               │
 │                │─POST /assess►             │               │
 │                │             │─invoke()───►│               │
 │                │             │             │─RFC_SYSTEM_INFO►
 │                │             │             │◄─────────────┤
 │                │             │             │─Z_GET_CUSTOM_PROGRAMS►
 │                │             │             │◄─────────────┤
 │                │             │             │─SCI_RUN_CHECK►
 │                │             │             │◄─────────────┤
 │                │             │             │─[GPT-4o Recommendations]
 │                │             │             │─[PDF/DOCX/HTML export]
 │                │             │◄─complete──┤               │
 │                │◄─202 queued─┤             │               │
 │◄─Assessment──┤             │             │               │
 │  Complete     │             │             │               │
```

## Data Flow

AgentState flows through all 9 LangGraph nodes:

```
AgentState
  ├── assessment_id: UUID
  ├── sap_system: SAPSystem
  ├── landscape: LandscapeInventory        ← Agent 1
  ├── custom_code: CustomCodeInventory     ← Agent 2
  ├── atc_report: ATCReport               ← Agent 3
  ├── simplification_report               ← Agent 4
  ├── dependency_graph: DependencyGraph   ← Agent 5
  ├── readiness_score: MigrationReadiness ← Agent 6
  ├── recommendation_report               ← Agent 7
  ├── runbook: MigrationRunbook           ← Agent 8
  └── steps_completed: List[str]          ← Dashboard Agent 9
```
