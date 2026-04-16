# DAC-UW-Agent: ETL Pipeline & Recalibration System
## Design Summary for Implementation

**Document Version**: 1.0  
**Created**: 2026-04-16  
**Status**: Ready for Opus Implementation  
**Scope**: Option A (Periodic Batch Sync) with reactive drift-triggered recalibration overlay  
**Estimated Effort**: 3-4 weeks (1 senior engineer)

---

## 1. Overview & Motivation

### Problem
- Local pricing models (Cambodia Smart Underwriting Engine) need fresh production data to stay calibrated
- Current setup has **two backends**: Live (`C:\DAC\dac-health\backend` on Render) and Local (`C:\DAC-UW-Agent`)
- Production system accumulates quote + claims data daily but local system runs on static synthetic calibration
- Models drift over time without exposure to real applicant profiles and claims outcomes

### Solution
**ETL Pipeline + Recalibration Engine**:
1. **Daily batch sync**: Pull live quote/claims data from Render PostgreSQL → Local SQLite dataset
2. **Validation layer**: Schema checks, outlier detection, audit logging
3. **Recalibration trigger**: Scheduled (nightly) + Reactive (when PSI drift detected)
4. **Data lineage**: Full audit trail linking each assumption version to source data + sync timestamp

### Success Criteria
- ✅ New quotes available locally <24h after production insertion
- ✅ Recalibration pipeline runs nightly (configurable)
- ✅ Models reject retraining if data quality checks fail
- ✅ Every assumption version versioned with data provenance (date, row count, data hash)
- ✅ Zero breaking changes to existing pricing logic
- ✅ Integrates with existing PSI Drift Monitor (reuses `/dashboard/stats` data)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ PRODUCTION SYSTEM (Render)                                  │
│ ├─ PostgreSQL: hp_quote_log (quotes, claims, premiums)      │
│ └─ API: /dashboard/stats, /cases/{id}/review endpoints      │
└──────────────────────┬──────────────────────────────────────┘
                       │ (nightly sync via HTTP/DB)
                       ↓
┌──────────────────────────────────────────────────────────────┐
│ LOCAL ETL SYSTEM (C:\DAC-UW-Agent)                           │
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ data/synced/                 ← SQLite datasets          │ │
│ │  ├─ quotes_YYYY-MM-DD.db                               │ │
│ │  ├─ claims_YYYY-MM-DD.db                               │ │
│ │  └─ etl_audit_log.json                                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                       ↓                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ etl/pipeline.py              ← Data validation          │ │
│ │  ├─ fetch_production_data()                             │ │
│ │  ├─ validate_schema()                                   │ │
│ │  ├─ detect_outliers()                                   │ │
│ │  └─ write_local_dataset()                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                       ↓                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ medical_reader/calibration.py ← Recalibration engine   │ │
│ │  ├─ load_local_claims()                                 │ │
│ │  ├─ compute_actuarial_lift()                            │ │
│ │  ├─ test_fairness()                                     │ │
│ │  └─ save_new_assumptions()                              │ │
│ └─────────────────────────────────────────────────────────┘ │
│                       ↓                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ medical_reader/pricing/assumptions_versions/            │ │
│ │  ├─ v3.0-cambodia-2026-04-14.json (current)             │ │
│ │  ├─ v3.1-cambodia-2026-04-15.json (new if retrain)      │ │
│ │  └─ VERSION_MANIFEST.json                               │ │
│ └─────────────────────────────────────────────────────────┘ │
│                       ↓                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ api/routers/calibration.py    ← API endpoints           │ │
│ │  ├─ GET /api/v1/calibration/status                      │ │
│ │  ├─ GET /api/v1/calibration/assumptions/{version}       │ │
│ │  ├─ POST /api/v1/calibration/sync (manual trigger)      │ │
│ │  └─ POST /api/v1/calibration/recalibrate (manual)       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                       ↓                                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ wiki/data/etl-lineage.md      ← Documentation           │ │
│ │  ├─ Data provenance (source → transform → output)       │ │
│ │  ├─ Version history with metadata                       │ │
│ │  └─ Audit trail of every sync & recalibration          │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Data Models & Flow

### 3.1 Production Data Source (Render PostgreSQL)

