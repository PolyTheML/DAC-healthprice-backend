# AGENTS.md — DAC HealthPrice Platform & Underwriting Agent

> This file is the single source of truth for AI coding agents working on this repository.  
> Read it first.  Do not assume general Python/FastAPI conventions — this project has specific quirks, dual apps, and shared modules that are easy to confuse.

---

## 1. Project Overview

This repository contains **two related systems** that share code but serve different purposes:

1. **DAC HealthPrice Platform** — A production-grade health & life insurance pricing backend for Cambodia and Vietnam.  
   - Poisson-Gamma GLM pricing engine with explicit, auditable coefficient tables.  
   - PDF medical-record ingestion via Claude Vision API.  
   - LangGraph underwriting workflow (intake → pricing → review → HITL → decision).  
   - 6-layer anti-scraping protection (rate limiting, session quotas, parameter-sweep detection, output banding, partner API keys).

2. **Personal Knowledge Base** — An LLM-maintained Obsidian-compatible wiki for research accumulation (Karpathy autoresearch pattern).  
   - Immutable sources in `/sources`.  
   - Mutable synthesis in `/wiki`.  
   - Governed by `CLAUDE.md` schema.

**Current status**: The HealthPrice backend is deployed on Render (`render.yaml`). The Knowledge Base is local-only.

---

## 2. Technology Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.11+ |
| Web Framework | FastAPI (two separate apps) |
| Database | PostgreSQL (asyncpg raw SQL in `app/`, SQLAlchemy 2.0 ORM in `api/`) |
| ML / Data Science | scikit-learn, XGBoost, LightGBM, SHAP, numpy, pandas |
| PDF / OCR | pypdf, reportlab, Claude Vision API |
| Workflow Orchestration | LangGraph (`medical_reader/graph.py`) |
| Auth | PyJWT (HS256), HTTP Bearer, partner API keys |
| External APIs | Anthropic Claude API (chat proxy, medical extraction, scenario agent) |
| ETL | httpx, custom `fetch → validate → store → audit` pipeline |
| Deployment | Render.com (PaaS) via `render.yaml` + `Procfile` |
| Knowledge Base | Markdown (Obsidian-compatible), LLM-maintained |

**No Docker, no CI/CD, no Kubernetes** — those exist only as architecture documents (`PRODUCTION_STACK.md`) and are not yet implemented.

---

## 3. Project Structure

```
├── app/                          # Main HealthPrice API (v2.3) — DEPLOYED
│   ├── main.py                   # 1,710-line monolithic FastAPI app (core engine)
│   ├── routes/                   # Mounted routers: health_pricing, life_pricing, escalation
│   ├── pricing_engine/           # GLM health pricing, auto GLM, final pricing
│   ├── ml/                       # LightGBM inference + training
│   ├── data/                     # Feature engineering, health validation
│   ├── feedback/                 # Claims & metrics tracking
│   ├── monitoring/               # Drift detection alerts
│   └── pyproject.toml            # Package: dac-auto-pricing v2.0.0
│
├── api/                          # Secondary DAC-UW Underwriting API (v0.1.0)
│   ├── main.py                   # Smaller FastAPI app (cleaner architecture)
│   ├── routers/                  # applications, auth, cases, pricing, portfolio, dashboard, calibration
│   ├── middleware/jwt.py         # JWT auth dependency
│   ├── database.py               # SQLAlchemy engine + SessionLocal
│   ├── db_models.py              # ORM models (ApplicationRecord, CaseRecord)
│   ├── models.py                 # Pydantic schemas
│   ├── crud.py                   # CRUD helpers
│   └── deps.py                   # DI: singleton LangGraph instance
│
├── medical_reader/               # OCR → JSON → GLM pipeline (shared by both apps)
│   ├── nodes/                    # LangGraph nodes: intake, pricing, review, hitl, decision, life_pricing, health_pricing_bridge
│   ├── pricing/                  # Assumptions, calculator, Cambodia pricing, escalation calculator, versioning
│   ├── graph.py                  # StateGraph definition + run_case()/submit_review()
│   ├── state.py                  # UnderwritingState Pydantic state object
│   ├── extractor.py              # PDF → structured JSON (pypdf + Claude)
│   ├── validator.py              # 3-layer validation (schema, domain, consistency)
│   ├── schemas.py                # MedicalRecord Pydantic models
│   ├── calibration.py            # CalibrationEngine (reads ETL data, proposes multipliers)
│   └── app.py                    # Streamlit dashboard for underwriting workflow
│
├── etl/                          # Data sync pipeline
│   ├── config.py                 # ETLConfig dataclass (env-driven)
│   ├── fetch.py                  # ProductionDataFetcher (httpx)
│   ├── validate.py               # SchemaValidator + OutlierDetector
│   ├── storage.py                # LocalDatasetWriter (SQLite + JSON audit)
│   └── pipeline.py               # ETLPipeline orchestrator
│
├── portfolio/                    # Synthetic portfolio generation & calibration
│   ├── generator.py              # Creates synthetic_portfolio.parquet
│   ├── analysis.py               # ClaimsAnalyzer (A/E ratios, lifts)
│   └── calibration.py            # calibrate_assumptions() + build_calibrated_assumptions()
│
├── models/                       # Serialized ML models
│   ├── *.pkl                     # IPD/OPD/Dental/Maternity freq+sev models
│   └── model_meta.pkl
│
├── scripts/                      # Utilities & benchmarks
│   ├── generate_claims.py        # Synthetic claims generator (CLI)
│   ├── run_benchmark.py          # Competitor pricing benchmark
│   ├── train_custom_model.py     # Prospect-specific coefficient calibration
│   ├── train_model.py            # Frequency-severity trainer (deploy-time)
│   └── claims_*.csv              # Pre-generated synthetic datasets
│
├── tests/                        # Test suite
│   └── (see root test files below)
│
├── analytics/                    # PSI drift monitoring + HITL override rate
│   └── monitor.py
│
├── wiki/                         # Knowledge Base (LLM-maintained)
├── sources/                      # Immutable source documents (PDFs, theses)
├── data/                         # Runtime data (synced/, synthetic_portfolio.parquet)
├── test_data/                    # Sample PDFs for medical_reader testing
├── test_outputs/                 # Extracted JSON outputs from test runs
├── _archive/                     # Deprecated code — do not use unless asked
└── Root test files:
    ├── test_pricing_calculator.py    # ~20 unit tests for medical_reader.pricing.calculator
    ├── test_calibration_engine.py    # 6 tests for CalibrationEngine (tmp SQLite + monkeypatch)
    └── test_etl_pipeline.py          # 6 smoke tests for ETL (fake fetcher)
```

