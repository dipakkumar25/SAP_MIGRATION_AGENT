# Autonomous SAP S/4HANA Migration Assessment Agent

> **AI-powered, end-to-end SAP ECC → S/4HANA migration assessment platform**
> 
> Powered by LangGraph · FastAPI · Streamlit · GPT-4o · PyRFC · NetworkX · Plotly

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Agent Pipeline](#agent-pipeline)
- [REST API](#rest-api)
- [MCP Integration](#mcp-integration)
- [Testing](#testing)
- [Docker Deployment](#docker-deployment)
- [CI/CD](#cicd)
- [Security](#security)
- [Contributing](#contributing)

---

## Overview

The **Autonomous SAP Landscape Migration Agent** is a production-ready AI platform that automates the complete assessment lifecycle for migrating SAP ECC systems to SAP S/4HANA.

### What it does

| Step | Agent | Output |
|------|-------|--------|
| 1 | **Landscape Discovery** | System inventory (versions, components, RFC destinations) |
| 2 | **Custom Code Discovery** | All Z/Y objects, BADIs, User Exits, Custom Tables |
| 3 | **ATC Assessment** | ABAP Test Cockpit findings by severity |
| 4 | **Simplification DB Analysis** | Deprecated objects, UJ/BP/ML impacts |
| 5 | **Dependency Analysis** | NetworkX graph with PNG + HTML export |
| 6 | **Risk Assessment** | Weighted readiness score (0–100%) |
| 7 | **AI Recommendation Engine** | GPT-4o per-finding fix recommendations |
| 8 | **Runbook Generator** | Full migration runbook (PDF / DOCX / Markdown) |
| 9 | **Executive Dashboard** | Plotly interactive charts + HTML export |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend (port 8501)                │
│        SAP Login · Progress · Dashboard · Download Reports       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend (port 8000)                   │
│   /assess  /inventory  /atc  /risk  /runbook  /dashboard        │
└──────┬──────────────────────────────────────────┬───────────────┘
       │                                          │
┌──────▼──────────────────┐         ┌─────────────▼───────────────┐
│   LangGraph Workflow     │         │    MCP Server (stdio)        │
│                          │         │    run_full_assessment()     │
│  START                   │         │    get_landscape_inventory() │
│    ↓ Landscape           │         │    run_atc()                 │
│    ↓ Custom Code         │         │    calculate_risk()          │
│    ↓ ATC                 │         │    generate_runbook()        │
│    ↓ Simplification      │         └─────────────────────────────┘
│    ↓ Dependencies        │
│    ↓ Risk                │         ┌─────────────────────────────┐
│    ↓ [Human Approval]    │         │  SAP ECC System              │
│    ↓ Recommendations     │◄───────►│  RFC · OData · ATC           │
│    ↓ Runbook             │         │  (or MockRFCClient)          │
│    ↓ Dashboard           │         └─────────────────────────────┘
│  END                     │
└──────────────────────────┘
       │
┌──────▼────────────────────────────────────────────┐
│  Infrastructure                                    │
│  PostgreSQL (state) · ChromaDB (vector KB)         │
│  LangSmith (tracing) · Docker Compose              │
└───────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| AI Framework | LangGraph 0.1, LangChain 0.2 |
| LLM | OpenAI GPT-4o |
| Backend | FastAPI 0.111, Uvicorn |
| Frontend | Streamlit 1.36 |
| SAP Connectivity | PyRFC (real), MockRFCClient (demo) |
| Database | PostgreSQL 16 (SQLAlchemy async) |
| Vector DB | ChromaDB |
| Visualization | Plotly, NetworkX, Matplotlib |
| Reporting | ReportLab (PDF), python-docx (DOCX) |
| MCP | MCP 1.0 |
| Deployment | Docker, Docker Compose |
| Monitoring | LangSmith |
| CI/CD | GitHub Actions |

---

## Project Structure

```
sap-migration-agent/
├── app/
│   ├── agents/                   # 9 specialized assessment agents
│   │   ├── agent_01_landscape.py
│   │   ├── agent_02_custom_code.py
│   │   ├── agent_03_atc.py
│   │   ├── agent_04_simplification.py
│   │   ├── agent_05_dependencies.py
│   │   ├── agent_06_risk.py
│   │   ├── agent_07_recommendations.py
│   │   ├── agent_08_runbook.py
│   │   └── agent_09_dashboard.py
│   ├── graph/
│   │   └── workflow.py           # LangGraph workflow definition
│   ├── tools/
│   │   └── mcp_server.py         # MCP tools server
│   ├── services/
│   │   ├── sap_connector.py      # RFC connection factory
│   │   ├── mock_rfc.py           # Mock SAP RFC client
│   │   ├── llm_client.py         # OpenAI client factory
│   │   └── logger.py             # Structured logging
│   ├── models/
│   │   ├── schemas.py            # Pydantic schemas
│   │   ├── orm_models.py         # SQLAlchemy ORM
│   │   └── database.py           # Async engine + session
│   ├── prompts/
│   │   ├── recommendation_prompt.py
│   │   └── runbook_prompt.py
│   ├── reports/                  # Report templates
│   └── api/
│       ├── app.py                # FastAPI application factory
│       └── routes.py             # All REST endpoints
├── frontend/
│   └── app.py                    # Streamlit UI
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_mock_rfc.py
│   │   └── test_agents.py
│   └── integration/
│       ├── test_api.py
│       └── test_workflow.py
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.frontend
│   └── init.sql
├── config/
│   └── settings.py               # Pydantic settings
├── sample_data/
│   └── sample_assessment.json
├── .github/
│   └── workflows/ci.yml          # GitHub Actions CI/CD
├── main.py                       # FastAPI entry point
├── requirements.txt
├── docker-compose.yml
├── pytest.ini
├── .env.example
└── README.md
```

---

## Quick Start

### Option A — Demo Mode (no SAP required)

```bash
# 1. Clone and enter project
git clone <your-repo>
cd sap-migration-agent

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env

# 5. Start the API
uvicorn main:app --reload --port 8000

# 6. Start the Streamlit UI (new terminal)
streamlit run frontend/app.py

# 7. Open browser → http://localhost:8501
#    Click "Start Assessment" with Demo Mode checked ✓
```

### Option B — Docker Compose (recommended for production)

```bash
# 1. Copy and configure env
cp .env.example .env
# Edit .env with your OpenAI key and SAP credentials

# 2. Start all services
docker compose up -d

# 3. Services available at:
#    Frontend:  http://localhost:8501
#    API:       http://localhost:8000
#    API Docs:  http://localhost:8000/docs
#    ChromaDB:  http://localhost:8001
#    Postgres:  localhost:5432
```

### Option C — Real SAP Connection

```bash
# Prerequisites: SAP NW RFC SDK installed, pyrfc built

# In .env:
SAP_USE_MOCK=false
SAP_HOST=your-sap-host.company.com
SAP_SYSNR=00
SAP_CLIENT=100
SAP_USER=RFC_USER
SAP_PASSWORD=your-password

# Then run normally (Option A or B above)
```

---

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SAP_USE_MOCK` | `true` | Use built-in mock SAP data |
| `SAP_HOST` | `localhost` | SAP application server host |
| `SAP_SYSNR` | `00` | SAP system number |
| `SAP_CLIENT` | `100` | SAP client |
| `SAP_USER` | `RFC_USER` | RFC user |
| `SAP_PASSWORD` | — | RFC password |
| `OPENAI_API_KEY` | — | OpenAI API key (for AI recommendations) |
| `OPENAI_MODEL` | `gpt-4o` | LLM model |
| `DATABASE_URL` | PostgreSQL | Async database URL |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `REPORTS_OUTPUT_DIR` | `output/reports` | Report output directory |

---

## Agent Pipeline

### LangGraph Workflow

The assessment runs as a directed acyclic graph with 9 nodes + 1 human-approval checkpoint:

```python
from app.graph.workflow import run_assessment
from app.models.schemas import SAPSystem

result = run_assessment(SAPSystem(sid="ECC", host="sap.company.com"))
print(f"Readiness: {result.readiness_score.overall_score:.1f}%")
print(f"Risk Level: {result.readiness_score.risk_level}")
```

### Human-Approval Checkpoint

After the Risk Assessment node, the workflow pauses at `human_approval`. 
In automated mode it self-approves. To require manual review, call:

```python
# Interrupt before the human_approval node
graph.invoke(state, config={"configurable": {"thread_id": "..."}, 
                             "interrupt_before": ["human_approval"]})
```

---

## REST API

Full OpenAPI documentation at `http://localhost:8000/docs`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/assess` | Start full async assessment |
| `GET` | `/api/v1/status/{id}` | Poll assessment status |
| `POST` | `/api/v1/inventory` | Run landscape discovery |
| `POST` | `/api/v1/custom-code` | Run custom code discovery |
| `POST` | `/api/v1/atc` | Run ATC assessment |
| `POST` | `/api/v1/dependencies` | Build dependency graph |
| `POST` | `/api/v1/risk` | Calculate risk score |
| `POST` | `/api/v1/recommendations` | Generate AI recommendations |
| `POST` | `/api/v1/runbook` | Generate migration runbook |
| `GET` | `/api/v1/dashboard/{id}` | Get dashboard data (JSON) |
| `GET` | `/api/v1/dashboard/{id}/html` | Get dashboard (HTML) |
| `GET` | `/api/v1/report/{id}/{type}` | Download report (pdf/docx/markdown) |

### Example: Start Assessment

```bash
curl -X POST http://localhost:8000/api/v1/assess \
  -H "Content-Type: application/json" \
  -d '{"system_id": "ECC", "host": "localhost", "client": "100"}'

# Response: {"assessment_id": "abc-123", "status": "queued", ...}

# Poll status
curl http://localhost:8000/api/v1/status/abc-123
```

---

## MCP Integration

The agent exposes all capabilities as MCP tools via stdio transport.

### Register with Bob / Claude

```json
{
  "servers": {
    "sap-migration-agent": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "app.tools.mcp_server"],
      "cwd": "/path/to/sap-migration-agent"
    }
  }
}
```

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `run_full_assessment` | Complete pipeline assessment |
| `get_landscape_inventory` | System metadata only |
| `get_custom_programs` | Custom code counts |
| `run_atc` | ATC findings summary |
| `get_simplification_items` | Simplification DB analysis |
| `calculate_risk` | Risk score only |
| `generate_runbook` | Runbook generation |
| `export_dashboard` | Dashboard export |

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests only
pytest tests/integration/    # Integration tests only

# Target coverage: 90%+
```

---

## Docker Deployment

```bash
# Development
docker compose up -d

# Production (with real SAP + OpenAI)
SAP_USE_MOCK=false OPENAI_API_KEY=sk-... docker compose up -d

# View logs
docker compose logs -f api
docker compose logs -f frontend

# Stop
docker compose down
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 8501 | Streamlit UI |
| `api` | 8000 | FastAPI backend |
| `postgres` | 5432 | PostgreSQL database |
| `chromadb` | 8001 | ChromaDB vector store |

---

## CI/CD

GitHub Actions workflow in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

1. **Lint** — Ruff linting + format check
2. **Test** — Pytest with PostgreSQL service container
3. **Docker Build** — Multi-stage build + push to Docker Hub (on `main`)

---

## Security

- **Environment variables** — All secrets via `.env` (never committed)
- **Encrypted SAP credentials** — `SecretStr` Pydantic fields
- **JWT Authentication** — JOSE-based JWT for API endpoints (configured)
- **RBAC** — Role-based access control pattern (extend in `api/routes.py`)
- **Audit logging** — Structured JSON logs via structlog
- **Input validation** — Pydantic v2 strict validation on all endpoints
- **Non-root Docker** — All containers run as `appuser` (UID 1000)
- **Health checks** — All Docker services have health checks

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-agent`
3. Add tests for new functionality
4. Run: `pytest tests/ --cov=app --cov-fail-under=80`
5. Open a pull request

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Made with ❤️ by IBM Bob · SAP Migration Assessment Agent v1.0.0</sub>
</div>