**Table: `hp_quote_log`** (existing)
```sql
CREATE TABLE hp_quote_log (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP,
    applicant_profile JSONB,                    -- {age, gender, BMI, conditions, ...}
    extracted_from JSONB,                       -- {province, occupation, healthcare_tier, ...}
    mortality_ratio NUMERIC,
    total_annual_premium NUMERIC,
    underwriting_status VARCHAR,                -- 'approved', 'declined', 'manual_review'
    manual_override BOOLEAN,
    override_reason TEXT
);
```

### 3.2 Local ETL Datasets

**File: `data/synced/quotes_YYYY-MM-DD.db`** (SQLite)
```sql
-- Same schema as hp_quote_log, plus metadata
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    applicant_profile TEXT,                     -- JSON string
    extracted_from TEXT,                        -- JSON string
    mortality_ratio REAL,
    total_annual_premium REAL,
    underwriting_status TEXT,
    manual_override BOOLEAN,
    override_reason TEXT,
    
    -- ETL metadata
    synced_at TEXT,                             -- Timestamp of local insertion
    source_hash TEXT,                           -- Hash of source data (for dedup)
    validation_status TEXT                      -- 'valid', 'outlier', 'quarantined'
);
```

**File: `data/synced/etl_audit_log.json`** (Append-only)
```json
[
  {
    "sync_id": "sync_2026-04-16_000000",
    "sync_start": "2026-04-16T00:00:00Z",
    "sync_end": "2026-04-16T00:05:23Z",
    "source": "https://dac-healthprice-api.onrender.com/dashboard/stats",
    "rows_fetched": 42,
    "rows_validated": 40,
    "rows_quarantined": 2,
    "data_hash": "sha256:abc123...",
    "status": "success",
    "error": null
  },
  ...
]
```

### 3.3 Assumptions Versioning

**File: `medical_reader/pricing/assumptions_versions/v3.0-cambodia-2026-04-14.json`**
```json
{
  "version": "v3.0-cambodia-2026-04-14",
  "created_at": "2026-04-14T18:00:00Z",
  "data_provenance": {
    "source": "synthetic bootstrap (2000 policies, seed=333)",
    "rows_used": 2000,
    "data_hash": "synthetic_seed_333",
    "sync_id": null
  },
  "parameters": {
    "cambodia_mortality_adjustment": 0.85,
    "occupational_multipliers": {
      "office": 1.0,
      "motorbike_courier": 1.45,
      "construction": 1.35
    },
    "endemic_disease_multipliers": {
      "phnom_penh": 1.0,
      "mondulkiri": 1.30
    },
    "healthcare_tier_discounts": {
      "tier_a": 0.97,
      "clinic": 1.05
    }
  },
  "validation": {
    "fairness_score": 0.86,
    "disparity_impact_ratio": 0.82,
    "status": "approved"
  }
}
```

**File: `medical_reader/pricing/assumptions_versions/VERSION_MANIFEST.json`**
```json
{
  "active_version": "v3.0-cambodia-2026-04-14",
  "versions": [
    {
      "version": "v3.0-cambodia-2026-04-14",
      "created_at": "2026-04-14T18:00:00Z",
      "status": "active",
      "reason": "Initial Cambodia calibration"
    },
    {
      "version": "v3.1-cambodia-2026-04-16",
      "created_at": "2026-04-16T23:15:00Z",
      "status": "candidate",
      "reason": "Recalibration from 42 production quotes",
      "parent_version": "v3.0-cambodia-2026-04-14"
    }
  ],
  "recalibration_log": [
    {
      "timestamp": "2026-04-16T23:00:00Z",
      "trigger": "scheduled_nightly",
      "data_rows_available": 42,
      "recalibration_status": "completed",
      "new_version": "v3.1-cambodia-2026-04-16",
      "notes": "Occupational multipliers refined: courier 1.45→1.38"
    }
  ]
}
```

---

## 4. Component Breakdown

### 4.1 ETL Pipeline (`etl/pipeline.py`)

**Responsibility**: Fetch → Validate → Store → Audit