### 3.1 Important Distinction: `app/` vs `api/`

- **`app/main.py`** is the **deployed** production API (`render.yaml` starts `uvicorn app.main:app`).  
  It is monolithic (~1,700 lines), uses raw `asyncpg`, and contains the core GLM pricing engine, anti-scraping, JWT staff auth, partner API keys, and scenario AI agent.

- **`api/main.py`** is a **secondary** FastAPI app with cleaner modular architecture.  
  It uses SQLAlchemy ORM, seeds demo data on startup, and is designed for the LangGraph underwriting pipeline.  
  It is **NOT** the deployed entry point, but its routers and modules are imported by `app/main.py` in several places.

**Do not confuse the two.** When adding endpoints, check whether the requirement is for the production API (`app/`) or the underwriting workflow API (`api/`).

### 3.2 Shared Modules

Both apps import from these modules freely:
- `medical_reader/` — PDF extraction, pricing, LangGraph workflow
- `portfolio/` — Synthetic portfolio, A/E analysis
- `analytics/monitor.py` — PSI drift, override rates
- `etl/` — Data sync pipeline

---

## 4. Key Entry Points

| Purpose | Command |
|---------|---------|
| Production HealthPrice API | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| Underwriting API (local dev) | `uvicorn api.main:app --host 0.0.0.0 --port 8000` |
| Medical Reader Streamlit demo | `python -m medical_reader.run_demo` or `streamlit run medical_reader/app.py` |
| ETL sync (manual trigger) | `python -m etl.pipeline` |
| Synthetic claims generator | `python scripts/generate_claims.py --n 1000 --output claims.csv` |
| Competitor benchmark | `python scripts/run_benchmark.py --base-url http://localhost:8000` |

---

## 5. Configuration & Environment Variables

There is **no centralized settings file** (no `pydantic-settings` config). Everything is env-var driven:

**`app/main.py` reads:**
- `DATABASE_URL` — PostgreSQL connection string (asyncpg)
- `MODEL_DIR` — defaults to `models`
- `ALLOWED_ORIGINS` — CORS origins, comma-separated
- `JWT_SECRET` — HS256 secret for staff tokens
- `STAFF_ADMIN_PASS`, `STAFF_RADET_PASS`, `STAFF_ANALYST_PASS` — default passwords
- `ANTHROPIC_API_KEY` — Claude API access
- `DAILY_QUOTE_LIMIT` — default 15
- `RATE_LIMIT_PER_MIN` — default 30
- `SESSION_QUOTE_LIMIT`, `SWEEP_THRESHOLD` — anti-scraping knobs