```python
# File: etl/pipeline.py

class ProductionDataFetcher:
    """Retrieve quote/claims data from production Render API."""
    
    async def fetch_quotes(self, since: datetime) -> List[Dict]:
        """
        GET https://dac-healthprice-api.onrender.com/dashboard/stats
        Returns: List of hp_quote_log entries created since `since`
        
        Raises:
        - ConnectionError if API unreachable
        - ValueError if response format unexpected
        """
        
    async def fetch_claims(self, since: datetime) -> List[Dict]:
        """
        GET https://dac-healthprice-api.onrender.com/admin/claims
        (Note: May require new endpoint in production API)
        Returns: List of claim records (date, quote_id, claim_amount)
        """


class SchemaValidator:
    """Ensure incoming data matches expected structure."""
    
    def validate_quote(self, record: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate a single quote record:
        - Required fields present (age, BMI, mortality_ratio, premium)
        - Field types correct (numeric, string, bool)
        - Value ranges reasonable (age 0-150, BMI 10-60, premium > 0)
        
        Returns: (is_valid, error_message)
        """
    
    def validate_claim(self, record: Dict) -> Tuple[bool, Optional[str]]:
        """Validate claim record (date, quote_id, amount, status)."""


class OutlierDetector:
    """Identify suspicious data points that might skew calibration."""
    
    def detect_outliers(self, quotes: List[Dict]) -> List[int]:
        """
        Flags quotes where:
        - Premium > 10× median for that age/occupation (potential data entry error)
        - Mortality ratio inconsistent with profile (age mismatch?)
        - High-risk flags present but low premium (underpricing issue)
        
        Returns: List of indices to quarantine
        """


class LocalDatasetWriter:
    """Store validated data in local SQLite dataset."""
    
    def write_quotes(self, quotes: List[Dict], sync_id: str) -> int:
        """
        Insert into data/synced/quotes_YYYY-MM-DD.db
        - Skip duplicates (check source_hash)
        - Mark validation status (valid/quarantined)
        - Stamp synced_at timestamp
        
        Returns: Number of rows inserted
        """
    
    def write_audit_log(self, sync_id: str, stats: Dict) -> None:
        """Append entry to data/synced/etl_audit_log.json"""


class ETLPipeline:
    """Orchestrate entire sync process."""
    
    async def run_sync(self) -> Dict:
        """
        1. Fetch production data (since last sync)
        2. Validate schema
        3. Detect outliers → quarantine
        4. Write to local SQLite
        5. Log audit entry
        6. Return sync_id + stats
        
        Returns: {
            "sync_id": "sync_2026-04-16_000000",
            "status": "success|failed",
            "rows_fetched": 42,
            "rows_validated": 40,
            "rows_quarantined": 2,
            "error": null|str,
            "data_hash": "sha256:..."
        }
        """
```

**Integration Points**:
- ✅ Read: Render API (`https://dac-healthprice-api.onrender.com/dashboard/stats`)
- ✅ Write: Local SQLite (`data/synced/quotes_YYYY-MM-DD.db`)
- ✅ Log: ETL audit log (`data/synced/etl_audit_log.json`)

---

### 4.2 Recalibration Engine (`medical_reader/calibration.py`)

**Responsibility**: Load local data → Compute new multipliers → Test fairness → Save versioned assumptions

```python
# File: medical_reader/calibration.py

class LocalClaimsDataLoader:
    """Load validated quotes from local SQLite dataset."""
    
    def load_quotes(self, days_back: int = 90) -> List[Dict]:
        """
        Load all valid quotes from past N days.
        Filters:
        - validation_status == 'valid'
        - exclude quarantined/outlier records
        - return applicant_profile + mortality_ratio + premium
        
        Returns: DataFrame-like list of {age, occupation, province, ..., mortality_ratio, premium}
        """
    
    def load_claims(self, days_back: int = 90) -> List[Dict]:
        """Load actual claim outcomes (if available)."""


class ActuarialLiftCalculator:
    """Compute new risk multipliers from live data."""
    
    def compute_occupational_lift(self, quotes: List[Dict]) -> Dict[str, float]:
        """
        Groupby occupation_type → compute A/E ratio (Actual mortality / Expected mortality)
        Current: motorbike_courier 1.45× baseline
        From data: observed ratio 1.38× → New multiplier: 1.38
        
        Returns: {occupation: new_multiplier, ...}
        
        Guardrails:
        - Don't change by >20% (avoid overtraining on 40 samples)
        - Minimum sample size per occupation (n >= 5)
        - Cap adjustments at [0.75, 1.50] per assumptions
        """
    
    def compute_regional_lift(self, quotes: List[Dict]) -> Dict[str, float]:
        """
        Groupby province → compute endemic disease multiplier
        E.g., Mondulkiri: observed 1.25× (vs assumed 1.30×) → suggest adjustment
        """
    
    def compute_healthcare_tier_lift(self, quotes: List[Dict]) -> Dict[str, float]:
        """
        Groupby healthcare_tier → compute reliability discount
        E.g., TierA: 97% premium accuracy (high exam quality) → keep 0.97×
        """


class FairnessValidator:
    """Ensure new multipliers don't create unfair disparities."""
    
    def test_disparity_impact(self, quotes: List[Dict], new_multipliers: Dict) -> Dict:
        """
        Compute disparate impact ratio (Cambodia Prakas 093 requirement):
        - Approval rate for protected attribute (gender, occupation) vs baseline
        - Ratio < 0.80 → flags as potential discrimination
        
        Returns: {
            "metric": "disparate_impact_ratio",
            "value": 0.82,
            "status": "pass|warn|fail",
            "notes": "Female applicants approved 82% as often as males (threshold 80%)"
        }
        """
    
    def test_factor_importance(self, quotes: List[Dict]) -> Dict:
        """
        SHAP-style importance: which factors drive premium variance?
        Ensures no single factor dominates (early warning for overtraining)
        """


class AssumptionsVersionManager:
    """Create + persist new assumption versions."""
    
    def create_new_version(self, 
                          parent_version: str,
                          occupational_lift: Dict,
                          regional_lift: Dict,
                          fairness_report: Dict,
                          sync_id: str) -> str:
        """
        Build v3.1-cambodia-2026-04-16.json:
        - Merge parent version + new lifts
        - Stamp data_provenance (sync_id, row count, data hash)
        - Include fairness validation results
        - Write to medical_reader/pricing/assumptions_versions/
        
        Returns: new_version_id (e.g., "v3.1-cambodia-2026-04-16")
        """
    
    def promote_version(self, version_id: str) -> None:
        """Update VERSION_MANIFEST.json: active_version = version_id"""
    
    def rollback_version(self, version_id: str) -> None:
        """Revert to previous version (safety valve if new version breaks pricing)"""


class RecalibrationEngine:
    """Orchestrate entire recalibration process."""
    
    def run_recalibration(self, trigger: str = "scheduled") -> Dict:
        """
        1. Load local validated quotes (90-day rolling window)
        2. Compute occupational/regional/healthcare lifts
        3. Run fairness validation
        4. Create new assumption version
        5. Return report
        
        Args:
            trigger: "scheduled" (nightly) | "drift_detected" (PSI > 0.10) | "manual"
        
        Returns: {
            "status": "completed|failed|skipped",
            "reason": "insufficient_data|fairness_fail|no_lift_detected",
            "new_version": "v3.1-cambodia-2026-04-16" | null,
            "changes": {"occupational_multipliers": {...}, ...},
            "fairness_report": {...}
        }
        
        Guardrails (prevent bad versions):
        - Skip if < 30 valid quotes available
        - Fail if fairness_report.status == "fail"
        - Warn if lift > 20% (investigate before promoting)
        """
```

**Integration Points**:
- ✅ Read: Local SQLite (`data/synced/quotes_*.db`)
- ✅ Read: Current assumptions (`medical_reader/pricing/assumptions_versions/v3.0-...json`)
- ✅ Write: New assumptions (`medical_reader/pricing/assumptions_versions/v3.1-...json`)
- ✅ Write: Version manifest (`medical_reader/pricing/assumptions_versions/VERSION_MANIFEST.json`)

---

### 4.3 Recalibration Trigger (`etl/scheduler.py`)

**Responsibility**: Schedule nightly syncs + Listen for drift signals