**`api/database.py` reads:**
- `DATABASE_URL` — normalizes `postgres://` → `postgresql://` for SQLAlchemy

**`etl/config.py` reads:**
- `ETL_PRODUCTION_API_URL`, `ETL_PRODUCTION_API_KEY`
- `ETL_DATASET_DIR`, `ETL_SQLITE_PATH`, `ETL_AUDIT_LOG_PATH`

**Render deployment (`render.yaml`):**
- Build: `pip install -r requirements.txt && python scripts/train_model.py`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Python 3.11.7, Singapore region

---

## 6. Build and Test Commands

### Install dependencies
```bash
pip install -r requirements.txt
# For the secondary API / LangGraph stack:
pip install -r requirements-api.txt
# For the Streamlit demo:
pip install -r requirements-demo.txt
```

### Run tests
```bash
# All pytest tests (root + tests/)
pytest -v

# Specific test files
pytest test_pricing_calculator.py -v
pytest test_calibration_engine.py -v
pytest test_etl_pipeline.py -v
```

**Note:** `medical_reader/test_workflow.py` is an executable script, **not** a pytest test. Run it directly:
```bash
python medical_reader/test_workflow.py
```

### Train models (deploy-time or local)
```bash
# Production frequency-severity models (IPD/OPD/Dental/Maternity)
python scripts/train_model.py

# Prospect-specific custom calibration
python scripts/train_custom_model.py --prospect-id PROSPECT_001 --claims data/claims.csv
```

### Code formatting (configured in `app/pyproject.toml`)
```bash
black --line-length 100 .
isort --profile black --line-length 100 .
```

---

## 7. Code Style Guidelines

- **Line length**: 100 characters (`tool.black.line-length = 100` in `app/pyproject.toml`).
- **Import sorting**: `isort` with `profile = "black"`.
- **Type hints**: Optional; `mypy` is configured but `disallow_untyped_defs = false`.
- **Docstrings**: Google-style or plain descriptive strings. Tests use class-based grouping with `Test*` naming.
- **File naming**: `lowercase_with_underscores.py` for Python; `lowercase-with-hyphens.md` for markdown (wiki).

### Style quirks in this codebase

- `app/main.py` is intentionally **monolithic** (~1,700 lines) for deployment simplicity on Render's free tier.  
  Do not refactor it into dozens of files unless explicitly asked — the current structure is a deliberate trade-off.

- `api/` is the **cleaner modular reference** for new underwriting-related features. If adding routers to `api/`, follow the existing pattern: Pydantic schemas in `api/models.py`, ORM models in `api/db_models.py`, CRUD in `api/crud.py`, routes in `api/routers/{name}.py`.

- **Anti-scraping code** in `app/main.py` uses compact one-liner style (`_rl()`, `_probe_buffer`, etc.). Keep it compact — these are hot-path functions.

- **GLM coefficients** are stored as explicit Python dicts (`COEFF` in `app/main.py`, ` RiskFactorMultipliers` in `medical_reader/pricing/assumptions.py`). Never hide them in black-box models for core pricing.

---

## 8. Testing Instructions

### Test framework
- **pytest** with `pytest-asyncio` for async tests.
- **No `pytest.ini`, `conftest.py`, or `setup.cfg`** exists. Tests are self-contained.

### Test organization

| File | Scope | Key technique |
|------|-------|---------------|
| `test_pricing_calculator.py` | Pure unit tests for actuarial math | Direct function calls, `pytest.approx` |
| `test_calibration_engine.py` | CalibrationEngine integration | `tmp_path` + `monkeypatch` for isolated SQLite & version dirs |
| `test_etl_pipeline.py` | ETL smoke tests | `_FakeFetcher` subclass to avoid hitting Render backend |
| `medical_reader/test_workflow.py` | Full LangGraph workflow | Executable script (not pytest); processes real test PDFs |

### Writing new tests
- Use `tmp_path` and `monkeypatch` when touching the filesystem (especially `medical_reader/pricing/versioning` and `etl/storage`).
- Use fake fetchers/subclasses (like `_FakeFetcher`) instead of mocking `httpx` when testing ETL.
- The real `assumptions_versions/` directory must not be mutated by tests. Copy it to `tmp_path` and monkeypatch `versioning.VERSIONS_DIR`.

### Running with coverage
```bash
pytest --cov=app --cov=medical_reader --cov=etl --cov=portfolio -v
```

---

## 9. Security Considerations

### Authentication layers
1. **Staff JWT** (`/auth/login`) — role-based (`admin`, `underwriter`, `analyst`). Expires in 8 hours. Secret from `JWT_SECRET` env var.
2. **Session tokens** (`/api/v2/session`) — anonymous consumer quotes, limited to `SESSION_QUOTE_LIMIT` per session.
3. **Partner API keys** (`X-Partner-Key` header) — per-partner daily quotas, stored in-memory (`_partner_keys`).