```python
# File: etl/scheduler.py

class RecalibrationScheduler:
    """Manage nightly sync + recalibration jobs."""
    
    def __init__(self, etl_pipeline, calibration_engine):
        self.etl = etl_pipeline
        self.calibration = calibration_engine
        
        # Nightly job: 11 PM local time (12 hour after Render data updates)
        self.schedule_job(
            name="nightly_sync_and_recalibrate",
            cron="0 23 * * *",  # 11 PM every day
            job_fn=self.nightly_sync_and_recalibrate
        )
    
    async def nightly_sync_and_recalibrate(self) -> None:
        """
        1. Run ETL sync (fetch from Render)
        2. Check if sufficient new data (>= 20 quotes) accumulated
        3. If yes: trigger recalibration
        4. Log results
        """
        
        sync_result = await self.etl.run_sync()
        if sync_result["status"] != "success":
            logger.error(f"ETL sync failed: {sync_result['error']}")
            return
        
        if sync_result["rows_validated"] < 20:
            logger.info(f"Only {sync_result['rows_validated']} quotes; skipping recalibration")
            return
        
        calib_result = self.calibration.run_recalibration(trigger="scheduled")
        logger.info(f"Recalibration completed: {calib_result}")
    
    def on_drift_detected(self, drift_signal: Dict) -> None:
        """
        Callback triggered by `/dashboard/stats` endpoint when PSI > 0.25 (drift threshold).
        
        Decoupled from nightly schedule:
        - If PSI spike detected (e.g., new high-risk cohort), retrain immediately
        - Prevents models operating on stale assumptions for long
        """
        logger.warning(f"Drift detected: {drift_signal}")
        calib_result = self.calibration.run_recalibration(trigger="drift_detected")
        logger.info(f"Emergency recalibration: {calib_result}")
```

**Integration Points**:
- ✅ Trigger: Scheduled via APScheduler or Celery Beat
- ✅ Callback: Wired into `/dashboard/stats` (PSI check)

---

### 4.4 API Endpoints (`api/routers/calibration.py`)

**Responsibility**: Expose ETL/recalibration operations to frontend + admin interfaces

```python
# File: api/routers/calibration.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/calibration")

# ========== DATA MODELS ==========

class SyncStatusResponse(BaseModel):
    sync_id: str
    status: str                    # "success" | "failed"
    rows_fetched: int
    rows_validated: int
    rows_quarantined: int
    last_sync: str                 # ISO timestamp
    next_sync: str                 # ISO timestamp (scheduled time)
    error: Optional[str]

class RecalibrationStatusResponse(BaseModel):
    latest_sync_id: str
    current_version: str           # "v3.0-cambodia-2026-04-14"
    candidate_version: Optional[str]  # "v3.1-..." if recalibration pending approval
    last_recalibration: str        # ISO timestamp
    next_scheduled_recalibration: str
    recalibration_status: str      # "idle" | "running" | "completed" | "failed"

class AssumptionsResponse(BaseModel):
    version: str
    created_at: str
    data_provenance: Dict          # source, rows_used, data_hash, sync_id
    parameters: Dict               # occupational_multipliers, etc.
    validation: Dict               # fairness_score, disparate_impact_ratio, status

# ========== ENDPOINTS ==========

@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """
    GET /api/v1/calibration/status
    
    Returns current ETL sync status:
    - When was last sync? Success or failed?
    - How many quotes have we ingested?
    - When is next sync scheduled?
    """

@router.post("/sync", response_model=SyncStatusResponse)
async def trigger_manual_sync():
    """
    POST /api/v1/calibration/sync
    
    Manually trigger a sync (for testing, or if admin wants to retrain today).
    Returns sync result.
    """

@router.get("/recalibration/status", response_model=RecalibrationStatusResponse)
async def get_recalibration_status():
    """
    GET /api/v1/calibration/recalibration/status
    
    Returns current recalibration state:
    - Active version (e.g., "v3.0-cambodia-2026-04-14")
    - Candidate version pending approval (if recalibration recently completed)
    - When was last recalibration? Scheduled for when next?
    """

@router.post("/recalibrate")
async def trigger_manual_recalibration():
    """
    POST /api/v1/calibration/recalibrate
    
    Manually trigger recalibration (for testing, or admin wants to retrain based on recent sync).
    Runs fairness validation + returns report.
    """

@router.get("/assumptions/{version}", response_model=AssumptionsResponse)
async def get_assumptions(version: str):
    """
    GET /api/v1/calibration/assumptions/v3.0-cambodia-2026-04-14
    
    Returns full assumption set for a specific version:
    - Occupational multipliers
    - Regional multipliers
    - Healthcare tier discounts
    - Data provenance + fairness validation
    """

@router.get("/assumptions/active", response_model=AssumptionsResponse)
async def get_active_assumptions():
    """GET /api/v1/calibration/assumptions/active
    
    Returns the currently active assumption version."""

@router.get("/assumptions/versions")
async def list_assumption_versions():
    """
    GET /api/v1/calibration/assumptions/versions
    
    Returns VERSION_MANIFEST.json:
    - Active version
    - All historical versions + metadata
    - Recalibration log
    """

@router.post("/promote/{version}")
async def promote_version(version: str):
    """
    POST /api/v1/calibration/promote/v3.1-cambodia-2026-04-16
    
    Promote candidate version to active (requires fairness validation already passed).
    Admin-only endpoint.
    """

@router.post("/rollback/{version}")
async def rollback_version(version: str):
    """
    POST /api/v1/calibration/rollback/v3.0-cambodia-2026-04-14
    
    Emergency rollback to previous version (if new version breaks pricing).
    Admin-only endpoint.
    """

@router.get("/lineage")
async def get_data_lineage():
    """
    GET /api/v1/calibration/lineage
    
    Returns wiki/data/etl-lineage.md as structured data:
    - Full audit trail of every sync + recalibration
    - Data provenance (which assumptions came from which data)
    - Version history
    """
```