### Anti-scraping (6 layers in `app/main.py`)
1. Per-IP rate limiting (token bucket, `RATE_LIMIT_PER_MIN`).
2. Daily quote limit per IP (`DAILY_QUOTE_LIMIT`).
3. Session quote limit (`SESSION_QUOTE_LIMIT`).
4. Parameter-sweep detection (`SWEEP_THRESHOLD` on `SWEEP_FIELDS`).
5. Output banding (premiums rounded to nearest $5).
6. Partner key quotas (`_partner_keys` with daily counters).

### Sensitive data handling
- PDFs may contain PHI. The `intake` node uses Claude Vision API; PDF content is base64-encoded and sent to Anthropic.
- Database `applications` table stores medical data as JSONB.
- No encryption-at-rest is implemented in the current deployment (noted as future work in `PRODUCTION_STACK.md`).

### Secrets
- Never commit `.env` files. The repo has no `.env.example`.
- Default passwords in `app/main.py` are development-only (`dac2026!`). They are overridden by env vars in production.

---

## 10. Deployment

### Current: Render.com (PaaS)
- **Config**: `render.yaml` + `Procfile`
- **Build command**: `pip install -r requirements.txt && python scripts/train_model.py`
- **Start command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check**: `GET /health`
- **Region**: Singapore
- **Plan**: Free tier

### Model artifacts at deploy time
`scripts/train_model.py` runs during the Render build step. It generates:
- `models/*.pkl` (IPD/OPD/Dental/Maternity frequency + severity)
- `data/synthetic/*.csv`

If models are missing at runtime, the API falls back to GLM-only pricing.

### No CI/CD
There are no GitHub Actions, GitLab CI, or pre-commit hooks. Deployment is manual (git push → Render auto-deploy).

---

## 11. Important Conventions & Caveats

### Assumption versioning (`medical_reader/pricing/versioning.py`)
- Assumptions are JSON files in `medical_reader/pricing/assumptions_versions/`.
- Active version is tracked in `VERSION_MANIFEST.json`.
- Current active ID: `v3.0-cambodia-2026-04-14`.
- `CalibrationEngine` creates **candidate** versions; auto-promotes only if fairness check passes (disparate impact ratio ≥ 0.80 per Prakas 093).
- **Never** delete or rename existing version files — the calibration engine depends on parent versioning.

### Database divergence
- `app/main.py` uses **asyncpg** with raw SQL (tables: `hp_quote_log`, `hp_user_behavior`, `hp_sessions`, `hp_partner_keys`, `applications`, `documents`).
- `api/main.py` uses **SQLAlchemy 2.0 ORM** with SQLite/PostgreSQL (`api/database.py`, tables: `ApplicationRecord`, `CaseRecord`).
- These schemas are **not unified**. Do not assume a table created in one app exists in the other.

### `_archive/` directory
- Contains deprecated Streamlit demos and standalone research daemons.
- **Do not read or reference** unless explicitly asked by the user.

### Knowledge Base (`wiki/`, `sources/`, `CLAUDE.md`)
- `CLAUDE.md` is the schema/governance document for the knowledge base.
- `sources/` is immutable — never modify files there.
- `wiki/` is LLM-maintained — agents may create/update pages there during ingestion/query/lint workflows.
- See `README.md` (root) for knowledge base usage instructions.

---

## 12. Quick Reference: Common Tasks

| Task | Where to look / What to run |
|------|----------------------------|
| Add a new health pricing endpoint | `app/routes/health_pricing.py` or `app/main.py` (if needs anti-scraping) |
| Add a new underwriting router | `api/routers/{name}.py`, register in `api/main.py` |
| Modify GLM coefficients | `app/main.py` (`COEFF` dict) or `medical_reader/pricing/assumptions.py` |
| Change assumption version | `medical_reader/pricing/versioning.py` + create new JSON in `assumptions_versions/` |
| Run ETL sync manually | `python -m etl.pipeline` or call `ETLPipeline.run_sync()` |
| Calibrate from production quotes | `api/routers/calibration.py` → `POST /api/v1/calibration/recalibrate` |
| Generate synthetic claims | `python scripts/generate_claims.py --n 1000` |
| Check PSI drift | `analytics/monitor.py` → `calculate_psi()` |
| Process a test PDF through underwriting | `python medical_reader/test_workflow.py` |

---

*Last updated: 2026-04-22*  
*If you modify project structure, build steps, or testing strategy, update this file.*