**Integration Points**:
- ✅ Call: ETL pipeline (trigger sync)
- ✅ Call: Recalibration engine (trigger retrain)
- ✅ Read: VERSION_MANIFEST.json
- ✅ Write: VERSION_MANIFEST.json (on promote/rollback)

---

## 5. Data Lineage & Documentation

### 5.1 Lineage Document (`wiki/data/etl-lineage.md`)

**Purpose**: Answer "Why does v3.1 have these multipliers?" in auditable terms

```markdown
# ETL Data Lineage & Assumption Versioning

## Version: v3.1-cambodia-2026-04-16

### Data Provenance
- **Source**: Render PostgreSQL `hp_quote_log` (production)
- **Sync ID**: `sync_2026-04-16_000000`
- **Sync Date**: 2026-04-16 00:05:23 UTC
- **Rows Fetched**: 42 quotes
- **Rows Validated**: 40 (2 quarantined as outliers)
- **Data Hash**: sha256:abc123def456...
- **Parent Version**: v3.0-cambodia-2026-04-14

### Changes from Parent
| Factor | Old (v3.0) | New (v3.1) | Δ | Reason |
|--------|-----------|-----------|---|--------|
| Motorbike Courier Multiplier | 1.45 | 1.38 | -4.8% | 8/8 couriers in data had lower-than-expected mortality |
| Mondulkiri Endemic | 1.30 | 1.25 | -3.8% | 2 quotes from Mondulkiri, both low-risk profiles |
| TierA Healthcare Discount | 0.97 | 0.97 | — | No change (stable signal) |

### Fairness Validation (v3.1)
- **Disparate Impact Ratio**: 0.84 (✅ Pass; >= 0.80 threshold)
- **Gender**: Female approval rate 88%, Male 88% (✅ Parity)
- **Occupation**: Healthcare worker approval rate 91%, Construction 85% (⚠️ Flag for review, but likely due to genuine occupational risk)
- **Province**: Phnom Penh 90%, Rural 85% (✅ Within tolerance; reflects healthcare access)

### Recalibration Metadata
- **Triggered**: 2026-04-16 23:00:00 UTC (scheduled nightly)
- **Reason**: Sufficient data accumulated (40 valid quotes)
- **Status**: ✅ Completed + Fairness Approved
- **Duration**: 2m 15s

### How to Use This Version
1. Update `medical_reader/pricing/assumptions_versions/v3.0-cambodia-2026-04-14.json` → `v3.1-cambodia-2026-04-16.json`
2. Update `VERSION_MANIFEST.json`: active_version = "v3.1-cambodia-2026-04-16"
3. All future quotes use new multipliers automatically
4. Audit trail: Every quote references its assumption version in `audit_trail`

### Audit Trail
```
[2026-04-16 23:00:15] etl/sync_completed (confidence: 1.0)
  sync_id: "sync_2026-04-16_000000"
  rows_validated: 40
[2026-04-16 23:02:30] calibration/recalibration_started (confidence: 1.0)
  parent_version: "v3.0-cambodia-2026-04-14"
  data_hash: "sha256:abc123..."
[2026-04-16 23:04:45] calibration/occupational_lift_computed (confidence: 0.88)
  motorbike_courier: 1.38 (was 1.45, n=8)
[2026-04-16 23:05:00] calibration/fairness_validated (confidence: 0.95)
  status: "pass"
[2026-04-16 23:05:15] calibration/version_created (confidence: 1.0)
  version_id: "v3.1-cambodia-2026-04-16"
```
```

**Updated on every recalibration event.**

---

## 6. Integration with Existing Stack

### 6.1 Local System Files Structure

```
C:\DAC-UW-Agent\
├── etl/                                  ← NEW
│   ├── __init__.py
│   ├── pipeline.py                       ← ETL orchestration
│   ├── scheduler.py                      ← Nightly jobs + drift listener
│   ├── fetch.py                          ← Render API client
│   ├── validate.py                       ← Schema + outlier checks
│   └── storage.py                        ← SQLite write logic
│
├── medical_reader/
│   ├── calibration.py                    ← NEW: Recalibration engine
│   ├── pricing/
│   │   ├── assumptions_versions/         ← NEW: Version storage
│   │   │   ├── v3.0-cambodia-2026-04-14.json
│   │   │   ├── v3.1-cambodia-2026-04-16.json
│   │   │   └── VERSION_MANIFEST.json
│   │   └── calculator.py                 ← UNCHANGED: Uses active version
│   └── ...
│
├── api/
│   ├── routers/
│   │   ├── calibration.py                ← NEW: Calibration endpoints
│   │   └── ...
│   └── main.py                           ← Wire in calibration router
│
├── data/
│   └── synced/                           ← NEW: Local datasets
│       ├── quotes_2026-04-16.db
│       ├── quotes_2026-04-15.db
│       └── etl_audit_log.json
│
├── wiki/
│   └── data/
│       └── etl-lineage.md                ← NEW: Lineage documentation
│
└── requirements-api.txt                  ← Add: httpx, APScheduler, sqlite3
```

### 6.2 Existing File Changes

**File: `api/main.py`**
```python
# Add at top
from api.routers import calibration

# Add in app.include_router section
app.include_router(calibration.router)

# Add startup event to launch scheduler
@app.on_event("startup")
async def startup_scheduler():
    from etl.scheduler import RecalibrationScheduler
    from etl.pipeline import ETLPipeline
    from medical_reader.calibration import RecalibrationEngine
    
    etl = ETLPipeline()
    calib = RecalibrationEngine()
    scheduler = RecalibrationScheduler(etl, calib)
    scheduler.start()  # Starts nightly jobs
```

**File: `medical_reader/pricing/calculator.py`** (UNCHANGED)
```python
# Existing calculator already loads active assumptions:
from medical_reader.pricing.assumptions_versions import load_active_assumptions

def calculate_annual_premium(profile, assumptions=None):
    if assumptions is None:
        assumptions = load_active_assumptions()  # Loads from VERSION_MANIFEST
    # ... rest of logic unchanged
```

**No breaking changes** — versioning system is transparent to existing code.

---

## 7. Success Criteria & Testing

### 7.1 Unit Tests (`tests/test_etl_pipeline.py`)

```python
def test_schema_validation():
    """Valid quote passes; invalid quote fails."""

def test_outlier_detection():
    """Premium > 10× median is flagged."""

def test_duplicate_prevention():
    """Same source_hash not inserted twice."""

def test_occupational_lift_calculation():
    """Given motorbike couriers: 8 cases, A/E=1.38, expects lift to 1.38."""

def test_fairness_validation_pass():
    """Disparate impact ratio >= 0.80 → status='pass'."""

def test_fairness_validation_fail():
    """DI ratio < 0.80 → status='fail'; recalibration rejected."""

def test_version_creation():
    """New version JSON is well-formed; stamped with sync_id."""

def test_assumptions_loading():
    """Load active assumptions; multipliers applied to pricing."""
```

### 7.2 Integration Test (`tests/test_etl_integration.py`)

```python
async def test_full_sync_and_recalibration():
    """
    Mock production API → 50 quotes → sync → validate → write → 
    load into recalibration → compute lifts → fairness check → 
    new version created → promote → verify pricing uses new multipliers.
    """
```

### 7.3 Acceptance Criteria

- ✅ Nightly sync runs at 11 PM; fetches new quotes
- ✅ Outliers quarantined; valid quotes stored locally
- ✅ Recalibration triggers if >= 20 new valid quotes
- ✅ Fairness validation blocks bad versions
- ✅ VERSION_MANIFEST updated on each recalibration
- ✅ `/api/v1/calibration/status` returns accurate sync/recalibration state
- ✅ Wiki lineage document auto-updated with each version
- ✅ PSI Drift Monitor can query assumption version history (for audit)
- ✅ Zero impact on existing pricing logic (backward compatible)

---

## 8. Deployment & Rollout

### Phase 1: Core ETL (Week 1–2)
1. Implement `etl/pipeline.py` (fetch, validate, store)
2. Implement `etl/storage.py` (SQLite dataset writer)
3. Test with mock production data
4. **Deliverable**: Local dataset populated daily

### Phase 2: Recalibration Engine (Week 2–3)
1. Implement `medical_reader/calibration.py` (lifts, fairness, versioning)
2. Implement `etl/scheduler.py` (nightly job)
3. Test recalibration on local dataset
4. **Deliverable**: New assumption versions created nightly

### Phase 3: API & Integration (Week 3–4)
1. Implement `api/routers/calibration.py` (6 endpoints)
2. Wire scheduler into FastAPI startup
3. Update `medical_reader/pricing/calculator.py` to load active version
4. **Deliverable**: API endpoints live; pricing uses latest assumptions

### Phase 4: Documentation (Week 4)
1. Auto-generate lineage document (`wiki/data/etl-lineage.md`)
2. Wire drift monitor callback to `on_drift_detected()`
3. **Deliverable**: Full audit trail + lineage documentation

---

## 9. Configuration & Environment

### Environment Variables
```
# .env
PRODUCTION_API_URL=https://dac-healthprice-api.onrender.com
PRODUCTION_API_KEY=<admin_api_key>  # Needs to be set up in production

SYNC_SCHEDULE_CRON=0 23 * * *  # 11 PM daily
RECALIBRATION_MIN_QUOTES=20    # Minimum valid quotes before retraining
RECALIBRATION_MAX_CHANGE_PCT=20  # Max % change per multiplier (guardrail)

LOCAL_DATASET_PATH=data/synced/
ASSUMPTIONS_PATH=medical_reader/pricing/assumptions_versions/
```

### Dependencies
```
# requirements-api.txt (add these)
httpx>=0.25.0          # Async HTTP client for production API
APScheduler>=3.10.0    # Scheduled jobs
sqlite3                # Built-in; included
```

---

## 10. Open Questions for Opus

**Before starting**, clarify with user:

1. **Production API Authentication**: How to securely pass credentials to fetch from Render?
   - API key in `.env`?
   - OAuth token from GitHub?
   - Database connection string directly?

2. **Render PostgreSQL Access**: Can local system connect directly to production DB, or only via API?
   - If DB direct: Use `psycopg2` to query `hp_quote_log` directly
   - If API only: Implement new `/admin/etl` endpoint in production backend

3. **Claims Data Availability**: Do you have actual claims outcomes yet, or only quotes?
   - If quotes only: Recalibration based on quote patterns (observed premium spread)
   - If claims available: Can compute actual A/E (Actual deaths / Expected deaths)

4. **Drift Monitoring**: Should `/dashboard/stats` endpoint trigger `on_drift_detected()` automatically?
   - If PSI > 0.25, immediately retrain?
   - Or just flag & let admin decide?

5. **Version Promotion**: Should new versions auto-promote to active, or require admin approval?
   - Auto-promote if fairness passes?
   - Or always require admin click on `/promote/{version}`?

---

## Summary

This design provides:
- ✅ **Periodic batch sync** (daily) with validation & audit logging
- ✅ **Recalibration engine** that computes new multipliers from live data
- ✅ **Fairness guardrails** (prevents bad versions from going live)
- ✅ **Version control** (full lineage, rollback capability)
- ✅ **Zero breaking changes** (transparent to existing pricing logic)
- ✅ **Scalable from MVP**: Start with simple periodic sync; add reactive drift-triggered retraining later

**Ready for Opus to implement end-to-end.**

---

**Questions?** Reach out to discuss Phase 1 kickoff or clarify any unknowns above.
