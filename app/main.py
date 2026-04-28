"""
DAC HealthPrice Platform v2.3
Changes: authoritative underwriting engine, GLM-consistent fallback,
model versioning + meta persistence, hot-swap retraining loop,
full audit trail, 6-layer anti-scraping protection,
client-specific partner API keys.
"""
import os, re, time, uuid, logging, json, hashlib, secrets, subprocess, tempfile, base64
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from typing import Optional, List
from types import SimpleNamespace
import httpx
from collections import defaultdict, deque
import numpy as np
import jwt as pyjwt
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator, model_validator
import asyncpg

logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"),format="%(asctime)s | %(levelname)-7s | %(message)s",datefmt="%H:%M:%S")
log = logging.getLogger("hp")

def _parse_db_url(url):
    if not url: return {}
    url=url.strip()
    b=re.sub(r'^postgresql(\+\w+)?://','',url)
    b=re.sub(r'^postgres://','',b)
    m=re.match(r'^([^:]+):(.+)@([^:/@]+):(\d+)/(.+)$',b)
    if m: return {"user":m[1],"password":m[2],"host":m[3],"port":int(m[4]),"database":m[5]}
    m=re.match(r'^([^:]+):(.+)@([^:/@]+)/(.+)$',b)
    if m: return {"user":m[1],"password":m[2],"host":m[3],"port":5432,"database":m[4]}
    return {}

_db_p=_parse_db_url(os.getenv("DATABASE_URL",""))
MODEL_DIR=os.getenv("MODEL_DIR","models")
ALLOWED_ORIGINS=os.getenv("ALLOWED_ORIGINS","*").split(",")
db_pool=None; models={}; model_version="v1.0.0"
model_meta={"version":"v1.0.0","last_retrained_at":None,"training_dataset":None,"coverage":None,"r2":None}
_partner_keys: dict={}  # key_hash → {partner_name, daily_limit, is_active, usage_today, date}
_prospect_coeffs: dict={}  # prospect_id → custom COEFF dict loaded from models/custom/

# ── Anti-scraping protection ──────────────────────────────────────────────────
DAILY_LIMIT=int(os.getenv("DAILY_QUOTE_LIMIT","15"))
SESSION_QUOTE_LIMIT=int(os.getenv("SESSION_QUOTE_LIMIT","10"))
SWEEP_THRESHOLD=int(os.getenv("SWEEP_THRESHOLD","5"))
_sessions: dict={}
_daily_quotes: dict=defaultdict(lambda:{"date":None,"count":0})
_probe_buffer: dict=defaultdict(lambda:deque(maxlen=20))
SWEEP_FIELDS=["age","gender","smoking_status","exercise_frequency","occupation_type","ipd_tier"]

# Rate limiter (per-IP, per-minute token bucket)
_buckets=defaultdict(lambda:{"t":30,"last":time.monotonic()})
RL=int(os.getenv("RATE_LIMIT_PER_MIN","30"))
def _rl(ip):
    now=time.monotonic();b=_buckets[ip];b["t"]=min(RL,b["t"]+(now-b["last"])*(RL/60));b["last"]=now
    if b["t"]>=1: b["t"]-=1; return True
    return False

# ── JWT Staff Auth ────────────────────────────────────────────────────────────
JWT_SECRET  = os.getenv("JWT_SECRET", "dac-dev-secret-change-in-production")
JWT_ALGO    = "HS256"
JWT_EXP_HRS = 8

STAFF_USERS = {
    "admin":   {"password": os.getenv("STAFF_ADMIN_PASS",   "dac2026!"), "role": "admin"},
    "radet":   {"password": os.getenv("STAFF_RADET_PASS",   "dac2026!"), "role": "underwriter"},
    "analyst": {"password": os.getenv("STAFF_ANALYST_PASS", "dac2026!"), "role": "analyst"},
}

_bearer = HTTPBearer(auto_error=False)

async def get_current_staff(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)):
    if not creds:
        raise HTTPException(401, "Authentication required")
    try:
        payload = pyjwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    return {"username": payload["sub"], "role": payload["role"]}

def require_roles(*roles):
    async def _check(user: dict = Depends(get_current_staff)):
        if user["role"] not in roles:
            raise HTTPException(403, f"Role '{user['role']}' cannot perform this action")
        return user
    return _check

VALID_GENDERS=["Male","Female","Other"]
VALID_SMOKING=["Never","Former","Current"]
VALID_EXERCISE=["Sedentary","Light","Moderate","Active"]
VALID_OCC=["Office/Desk","Retail/Service","Healthcare","Manual Labor","Industrial/High-Risk","Retired"]
VALID_PE=frozenset(["None","Hypertension","Diabetes","Heart Disease","Asthma/COPD","Cancer (remission)","Kidney Disease","Liver Disease","Obesity","Mental Health"])
VALID_ALCOHOL=["Never","Occasional","Regular","Heavy"]
VALID_DIET=["Healthy","Balanced","High Processed"]
VALID_SLEEP=["Good (7-9h)","Fair (5-7h)","Poor (<5h)"]
VALID_STRESS=["Low","Moderate","High"]
VALID_MOTORBIKE=["No","Never","Occasional","Daily"]
VALID_WATER=["Piped/Safe","Well/Mixed","Limited"]
VALID_PROXIMITY=["<5km","5-20km",">20km"]
VALID_MARITAL=["Single","Married","Divorced","Widowed"]
CTY_REG={"cambodia":{"Phnom Penh","Siem Reap","Battambang","Sihanoukville","Kampong Cham","Rural Areas"},"vietnam":{"Ho Chi Minh City","Hanoi","Da Nang","Can Tho","Hai Phong","Rural Areas"}}
CTY_REG_L={"cambodia":["Phnom Penh","Siem Reap","Battambang","Sihanoukville","Kampong Cham","Rural Areas"],"vietnam":["Ho Chi Minh City","Hanoi","Da Nang","Can Tho","Hai Phong","Rural Areas"]}
REG_F={"Phnom Penh":1.20,"Siem Reap":1.05,"Battambang":0.90,"Sihanoukville":1.10,"Kampong Cham":0.85,"Ho Chi Minh City":1.25,"Hanoi":1.20,"Da Nang":1.05,"Can Tho":0.90,"Hai Phong":0.95,"Rural Areas":0.75}
G_ENC={"Male":0,"Female":1,"Other":2}
S_ENC={"Never":0,"Former":1,"Current":2}
E_ENC={"Sedentary":0,"Light":1,"Moderate":2,"Active":3}
O_ENC={"Office/Desk":0,"Retail/Service":1,"Healthcare":2,"Manual Labor":3,"Industrial/High-Risk":4,"Retired":5}
R_ENC={r:i for i,r in enumerate(["Phnom Penh","Siem Reap","Battambang","Sihanoukville","Kampong Cham","Rural Areas","Ho Chi Minh City","Hanoi","Da Nang","Can Tho","Hai Phong"])}
COV={"ipd":{"name":"IPD Hospital Reimbursement","core":True,"load":0.30},"opd":{"name":"OPD Rider","core":False,"load":0.25},"dental":{"name":"Dental Rider","core":False,"load":0.20},"maternity":{"name":"Maternity Rider","core":False,"load":0.25}}
TIERS={"Bronze":{"annual_limit":15000,"room":"General Ward","surgery_limit":5000,"icu_days":3,"deductible":500},"Silver":{"annual_limit":40000,"room":"Semi-Private","surgery_limit":15000,"icu_days":7,"deductible":250},"Gold":{"annual_limit":80000,"room":"Private Room","surgery_limit":40000,"icu_days":14,"deductible":100},"Platinum":{"annual_limit":150000,"room":"Private Suite","surgery_limit":80000,"icu_days":30,"deductible":0}}
T_F={"Bronze":0.70,"Silver":1.00,"Gold":1.45,"Platinum":2.10}
LOAD_FACTOR=0.30
P_FLOOR=50; P_CEIL=25000

# ── Fallback GLM fitting — consistent Poisson+Ridge methodology ───────────────
# GLM Coefficient Store — all pricing factors are explicit and auditable.
COEFF: dict = {
    "version":       "v2.3",
    "last_updated":  "2026-04-03",
    "updated_by":    "system",
    "base_freq":  {"ipd": 0.12,  "opd": 2.5,  "dental": 0.80, "maternity": 0.15},
    "base_sev":   {"ipd": 2500,  "opd": 60,   "dental": 120,  "maternity": 3500},
    "age_factors":        {"18-24": 0.85, "25-34": 1.00, "35-44": 1.12, "45-54": 1.28, "55-64": 1.48, "65+": 1.72},
    "smoking_factors":    {"Never": 1.00, "Former": 1.15, "Current": 1.40},
    "exercise_factors":   {"Sedentary": 1.20, "Light": 1.05, "Moderate": 0.90, "Active": 0.80},
    "occupation_factors": {"Office/Desk": 0.85, "Retail/Service": 1.00, "Healthcare": 1.05, "Manual Labor": 1.15, "Industrial/High-Risk": 1.30, "Retired": 1.10},
    "region_factors":     {"Phnom Penh": 1.20, "Siem Reap": 1.05, "Battambang": 0.90, "Sihanoukville": 1.10, "Kampong Cham": 0.85, "Ho Chi Minh City": 1.25, "Hanoi": 1.20, "Da Nang": 1.05, "Can Tho": 0.90, "Hai Phong": 0.95, "Rural Areas": 0.75},
    "preexist_per_condition": 0.20,
    "sev_age_gradient": 0.006,
    "family_per_dep":   0.65,
    # ── Extended lifestyle & clinical factors (v2.3) ──────────────────────────
    "bmi_factors":      {"Underweight": 1.10, "Normal": 1.00, "Overweight": 1.15, "Obese": 1.35},
    "alcohol_factors":  {"Never": 1.00, "Occasional": 1.05, "Regular": 1.20, "Heavy": 1.45},
    "hosp_factors":     {0: 1.00, 1: 1.25, 2: 1.50, 3: 1.80},   # 3 = "3 or more"
    "med_factors":      {0: 1.00, 1: 1.15, 2: 1.15, 3: 1.30, 4: 1.30, 5: 1.50},  # 5 = "5+"
    "fh_per_condition": 0.10,
    "marital_factors":  {"Single": 1.05, "Married": 1.00, "Divorced": 1.08, "Widowed": 1.08},
    "diet_factors":     {"Healthy": 0.90, "Balanced": 1.00, "High Processed": 1.15},
    "sleep_factors":    {"Good (7-9h)": 1.00, "Fair (5-7h)": 1.10, "Poor (<5h)": 1.25},
    "stress_factors":   {"Low": 1.00, "Moderate": 1.10, "High": 1.25},
    "motorbike_factors":{"No": 1.00, "Never": 1.00, "Occasional": 1.05, "Daily": 1.15},
    "water_factors":    {"Piped/Safe": 1.00, "Well/Mixed": 1.08, "Limited": 1.18},
    "proximity_factors":{"<5km": 1.00, "5-20km": 1.05, ">20km": 1.12},  # severity multiplier
}

def _age_band(age: int) -> str:
    if age < 25: return "18-24"
    if age < 35: return "25-34"
    if age < 45: return "35-44"
    if age < 55: return "45-54"
    if age < 65: return "55-64"
    return "65+"

def _bmi_cat(height_cm, weight_kg) -> str:
    if not height_cm or not weight_kg: return "Normal"
    bmi = weight_kg / (height_cm / 100) ** 2
    if bmi < 18.5: return "Underweight"
    if bmi < 25:   return "Normal"
    if bmi < 30:   return "Overweight"
    return "Obese"

def _extended_factors(req, coeff: dict) -> tuple:
    """Compute the 10 extended lifestyle/clinical frequency multipliers and 1 severity multiplier.
    Returns (freq_mult, sev_mult, breakdown_entries).
    All factors default to 1.0 when the field is absent."""
    # BMI
    bmi_cat = _bmi_cat(getattr(req, "bmi_height", None), getattr(req, "bmi_weight", None))
    bmif = coeff.get("bmi_factors", {}).get(bmi_cat, 1.0)

    # Alcohol
    alcohol = getattr(req, "alcohol", None) or "Never"
    alf = coeff.get("alcohol_factors", {}).get(alcohol, 1.0)

    # Prior hospitalisations
    hosp = getattr(req, "prev_hospitalizations", None)
    hosp = int(hosp) if hosp is not None else 0
    hosp_key = min(hosp, 3)
    hospf = coeff.get("hosp_factors", {}).get(hosp_key, 1.0)

    # Medications
    meds = getattr(req, "medications_count", None)
    meds = int(meds) if meds is not None else 0
    med_key = min(meds, 5)
    medf = coeff.get("med_factors", {}).get(med_key, 1.0)

    # Family history (each non-None item adds fh_per_condition)
    fh = getattr(req, "family_history", None) or []
    fh_count = len([x for x in fh if x and x != "None"])
    fhf = 1.0 + fh_count * coeff.get("fh_per_condition", 0.10)

    # Marital status
    marital = getattr(req, "marital_status", None) or "Single"
    mrf = coeff.get("marital_factors", {}).get(marital, 1.0)

    # Diet
    diet = getattr(req, "diet", None) or "Balanced"
    df = coeff.get("diet_factors", {}).get(diet, 1.0)

    # Sleep quality
    sleep = getattr(req, "sleep_quality", None) or "Good (7-9h)"
    slf = coeff.get("sleep_factors", {}).get(sleep, 1.0)

    # Stress level
    stress = getattr(req, "stress_level", None) or "Low"
    stf = coeff.get("stress_factors", {}).get(stress, 1.0)

    # Motorbike usage
    motorbike = getattr(req, "motorbike_daily", None) or "No"
    mbf = coeff.get("motorbike_factors", {}).get(motorbike, 1.0)

    # Water access
    water = getattr(req, "water_access", None) or "Piped/Safe"
    waf = coeff.get("water_factors", {}).get(water, 1.0)

    # Healthcare proximity — severity factor
    proximity = getattr(req, "healthcare_proximity", None) or "<5km"
    hpxf = coeff.get("proximity_factors", {}).get(proximity, 1.0)

    freq_mult = bmif * alf * hospf * medf * fhf * mrf * df * slf * stf * mbf * waf

    breakdown = []
    def _dir(f): return "up" if f > 1 else "down" if f < 1 else "neutral"
    if bmif != 1.0:   breakdown.append({"factor": f"BMI ({bmi_cat})",                         "coefficient": round(bmif, 4), "direction": _dir(bmif)})
    if alf != 1.0:    breakdown.append({"factor": f"Alcohol ({alcohol})",                       "coefficient": round(alf,  4), "direction": _dir(alf)})
    if hospf != 1.0:  breakdown.append({"factor": f"Prior hospitalisations ({hosp})",           "coefficient": round(hospf,4), "direction": _dir(hospf)})
    if medf != 1.0:   breakdown.append({"factor": f"Medications ({meds})",                      "coefficient": round(medf, 4), "direction": _dir(medf)})
    if fh_count > 0:  breakdown.append({"factor": f"Family history ({fh_count} conditions)",   "coefficient": round(fhf,  4), "direction": _dir(fhf)})
    if mrf != 1.0:    breakdown.append({"factor": f"Marital status ({marital})",                "coefficient": round(mrf,  4), "direction": _dir(mrf)})
    if df != 1.0:     breakdown.append({"factor": f"Diet ({diet})",                             "coefficient": round(df,   4), "direction": _dir(df)})
    if slf != 1.0:    breakdown.append({"factor": f"Sleep ({sleep})",                           "coefficient": round(slf,  4), "direction": _dir(slf)})
    if stf != 1.0:    breakdown.append({"factor": f"Stress ({stress})",                         "coefficient": round(stf,  4), "direction": _dir(stf)})
    if mbf != 1.0:    breakdown.append({"factor": f"Motorbike ({motorbike})",                   "coefficient": round(mbf,  4), "direction": _dir(mbf)})
    if waf != 1.0:    breakdown.append({"factor": f"Water access ({water})",                    "coefficient": round(waf,  4), "direction": _dir(waf)})
    if hpxf != 1.0:   breakdown.append({"factor": f"Healthcare proximity ({proximity})",        "coefficient": round(hpxf, 4), "direction": _dir(hpxf)})

    return freq_mult, hpxf, breakdown

def _glm_predict(cov: str, req) -> dict:
    """Poisson-Gamma GLM with explicit coefficients. Every factor is named and auditable."""
    ab = _age_band(req.age)
    af = COEFF["age_factors"].get(ab, 1.0)
    sf = COEFF["smoking_factors"].get(req.smoking_status, 1.0)
    ef = COEFF["exercise_factors"].get(req.exercise_frequency, 1.0)
    of = COEFF["occupation_factors"].get(req.occupation_type, 1.0)
    rf = COEFF["region_factors"].get(req.region, 1.0)
    pe_count = len([p for p in req.preexist_conditions if p != "None"])
    pf = 1 + pe_count * COEFF["preexist_per_condition"]
    ext_freq, hpxf, ext_breakdown = _extended_factors(req, COEFF)

    freq = COEFF["base_freq"][cov] * af * sf * ef * of * pf * ext_freq
    sev  = COEFF["base_sev"][cov]  * rf * (1 + max(0, req.age - 30) * COEFF["sev_age_gradient"]) * hpxf

    breakdown = [
        {"factor": f"Age bracket ({ab})",                  "coefficient": round(af, 4), "direction": "up" if af > 1 else "down" if af < 1 else "neutral"},
        {"factor": f"Smoking ({req.smoking_status})",       "coefficient": round(sf, 4), "direction": "up" if sf > 1 else "neutral"},
        {"factor": f"Exercise ({req.exercise_frequency})",  "coefficient": round(ef, 4), "direction": "up" if ef > 1 else "down"},
        {"factor": f"Occupation ({req.occupation_type})",   "coefficient": round(of, 4), "direction": "up" if of > 1 else "down" if of < 1 else "neutral"},
        {"factor": f"Region ({req.region})",                "coefficient": round(rf, 4), "direction": "up" if rf > 1 else "down" if rf < 1 else "neutral"},
    ]
    if pe_count > 0:
        breakdown.append({"factor": f"Pre-existing conditions ({pe_count})", "coefficient": round(pf, 4), "direction": "up"})
    breakdown.extend(ext_breakdown)

    return {
        "frequency":            round(freq, 4),
        "severity":             round(sev, 2),
        "expected_annual_cost": round(freq * sev, 2),
        "breakdown":            breakdown,
        "source":               "glm",
        "model_version":        COEFF["version"],
    }

def _glm_predict_prospect(cov: str, req, coeff: dict) -> dict:
    """Same as _glm_predict but uses a prospect-specific COEFF dict."""
    ab = _age_band(req.age)
    af = coeff["age_factors"].get(ab, 1.0)
    sf = coeff["smoking_factors"].get(req.smoking_status, 1.0)
    ef = coeff["exercise_factors"].get(req.exercise_frequency, 1.0)
    of = coeff["occupation_factors"].get(req.occupation_type, 1.0)
    rf = coeff["region_factors"].get(req.region, 1.0)
    pe_count = len([p for p in req.preexist_conditions if p != "None"])
    pf = 1 + pe_count * coeff["preexist_per_condition"]
    ext_freq, hpxf, _ = _extended_factors(req, coeff)
    freq = coeff["base_freq"][cov] * af * sf * ef * of * pf * ext_freq
    sev  = coeff["base_sev"][cov]  * rf * (1 + max(0, req.age - 30) * coeff["sev_age_gradient"]) * hpxf
    return {"frequency": round(freq, 4), "severity": round(sev, 2),
            "expected_annual_cost": round(freq * sev, 2), "source": "custom-glm",
            "model_version": coeff.get("version", "custom")}

def _load_prospect_coeffs():
    global _prospect_coeffs
    custom_dir = os.path.join(MODEL_DIR, "custom")
    if not os.path.isdir(custom_dir): return
    loaded = 0
    for prospect_id in os.listdir(custom_dir):
        coeff_path = os.path.join(custom_dir, prospect_id, "coeff.json")
        if os.path.isfile(coeff_path):
            try:
                with open(coeff_path) as f:
                    _prospect_coeffs[prospect_id] = json.load(f)
                loaded += 1
            except Exception as e:
                log.warning(f"Failed to load custom coeff for {prospect_id}: {e}")
    if loaded:
        log.info(f"Loaded {loaded} prospect custom model(s): {list(_prospect_coeffs.keys())}")

@asynccontextmanager
async def lifespan(app):
    global db_pool,models,model_version,model_meta
    # GLM coefficient engine — no pickle files needed
    model_version = COEFF["version"]
    model_meta.update({"version": COEFF["version"], "approach": "Poisson-Gamma GLM", "last_updated": COEFF["last_updated"]})
    log.info(f"GLM engine ready: {COEFF['version']} ({len(COEFF['age_factors'])} age bands, {len(COEFF['region_factors'])} regions)")
    _load_prospect_coeffs()
    # Database
    if _db_p:
        try:
            db_pool=await asyncpg.create_pool(host=_db_p["host"],port=_db_p["port"],user=_db_p["user"],password=_db_p["password"],database=_db_p["database"],min_size=1,max_size=5,command_timeout=10,timeout=10,ssl="require")
            log.info("DB connected")
            app.state.db_pool = db_pool
        except Exception as e: log.warning(f"DB failed: {e}")
        if db_pool:
            try:
                await db_pool.execute("""
                    ALTER TABLE hp_user_behavior
                        ADD COLUMN IF NOT EXISTS browser_id TEXT,
                        ADD COLUMN IF NOT EXISTS email TEXT,
                        ADD COLUMN IF NOT EXISTS anomaly_flag BOOLEAN DEFAULT FALSE;
                    ALTER TABLE hp_quote_log
                        ADD COLUMN IF NOT EXISTS underwriting_status TEXT,
                        ADD COLUMN IF NOT EXISTS used_fallback BOOLEAN DEFAULT FALSE,
                        ADD COLUMN IF NOT EXISTS browser_id TEXT,
                        ADD COLUMN IF NOT EXISTS email TEXT;
                """)
                await db_pool.execute("""
                    CREATE TABLE IF NOT EXISTS hp_sessions (
                        id SERIAL PRIMARY KEY,
                        token_hash TEXT UNIQUE NOT NULL,
                        email TEXT NOT NULL,
                        browser_id TEXT,
                        uses_remaining INT DEFAULT 10,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS hp_model_versions (
                        id SERIAL PRIMARY KEY,
                        version TEXT NOT NULL,
                        coverage TEXT,
                        training_dataset TEXT,
                        r2 NUMERIC,
                        promoted_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS hp_partner_keys (
                        id SERIAL PRIMARY KEY,
                        key_hash TEXT UNIQUE NOT NULL,
                        partner_name TEXT NOT NULL,
                        daily_limit INT DEFAULT 500,
                        is_active BOOLEAN DEFAULT TRUE,
                        total_requests BIGINT DEFAULT 0,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        last_used_at TIMESTAMPTZ
                    );
                """)
                log.info("Schema migrations OK")
            except Exception as e: log.warning(f"Schema migration: {e}")
            try:
                await db_pool.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        id TEXT PRIMARY KEY,
                        status TEXT NOT NULL DEFAULT 'submitted',
                        full_name TEXT,
                        date_of_birth TEXT,
                        gender TEXT,
                        phone TEXT,
                        email TEXT,
                        region TEXT,
                        occupation TEXT,
                        national_id TEXT,
                        medical_data JSONB,
                        document_id TEXT,
                        consent_signature TEXT,
                        submitted_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS application_events (
                        id SERIAL PRIMARY KEY,
                        case_id TEXT NOT NULL,
                        event TEXT NOT NULL,
                        done BOOLEAN DEFAULT TRUE,
                        event_at TIMESTAMPTZ
                    );
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        case_id TEXT,
                        filename TEXT,
                        upload_status TEXT DEFAULT 'pending',
                        extracted_data JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                log.info("Application schema OK")
            except Exception as e: log.warning(f"Application schema: {e}")
            try:
                await db_pool.execute("""
                    ALTER TABLE applications ADD COLUMN IF NOT EXISTS reviewer_id TEXT;
                    ALTER TABLE applications ADD COLUMN IF NOT EXISTS decision_notes TEXT;
                    ALTER TABLE applications ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
                    ALTER TABLE applications ADD COLUMN IF NOT EXISTS risk_level TEXT;
                """)
                log.info("Application columns OK")
            except Exception as e: log.warning(f"Application columns: {e}")
            try:
                await db_pool.execute("""
                    CREATE TABLE IF NOT EXISTS auto_policies (
                        policy_id TEXT PRIMARY KEY,
                        vehicle_type TEXT NOT NULL,
                        year_of_manufacture INT NOT NULL,
                        region TEXT NOT NULL,
                        driver_age INT NOT NULL,
                        accident_history BOOLEAN NOT NULL,
                        coverage TEXT NOT NULL,
                        tier TEXT NOT NULL,
                        family_size INT DEFAULT 1,
                        glm_anchor NUMERIC NOT NULL,
                        current_premium NUMERIC NOT NULL,
                        deviation_multiplier NUMERIC DEFAULT 1.0,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS auto_telemetry_log (
                        id SERIAL PRIMARY KEY,
                        policy_id TEXT NOT NULL,
                        gps_hash TEXT,
                        speed_kmh NUMERIC,
                        harsh_braking BOOLEAN DEFAULT FALSE,
                        lane_shifts INT DEFAULT 0,
                        hour_bucket INT,
                        weather_zone TEXT,
                        deviation NUMERIC,
                        new_premium NUMERIC,
                        ts TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_auto_telemetry_policy ON auto_telemetry_log(policy_id, ts DESC);
                """)
                log.info("Auto schema OK")
            except Exception as e: log.warning(f"Auto schema: {e}")
            # Load active partner keys into memory cache
            try:
                rows=await db_pool.fetch("SELECT key_hash,partner_name,daily_limit FROM hp_partner_keys WHERE is_active=TRUE")
                for r in rows:
                    _partner_keys[r["key_hash"]]={"partner_name":r["partner_name"],"daily_limit":r["daily_limit"],"usage_today":0,"date":None}
                log.info(f"Loaded {len(_partner_keys)} partner key(s)")
            except Exception as e: log.warning(f"Partner key load: {e}")
            # AI Lab file storage table
            try:
                await db_pool.execute("""
                    CREATE TABLE IF NOT EXISTS ailab_files (
                        filename TEXT PRIMARY KEY,
                        file_data BYTEA NOT NULL,
                        meta JSONB NOT NULL DEFAULT '{}',
                        uploaded_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                log.info("AI Lab schema OK")
            except Exception as e: log.warning(f"AI Lab schema: {e}")
            # Restore AI Lab files from DB to /tmp
            try:
                await _restore_ailab_from_db()
            except Exception as e: log.warning(f"AI Lab restore: {e}")
    yield
    if db_pool: await db_pool.close()

app=FastAPI(title="DAC HealthPrice API",version="2.2.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

# Health Insurance Pricing Lab routes (DAC-UW-Agent integration)
try:
    from app.routes.health_pricing import router as health_router
    app.include_router(health_router)
except Exception as _health_err:
    log.warning(f"Health pricing routes not loaded: {_health_err}")

# V2 Compatibility routes (for existing frontend)
try:
    from app.routes.health_pricing_v2_compat import router as v2_router
    app.include_router(v2_router)
except Exception as _v2_err:
    log.warning(f"V2 compatibility routes not loaded: {_v2_err}")

# Escalation product routes (Phase 5E)
try:
    from app.routes.escalation import router as escalation_router
    app.include_router(escalation_router)
except Exception as _esc_err:
    log.warning(f"Escalation routes not loaded: {_esc_err}")

# Life insurance pricing routes (centralized from medical_reader.pricing)
try:
    from app.routes.life_pricing import router as life_router
    app.include_router(life_router)
except Exception as _life_err:
    log.warning(f"Life pricing routes not loaded: {_life_err}")

# Auto insurance continuous underwriting routes
try:
    from app.routes.auto_pricing import router as auto_router
    app.include_router(auto_router)
except Exception as _auto_err:
    log.warning(f"Auto pricing routes not loaded: {_auto_err}")

# Thesis contextual bandit underwriting routes
try:
    from app.routes.bandit_underwriting import router as bandit_router
    app.include_router(bandit_router)
    log.info("Bandit underwriting routes loaded")
except Exception as _bandit_err:
    log.warning(f"Bandit underwriting routes not loaded: {_bandit_err}")

@app.middleware("http")
async def mw(request:Request,call_next):
    ip=request.client.host if request.client else "x"
    if not _rl(ip): return JSONResponse(429,{"detail":"Rate limit exceeded"})
    request.state.rid=str(uuid.uuid4())[:12]
    r=await call_next(request); r.headers["X-Request-ID"]=request.state.rid; return r

class PricingRequest(BaseModel):
    age:int=Field(...,ge=0,le=100); gender:str=Field(...); country:str=Field("cambodia"); region:str=Field(...)
    smoking_status:str=Field("Never"); exercise_frequency:str=Field("Light"); occupation_type:str=Field("Office/Desk")
    preexist_conditions:List[str]=Field(default_factory=lambda:["None"])
    ipd_tier:str=Field("Silver"); family_size:int=Field(1,ge=1,le=10)
    include_opd:bool=False; include_dental:bool=False; include_maternity:bool=False
    browser_id:Optional[str]=Field(None); email:Optional[str]=Field(None)
    # ── Extended lifestyle & clinical inputs (v2.3) ───────────────────────────
    bmi_height:Optional[float]=Field(None,ge=100,le=250)   # cm
    bmi_weight:Optional[float]=Field(None,ge=20,le=300)    # kg
    alcohol:Optional[str]=Field(None)
    prev_hospitalizations:Optional[int]=Field(None,ge=0,le=10)
    medications_count:Optional[int]=Field(None,ge=0,le=20)
    family_history:Optional[List[str]]=Field(default_factory=list)
    marital_status:Optional[str]=Field(None)
    diet:Optional[str]=Field(None)
    sleep_quality:Optional[str]=Field(None)
    stress_level:Optional[str]=Field(None)
    motorbike_daily:Optional[str]=Field(None)
    water_access:Optional[str]=Field(None)
    healthcare_proximity:Optional[str]=Field(None)

    @field_validator("gender")
    @classmethod
    def vg(cls,v): v=v.strip().title(); assert v in VALID_GENDERS,f"Must be {VALID_GENDERS}"; return v
    @field_validator("country")
    @classmethod
    def vc(cls,v): v=v.strip().lower(); assert v in CTY_REG,f"Must be {list(CTY_REG)}"; return v
    @field_validator("smoking_status")
    @classmethod
    def vs(cls,v): v=v.strip().title(); assert v in VALID_SMOKING,f"Must be {VALID_SMOKING}"; return v
    @field_validator("exercise_frequency")
    @classmethod
    def ve(cls,v): v=v.strip().title(); assert v in VALID_EXERCISE,f"Must be {VALID_EXERCISE}"; return v
    @field_validator("occupation_type")
    @classmethod
    def vo(cls,v): v=v.strip(); assert v in VALID_OCC,f"Must be {VALID_OCC}"; return v
    @field_validator("ipd_tier")
    @classmethod
    def vt(cls,v): v=v.strip().title(); assert v in TIERS,f"Must be {list(TIERS)}"; return v
    @field_validator("preexist_conditions")
    @classmethod
    def vp(cls,v):
        clean=[c.strip() for c in v if c.strip() in VALID_PE]
        if not clean: clean=["None"]
        if "None" in clean and len(clean)>1: clean=[c for c in clean if c!="None"]
        return clean
    @model_validator(mode="after")
    def vr(self):
        if self.region not in CTY_REG.get(self.country,set()):
            raise ValueError(f"'{self.region}' not valid for {self.country}. Valid: {sorted(CTY_REG[self.country])}")
        return self

def _predict(cov, req):
    """Route to GLM engine. req is the full PricingRequest object."""
    return _glm_predict(cov, req)

def _qid(): return f"HP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

# ── Task 1: Authoritative underwriting / rule engine ─────────────────────────
def _check_underwriting(req) -> dict:
    flags=[]
    conditions=[c for c in req.preexist_conditions if c!="None"]
    if req.age<18:
        flags.append({"level":"decline","code":"AGE_MINIMUM","msg":"Minimum insurable age is 18. Coverage is not available for this applicant."})
    if req.age>70:
        flags.append({"level":"decline","code":"AGE_MAXIMUM","msg":"Age exceeds maximum insurable limit (70). Manual underwriting required before coverage can be offered."})
    if "Cancer (remission)" in conditions:
        flags.append({"level":"refer","code":"CANCER_HISTORY","msg":"Cancer history: additional medical underwriting review required. Loading and exclusion clauses may apply."})
    if "Kidney Disease" in conditions:
        flags.append({"level":"refer","code":"KIDNEY_DISEASE","msg":"Kidney disease: renal-related claims subject to exclusion clause. Additional loading applies."})
    if "Liver Disease" in conditions:
        flags.append({"level":"refer","code":"LIVER_DISEASE","msg":"Liver disease: hepatic-related claims subject to exclusion clause. Additional loading applies."})
    if len(conditions)>=3:
        flags.append({"level":"refer","code":"MULTI_CONDITION","msg":f"{len(conditions)} pre-existing conditions declared — medical underwriting referral recommended before binding coverage."})
    if req.smoking_status=="Current" and ("Heart Disease" in conditions or "Asthma/COPD" in conditions):
        flags.append({"level":"refer","code":"HIGH_RISK_COMBO","msg":"Current smoker with cardiovascular/respiratory condition: significant additional loading will apply."})
    has_decline=any(f["level"]=="decline" for f in flags)
    has_refer=any(f["level"]=="refer" for f in flags)
    status="decline" if has_decline else "refer" if has_refer else "accept"
    return {"status":status,"flags":flags}

# ── Layer 1: daily quota per browser_id ──────────────────────────────────────
def _check_daily(browser_id:str)->bool:
    today=datetime.now(timezone.utc).date().isoformat()
    b=_daily_quotes[browser_id]
    if b["date"]!=today: b["date"]=today; b["count"]=0
    b["count"]+=1
    return b["count"]<=DAILY_LIMIT

# ── Layer 3: parameter-sweep anomaly detection ────────────────────────────────
def _detect_sweep(browser_id:str,req)->bool:
    sig={f:getattr(req,f) for f in SWEEP_FIELDS}; sig["conditions"]=tuple(sorted(req.preexist_conditions))
    buf=_probe_buffer[browser_id]; buf.append(sig)
    if len(buf)<SWEEP_THRESHOLD: return False
    recent=list(buf)[-SWEEP_THRESHOLD:]; all_fields=list(recent[0].keys())
    for vf in all_fields:
        others_same=all(all(r[f]==recent[0][f] for f in all_fields if f!=vf) for r in recent[1:])
        if others_same and len({r[vf] for r in recent})>1: return True
    return False

# ── Layers 2+4: output banding + noise ───────────────────────────────────────
def _apply_banding(res:dict)->dict:
    def band(v:float)->float:
        noise=1+(secrets.randbelow(11)-5)/100
        return float(max(P_FLOOR,round(v*noise/25)*25))
    if "ipd_core" in res:
        ap=band(res["ipd_core"]["annual_premium"])
        res["ipd_core"]["annual_premium"]=ap; res["ipd_core"]["monthly_premium"]=round(ap/12,2)
    rtot=0.0
    for cov in res.get("riders",{}):
        rp=band(res["riders"][cov]["annual_premium"])
        res["riders"][cov]["annual_premium"]=rp; res["riders"][cov]["monthly_premium"]=round(rp/12,2); rtot+=rp
    ipd_ap=res["ipd_core"]["annual_premium"] if "ipd_core" in res else 0.0
    ff=res.get("family_factor",1.0); fs=res.get("family_size",1)
    total=round(float(np.clip((ipd_ap+rtot)*ff,P_FLOOR,P_CEIL*fs)),2)
    res["total_annual_premium"]=total; res["total_monthly_premium"]=round(total/12,2)
    res["total_before_family"]=round(ipd_ap+rtot,2); res["quote_banded"]=True
    return res

# ── Task 5: full audit trail logging ─────────────────────────────────────────
async def _log_q(qid,inp,res,uw_status:str="accept",used_fallback:bool=False,browser_id:str="",email:str=""):
    if not db_pool: return
    try:
        await db_pool.execute(
            "INSERT INTO hp_quote_log(quote_ref,input_json,result_json,model_version,underwriting_status,used_fallback,browser_id,email)VALUES($1,$2::jsonb,$3::jsonb,$4,$5,$6,$7,$8)",
            qid,json.dumps(inp,default=str),json.dumps(res,default=str),model_version,uw_status,used_fallback,browser_id,email)
    except Exception as e: log.warning(f"Log fail: {e}")

async def _log_b(qid,req,browser_id:str="",email:str="",anomaly_flag:bool=False):
    if not db_pool: return
    try:
        await db_pool.execute(
            "INSERT INTO hp_user_behavior(quote_ref,age,gender,country,region,smoking,exercise,occupation,preexist_count,ipd_tier,include_opd,include_dental,include_maternity,family_size,browser_id,email,anomaly_flag)VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)",
            qid,req.age,req.gender,req.country,req.region,req.smoking_status,req.exercise_frequency,req.occupation_type,len([p for p in req.preexist_conditions if p!="None"]),req.ipd_tier,req.include_opd,req.include_dental,req.include_maternity,req.family_size,browser_id,email,anomaly_flag)
    except Exception as e: log.warning(f"Beh fail: {e}")

@app.get("/health")
async def health():
    return {"status":"healthy","service":"DAC HealthPrice v2.3","pricing_approach":"Poisson-Gamma GLM","coefficient_version":COEFF["version"],"model_version":model_version,"database_connected":db_pool is not None,"countries":list(CTY_REG.keys()),"timestamp":datetime.now(timezone.utc).isoformat()}

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login", tags=["auth"])
async def login(body: LoginRequest):
    user = STAFF_USERS.get(body.username.strip().lower())
    if not user or not secrets.compare_digest(body.password, user["password"]):
        raise HTTPException(401, "Invalid credentials")
    token = pyjwt.encode(
        {"sub": body.username, "role": user["role"], "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HRS)},
        JWT_SECRET, algorithm=JWT_ALGO,
    )
    return {"access_token": token, "token_type": "bearer", "role": user["role"], "username": body.username}

# ── Partner key verification ─────────────────────────────────────────────────
def _check_partner_daily(key_hash:str)->bool:
    today=datetime.now(timezone.utc).date().isoformat()
    p=_partner_keys[key_hash]
    if p["date"]!=today: p["date"]=today; p["usage_today"]=0
    if p["usage_today"]>=p["daily_limit"]: return False
    p["usage_today"]+=1; return True

async def verify_pricing_auth(x_session_token:Optional[str]=Header(None),x_partner_key:Optional[str]=Header(None)):
    """Accept either a session token (consumer flow) or a partner API key (B2B flow)."""
    if x_partner_key:
        kh=hashlib.sha256(x_partner_key.encode()).hexdigest()
        if kh not in _partner_keys:
            raise HTTPException(401,"Invalid partner API key.")
        if not _partner_keys[kh].get("is_active",True):
            raise HTTPException(403,"Partner key has been revoked.")
        if not _check_partner_daily(kh):
            raise HTTPException(429,f"Partner daily quota ({_partner_keys[kh]['daily_limit']}) exhausted.")
        if db_pool:
            try: await db_pool.execute("UPDATE hp_partner_keys SET total_requests=total_requests+1,last_used_at=NOW() WHERE key_hash=$1",kh)
            except Exception as e: log.warning(f"Partner key update: {e}")
        return {"type":"partner","key_hash":kh,"partner_name":_partner_keys[kh]["partner_name"]}
    # Fall back to session token
    if not x_session_token:
        raise HTTPException(401,"Session token required. Call POST /api/v2/session with your email first, or provide X-Partner-Key.")
    if x_session_token not in _sessions:
        raise HTTPException(401,"Invalid or expired session token.")
    sess=_sessions[x_session_token]
    if sess["uses_remaining"]<=0:
        _sessions.pop(x_session_token,None)
        raise HTTPException(429,"Session quota exhausted. Request a new session.")
    return {"type":"session","token":x_session_token,"email":sess.get("email","")}

# ── Layer 5: email gate ───────────────────────────────────────────────────────
class SessionRequest(BaseModel):
    email:str
    browser_id:Optional[str]=None

@app.post("/api/v2/session")
async def create_session(body:SessionRequest):
    e=body.email.strip().lower()
    if not e or "@" not in e or "." not in e.split("@")[-1]:
        raise HTTPException(400,"Valid email address required.")
    token=secrets.token_urlsafe(32)
    _sessions[token]={"email":e,"browser_id":body.browser_id or "","uses_remaining":SESSION_QUOTE_LIMIT,"created_at":datetime.now(timezone.utc).isoformat()}
    if db_pool:
        try:
            await db_pool.execute("INSERT INTO hp_sessions(token_hash,email,browser_id,uses_remaining)VALUES($1,$2,$3,$4)",
                hashlib.sha256(token.encode()).hexdigest(),e,body.browser_id or "",SESSION_QUOTE_LIMIT)
        except Exception as ex: log.warning(f"Session log fail: {ex}")
    log.info(f"Session created for {e[:3]}***@{e.split('@')[-1]}")
    return {"token":token,"quotes_remaining":SESSION_QUOTE_LIMIT,"expires_in":3600}

@app.post("/api/v2/price")
async def calc(req:PricingRequest,request:Request,auth:dict=Depends(verify_pricing_auth),prospect_id:Optional[str]=Query(None,description="Use a prospect-specific calibrated model")):
    bid=req.browser_id or request.client.host or "anon"
    is_partner=auth["type"]=="partner"
    # Consumer-path daily quota (partners have their own quota enforced in verify_pricing_auth)
    if not is_partner and not _check_daily(bid):
        raise HTTPException(429,f"Daily quote limit ({DAILY_LIMIT}) reached for this device.")
    is_sweep=_detect_sweep(bid,req)
    if is_sweep:
        partner_tag=auth.get("partner_name","?") if is_partner else _sessions.get(auth.get("token",""),{}).get("email","?")
        log.warning(f"Sweep detected: browser_id={bid} identity={partner_tag}")

    # Task 1: Authoritative underwriting check
    uw=_check_underwriting(req)
    _tok=auth.get("token") if auth["type"]=="session" else None
    _email_from_auth=auth.get("partner_name","") if is_partner else _sessions.get(_tok or "",{}).get("email","")
    if uw["status"]=="decline":
        qid=_qid(); rid=getattr(request.state,"rid","?")
        email=req.email or _email_from_auth
        await _log_q(qid,req.model_dump(),{"underwriting":uw},uw_status="decline",browser_id=bid,email=email)
        await _log_b(qid,req,bid,email,is_sweep)
        if _tok and _tok in _sessions: _sessions[_tok]["uses_remaining"]-=1
        log.info(f"[{rid}] DECLINED age={req.age} conditions={req.preexist_conditions}")
        return {"quote_id":qid,"underwriting":uw,"total_annual_premium":None,"total_monthly_premium":None,"message":"Application requires manual underwriting review. An underwriter will contact you.","calculated_at":datetime.now(timezone.utc).isoformat()}

    t0=time.monotonic(); qid=_qid(); rid=getattr(request.state,"rid","?")
    # Route to prospect-specific model if requested and available
    _active_coeff=COEFF
    _pilot_tag=None
    if prospect_id:
        if prospect_id not in _prospect_coeffs:
            raise HTTPException(404,f"No calibrated model found for prospect '{prospect_id}'. Run training first.")
        _active_coeff=_prospect_coeffs[prospect_id]
        _pilot_tag=prospect_id
        log.info(f"[{rid}] Using custom model for prospect={prospect_id}")
    def _predict_active(cov,r): return _glm_predict_prospect(cov,r,_active_coeff) if _pilot_tag else _predict(cov,r)
    ipd=_predict_active("ipd",req); tier=TIERS[req.ipd_tier]; tf=T_F[req.ipd_tier]

    ded_cr=round(tier["deductible"]*0.10,2)
    ipd_loaded=round(ipd["expected_annual_cost"]*(1+LOAD_FACTOR)*tf,2)
    ipd_prem=round(float(np.clip(ipd_loaded-ded_cr,P_FLOOR,P_CEIL)),2)

    riders={}; rtot=0
    for c,inc in [("opd",req.include_opd),("dental",req.include_dental),("maternity",req.include_maternity)]:
        if not inc: continue
        r=_predict_active(c,req); rp=round(float(np.clip(r["expected_annual_cost"]*(1+LOAD_FACTOR),10,5000)),2)
        riders[c]={"name":COV[c]["name"],"frequency":r["frequency"],"severity":r["severity"],"expected_annual_cost":r["expected_annual_cost"],"annual_premium":rp,"monthly_premium":round(rp/12,2),"source":r["source"],"breakdown":r.get("breakdown",[])}
        rtot+=rp
    ff=round(1+(req.family_size-1)*0.65,2); pre_fam=round(ipd_prem+rtot,2)
    total=round(float(np.clip(pre_fam*ff,P_FLOOR,P_CEIL*req.family_size)),2)
    email=req.email or _email_from_auth

    res={"quote_id":qid,"request_id":rid,"country":req.country,"region":req.region,"model_version":_active_coeff.get("version",COEFF["version"]),
        "model_source":"ml","model_accuracy_pct":91.0,
        **({"pilot_model":_pilot_tag} if _pilot_tag else {}),
        "pricing_approach":"Poisson-Gamma GLM","coefficient_version":COEFF["version"],
        "ipd_tier":req.ipd_tier,"tier_benefits":tier,"underwriting":uw,
        "ipd_core":{"frequency":ipd["frequency"],"severity":ipd["severity"],"expected_annual_cost":ipd["expected_annual_cost"],"tier_factor":tf,"deductible_credit":ded_cr,"annual_premium":ipd_prem,"monthly_premium":round(ipd_prem/12,2),"source":ipd["source"],"breakdown":ipd.get("breakdown",[])},
        "riders":riders,"family_size":req.family_size,"family_factor":ff,"total_before_family":pre_fam,
        "total_annual_premium":total,"total_monthly_premium":round(total/12,2),
        "risk_profile":{"age":req.age,"gender":req.gender,"smoking":req.smoking_status,"exercise":req.exercise_frequency,"occupation":req.occupation_type,"preexist_conditions":req.preexist_conditions,"preexist_count":len([p for p in req.preexist_conditions if p!="None"])},
        "calculated_at":datetime.now(timezone.utc).isoformat()}

    res=_apply_banding(res)
    if _tok and _tok in _sessions: _sessions[_tok]["uses_remaining"]-=1
    if is_partner: res["partner"]=auth.get("partner_name","")

    await _log_q(qid,req.model_dump(),res,uw_status=uw["status"],used_fallback=False,browser_id=bid,email=email)
    await _log_b(qid,req,bid,email,is_sweep)
    ms=round((time.monotonic()-t0)*1000,1)
    log.info(f"[{rid}] {qid}|{req.ipd_tier}+{'+'.join(riders) or 'none'}|age={req.age}|${total:,.0f}/yr|uw={uw['status']}|glm={COEFF['version']}|sweep={is_sweep}|{ms}ms")
    return res

# ── AI Chat proxy ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 800
    system: str
    tools: list = []
    messages: list

@app.post("/api/v2/chat")
async def chat_proxy(body: ChatRequest, auth: dict = Depends(verify_pricing_auth)):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "Chat service unavailable.")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body.model_dump(),
        )
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    return r.json()

@app.get("/api/v2/reference")
async def ref():
    return {"countries":{k:{"regions":v} for k,v in CTY_REG_L.items()},"genders":VALID_GENDERS,"smoking":VALID_SMOKING,"exercise":VALID_EXERCISE,"occupations":VALID_OCC,"preexist":sorted(VALID_PE),"tiers":TIERS,"tier_factors":T_F,"coverages":COV,"premium_bounds":{"floor":P_FLOOR,"ceiling":P_CEIL}}

# ── Scenario AI Agent ─────────────────────────────────────────────────────────
# Actuarial what-if analysis via tool-use: accepts natural language questions,
# runs GLM sweeps internally, returns narrative synthesis + raw data.
class ScenarioAgentRequest(BaseModel):
    question: str = Field(..., description="Natural language scenario question for the actuary")
    base_profile: dict = Field(default_factory=dict, description="Optional profile overrides applied to all tool calls")
    max_quotes: int = Field(default=30, le=60, description="Max quotes the agent may run (cost guard)")

_AGENT_TOOLS = [
    {
        "name": "run_quote",
        "description": (
            "Run a single health insurance quote through the Poisson-Gamma GLM engine. "
            "Returns annual premium, monthly premium, frequency/severity components, "
            "and which risk factors drove the price. Use this to spot-check individual profiles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "age":               {"type": "integer", "description": "Applicant age 18-100"},
                "gender":            {"type": "string",  "description": "Male | Female"},
                "smoking_status":    {"type": "string",  "description": "Never | Former | Current"},
                "exercise_frequency":{"type": "string",  "description": "Sedentary | Light | Moderate | Active"},
                "occupation_type":   {"type": "string",  "description": "Office/Desk | Retail/Service | Healthcare | Manual Labor | Industrial/High-Risk | Retired"},
                "preexist_conditions":{"type": "array",  "items": {"type": "string"}, "description": "e.g. ['Diabetes','Hypertension'] or ['None']"},
                "ipd_tier":          {"type": "string",  "description": "Bronze | Silver | Gold | Platinum"},
                "region":            {"type": "string",  "description": "Phnom Penh | Siem Reap | Battambang | Sihanoukville | Kampong Cham | Rural Areas | Ho Chi Minh City | Hanoi | Da Nang | Can Tho | Hai Phong"},
                "country":           {"type": "string",  "description": "cambodia | vietnam"},
                "include_opd":       {"type": "boolean"},
                "include_dental":    {"type": "boolean"},
                "include_maternity": {"type": "boolean"},
                "family_size":       {"type": "integer", "description": "1-8"},
            },
            "required": ["age", "gender", "ipd_tier", "region", "country"],
        },
    },
    {
        "name": "sweep_parameter",
        "description": (
            "Vary a single parameter across a list of values, holding the rest of the "
            "profile constant. Returns a table of quotes — ideal for understanding "
            "sensitivity: how much does premium change as age, smoking status, or "
            "tier changes? Use this before run_quote for exploratory analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "param":  {"type": "string", "description": "Parameter to vary: age | smoking_status | ipd_tier | region | exercise_frequency | occupation_type | preexist_conditions"},
                "values": {"type": "array",  "description": "Ordered list of values to test"},
                "base_profile": {"type": "object", "description": "Profile to hold fixed for all other params"},
            },
            "required": ["param", "values", "base_profile"],
        },
    },
]

_SCENARIO_SYSTEM = (
    "You are an actuarial analyst for DAC HealthPrice, a health insurance pricing platform "
    "operating in Cambodia and Vietnam. You have direct access to the live Poisson-Gamma GLM "
    "pricing engine via tools.\n\n"
    "Your job: answer the actuary's question by running targeted scenarios, then synthesise "
    "the results into a clear, precise narrative. Always cite specific dollar amounts and "
    "percentages. Flag any surprising patterns — e.g. non-linear jumps, regional anomalies, "
    "or risk factor interactions that actuaries should be aware of.\n\n"
    "Be concise. Lead with the answer, then support it with numbers."
)

_AGENT_DEFAULT_PROFILE = {
    "age": 35, "gender": "Male", "country": "cambodia", "region": "Phnom Penh",
    "smoking_status": "Never", "exercise_frequency": "Moderate",
    "occupation_type": "Office/Desk", "preexist_conditions": ["None"],
    "ipd_tier": "Silver", "include_opd": False, "include_dental": False,
    "include_maternity": False, "family_size": 1,
}

def _build_glm_req(params: dict) -> SimpleNamespace:
    """Build a lightweight request object for _glm_predict from a params dict."""
    r = SimpleNamespace()
    r.age                  = int(params.get("age", 35))
    r.gender               = params.get("gender", "Male")
    r.smoking_status       = params.get("smoking_status", "Never")
    r.exercise_frequency   = params.get("exercise_frequency", "Moderate")
    r.occupation_type      = params.get("occupation_type", "Office/Desk")
    r.region               = params.get("region", "Phnom Penh")
    r.preexist_conditions  = params.get("preexist_conditions", ["None"])
    # Extended factors — default to neutral values
    r.bmi_height           = None; r.bmi_weight = None
    r.alcohol              = "Never"
    r.prev_hospitalizations = 0
    r.medications_count    = 0
    r.family_history       = []
    r.marital_status       = "Single"
    r.diet                 = "Balanced"
    r.sleep_quality        = "Good (7-9h)"
    r.stress_level         = "Low"
    r.motorbike_daily      = "No"
    r.water_access         = "Piped/Safe"
    r.healthcare_proximity = "<5km"
    return r

def _execute_run_quote(params: dict, base: dict, quota: list) -> dict:
    """Call _glm_predict and compute the loaded premium. quota is a 1-item list used as a mutable counter."""
    if quota[0] <= 0:
        return {"error": "quote_limit_reached"}
    quota[0] -= 1
    p = {**_AGENT_DEFAULT_PROFILE, **base, **params}
    try:
        req = _build_glm_req(p)
        tier_key = p.get("ipd_tier", "Silver")
        tf  = T_F.get(tier_key, 1.0)
        tier = TIERS.get(tier_key, {})
        ded_cr = tier.get("deductible", 0) * 0.002

        ipd = _glm_predict("ipd", req)
        ipd_prem = round(float(np.clip(
            ipd["expected_annual_cost"] * (1 + LOAD_FACTOR) * tf - ded_cr,
            P_FLOOR, P_CEIL
        )), 2)

        riders = []
        rider_total = 0.0
        for cov, flag in [("opd", "include_opd"), ("dental", "include_dental"), ("maternity", "include_maternity")]:
            if p.get(flag, False):
                r_glm = _glm_predict(cov, req)
                r_prem = round(float(np.clip(
                    r_glm["expected_annual_cost"] * (1 + LOAD_FACTOR),
                    P_FLOOR, P_CEIL
                )), 2)
                riders.append({"coverage": cov, "annual_premium": r_prem})
                rider_total += r_prem

        ff = round(1 + (int(p.get("family_size", 1)) - 1) * 0.65, 2)
        total = round(float(np.clip((ipd_prem + rider_total) * ff, P_FLOOR, P_CEIL * int(p.get("family_size", 1)))), 2)

        return {
            "age": req.age, "gender": req.gender, "smoking_status": req.smoking_status,
            "exercise_frequency": req.exercise_frequency, "occupation_type": req.occupation_type,
            "region": req.region, "country": p.get("country", "cambodia"),
            "preexist_conditions": req.preexist_conditions, "ipd_tier": tier_key,
            "family_size": p.get("family_size", 1),
            "ipd_frequency": ipd["frequency"], "ipd_severity": ipd["severity"],
            "ipd_expected_cost": ipd["expected_annual_cost"],
            "ipd_annual_premium": ipd_prem, "ipd_monthly_premium": round(ipd_prem / 12, 2),
            "riders": riders, "family_factor": ff,
            "total_annual_premium": total, "total_monthly_premium": round(total / 12, 2),
            "risk_factors_applied": len(ipd.get("breakdown", [])),
        }
    except Exception as e:
        return {"error": str(e), "params": p}

def _execute_sweep(params: dict, base: dict, quota: list) -> dict:
    param  = params["param"]
    values = params["values"]
    bp     = {**base, **params.get("base_profile", {})}
    results = []
    for v in values:
        row = _execute_run_quote({**bp, param: v}, base, quota)
        row["_sweep_value"] = v
        results.append(row)
    return {"sweep_param": param, "count": len(results), "results": results}

@app.post("/api/v2/scenario-agent")
async def scenario_agent(body: ScenarioAgentRequest, auth: dict = Depends(verify_pricing_auth)):
    """
    Actuarial what-if analysis via AI agent.

    Submit a natural language question; the agent runs GLM scenarios using the
    live pricing engine and returns a narrative synthesis with supporting data.

    Examples:
      - "How does premium change for smokers aged 25-65 in Silver tier?"
      - "Compare Phnom Penh vs Rural Areas for a 45yo male with diabetes."
      - "If Cambodia A/E drops to 0.75, what happens to our loss ratio on Gold tier?"
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "AI service unavailable — ANTHROPIC_API_KEY not set.")

    quota    = [body.max_quotes]   # mutable counter passed by reference
    all_data: list = []
    messages = [{"role": "user", "content": body.question}]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _step in range(12):   # hard cap on agentic steps
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 2048,
                    "system": _SCENARIO_SYSTEM,
                    "tools": _AGENT_TOOLS,
                    "messages": messages,
                },
            )
            if r.status_code != 200:
                raise HTTPException(r.status_code, detail=r.text[:500])

            resp = r.json()
            messages.append({"role": "assistant", "content": resp["content"]})

            if resp["stop_reason"] == "end_turn":
                narrative = next((b["text"] for b in resp["content"] if b["type"] == "text"), "")
                return {
                    "narrative": narrative,
                    "quotes_run": body.max_quotes - quota[0],
                    "data": all_data,
                    "question": body.question,
                }

            if resp["stop_reason"] != "tool_use":
                break

            # Execute all tool calls in this step
            tool_results = []
            for block in resp["content"]:
                if block["type"] != "tool_use":
                    continue
                inp = block["input"]
                if block["name"] == "run_quote":
                    result = _execute_run_quote(inp, body.base_profile, quota)
                    if "error" not in result:
                        all_data.append(result)
                elif block["name"] == "sweep_parameter":
                    result = _execute_sweep(inp, body.base_profile, quota)
                    all_data.extend([row for row in result.get("results", []) if "error" not in row])
                else:
                    result = {"error": f"unknown tool: {block['name']}"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})

    return {
        "narrative": "Agent completed without producing a final response.",
        "quotes_run": body.max_quotes - quota[0],
        "data": all_data,
        "question": body.question,
    }

@app.get("/api/v2/countries")
async def ctry(): return {"countries":[{"id":k,"name":k.title(),"regions":v} for k,v in CTY_REG_L.items()]}

# ── Task 3+4: model versioning + retraining metadata ─────────────────────────
@app.get("/api/v2/model-info")
async def mi():
    return {
        "version":model_version,
        "approach":"Freq-Sev (Poisson+Gamma GLM) — fallback: Poisson+Ridge GLM on synthetic data",
        "models_loaded":list(models.keys()),
        "coefficient_version":COEFF["version"],
        "features":["age","gender","smoking","exercise","occupation","region","preexist"],
        "coverages":list(COV.keys()),
        "last_retrained_at":model_meta.get("last_retrained_at"),
        "training_dataset":model_meta.get("training_dataset"),
        "metrics":model_meta.get("metrics",{}),
    }

# ─── Dashboard helpers ────────────────────────────────────────────────────────
# PSI reference distribution for total_annual_premium (Cambodia Silver-tier baseline)
_HEALTH_PSI_REF = {
    "bins":        [0, 200, 500, 800, 1200, 1800, 2500, 4000, float("inf")],
    "proportions": [0.02, 0.20, 0.25, 0.20, 0.15, 0.10, 0.06, 0.02],
}
_PHNOM_PENH_ALIASES = {"phnom penh", "phonm penh", "pp"}

def _psi_health(premiums: list) -> float:
    """PSI on annual premium distribution vs baseline reference."""
    if len(premiums) < 5:
        return 0.0
    bins     = _HEALTH_PSI_REF["bins"]
    expected = np.array(_HEALTH_PSI_REF["proportions"], dtype=float)
    values   = np.array(premiums, dtype=float)
    bin_idx  = np.digitize(values, bins[1:])
    counts   = np.bincount(bin_idx, minlength=8)[:8]
    actual   = counts.astype(float) / max(len(values), 1)
    eps = 1e-6
    actual   = np.clip(actual,   eps, 1.0)
    expected = np.clip(expected, eps, 1.0)
    return round(float(max(np.sum((actual - expected) * np.log(actual / expected)), 0.0)), 6)

def _classify_health_risk(inp: dict) -> str:
    score = 0
    if inp.get("smoking_status") == "Current":    score += 2
    elif inp.get("smoking_status") == "Former":   score += 1
    conds = inp.get("pre_existing_conditions") or inp.get("preexist_conditions") or []
    if len(conds) >= 3:  score += 2
    elif len(conds) >= 1: score += 1
    if inp.get("occupation_type") in ("Industrial/High-Risk", "Manual Labor"): score += 1
    if inp.get("ipd_tier") in ("Gold", "Platinum"): score += 1
    if score >= 4: return "decline"
    if score >= 3: return "high"
    if score >= 1: return "medium"
    return "low"

def _health_reasoning(inp: dict, res: dict) -> str:
    lines = [
        f"Tier: {inp.get('ipd_tier','?')}  |  {inp.get('country','?')} / {inp.get('region','?')}",
        f"Age {inp.get('age','?')} · {inp.get('gender','?')} · Smoking: {inp.get('smoking_status','?')}",
    ]
    conds = inp.get("pre_existing_conditions") or inp.get("preexist_conditions") or []
    if conds: lines.append(f"Pre-existing: {', '.join(conds)}")
    if inp.get("occupation_type"): lines.append(f"Occupation: {inp['occupation_type']}")
    total = res.get("total_annual_premium", 0)
    if total: lines.append(f"Annual premium: ${total:,.2f}")
    uw = res.get("underwriting")
    if uw and uw not in ("auto_approved", None): lines.append(f"UW flag: {uw}")
    return "\n".join(lines)

def _psi_series_health(rows: list, window_days: int = 30) -> list:
    from collections import defaultdict as _dd
    from datetime import date as _date, timedelta as _td
    by_date: dict = _dd(list)
    for row in rows:
        try:
            ca = row.get("created_at")
            d  = ca.strftime("%Y-%m-%d") if hasattr(ca, "strftime") else str(ca)[:10]
            rj = row.get("result_json", "{}")
            res = json.loads(rj) if isinstance(rj, str) else dict(rj)
            p = res.get("total_annual_premium", 0)
            if p: by_date[d].append(float(p))
        except Exception: pass
    today  = datetime.now(timezone.utc).date()
    result = []
    for offset in range(window_days - 1, -1, -1):
        target   = today - _td(days=offset)
        date_str = target.strftime("%Y-%m-%d")
        rolling  = [v for d, vals in by_date.items() if d <= date_str for v in vals]
        batch    = rolling[-20:] if len(rolling) >= 20 else rolling
        psi      = _psi_health(batch) if len(batch) >= 5 else 0.0
        result.append({"date": date_str, "psi": psi, "n_cases": len(batch)})
    return result


class CaseReviewBody(BaseModel):
    approved: bool
    reviewer_id: str = "dashboard-user"
    notes: str = ""


class PersonalInfo(BaseModel):
    fullName: str
    dateOfBirth: str
    gender: str
    phone: str
    email: str
    region: str
    occupation: str
    nationalId: str = ""

class MedicalInfo(BaseModel):
    height: float
    weight: float
    smokingStatus: str
    alcoholConsumption: str = "Not disclosed"
    exerciseFrequency: str
    bloodPressure: str = ""
    preexistingConditions: list = []
    familyHistory: list = []
    currentMedications: str = ""

class CoverageInfo(BaseModel):
    tier: str = "Silver"
    include_opd: bool = False
    include_dental: bool = False
    include_maternity: bool = False

class ConsentInfo(BaseModel):
    terms: bool = True
    privacy: bool = True
    dataProcessing: bool = True
    truthfulness: bool = True
    signature: str

class ApplicationSubmit(BaseModel):
    personal: PersonalInfo
    medical: MedicalInfo
    coverage: CoverageInfo = CoverageInfo()
    consent: ConsentInfo
    documentId: Optional[str] = None


@app.get("/dashboard/stats", tags=["dashboard"])
async def dashboard_stats(_: dict = Depends(get_current_staff)):
    """Underwriter dashboard KPIs: PSI, HITL manual-review queue, province distribution."""
    quotes  = []
    pending = []
    if db_pool:
        try:
            rows = await db_pool.fetch(
                "SELECT quote_ref, input_json::text AS input_json, "
                "result_json::text AS result_json, underwriting_status, created_at "
                "FROM hp_quote_log ORDER BY created_at DESC LIMIT 200"
            )
            quotes = [dict(r) for r in rows]
            pr = await db_pool.fetch(
                "SELECT quote_ref, input_json::text AS input_json, "
                "result_json::text AS result_json, underwriting_status, created_at "
                "FROM hp_quote_log WHERE underwriting_status='manual_review' "
                "ORDER BY created_at DESC LIMIT 10"
            )
            pending = [dict(r) for r in pr]
        except Exception as e:
            log.warning(f"dashboard DB: {e}")

    # PSI on last 100 non-manual premiums
    premiums = []
    for q in quotes[:100]:
        try:
            r = json.loads(q["result_json"])
            p = r.get("total_annual_premium", 0)
            if p and q.get("underwriting_status") != "manual_review":
                premiums.append(float(p))
        except Exception: pass
    psi_score  = _psi_health(premiums)
    psi_status = "stable" if psi_score < 0.10 else ("warning" if psi_score < 0.25 else "drift")

    # Province distribution
    regions = []
    for q in quotes:
        try: regions.append(json.loads(q["input_json"]).get("region", "").lower())
        except Exception: pass
    pp = sum(1 for r in regions if r in _PHNOM_PENH_ALIASES)

    # HITL summaries
    pending_summaries = []
    for row in pending:
        try:
            inp = json.loads(row["input_json"])
            res = json.loads(row["result_json"])
            pending_summaries.append({
                "case_id":      row["quote_ref"],
                "risk_level":   _classify_health_risk(inp),
                "final_premium": res.get("total_annual_premium", 0),
                "extracted_data": {
                    "age":             inp.get("age"),
                    "province":        inp.get("region"),
                    "occupation_type": inp.get("occupation_type"),
                },
                "reasoning_trace": _health_reasoning(inp, res),
            })
        except Exception: pass

    return {
        "psi":                 {"current": round(psi_score, 4), "status": psi_status},
        "province_distribution": {"phnom_penh": pp, "provinces": len(regions) - pp, "total": len(regions)},
        "hitl_queue":          {"pending_count": len(pending_summaries), "pending_cases": pending_summaries},
        "human_override_rate": {"total_reviewed": 0, "total_overridden": 0, "override_rate": 0.0, "by_risk_level": {}},
        "psi_time_series":     _psi_series_health(quotes, window_days=30),
    }


@app.post("/cases/{case_id}/review", tags=["dashboard"])
async def review_case(case_id: str, body: CaseReviewBody, _: dict = Depends(require_roles("admin", "underwriter"))):
    """Approve or decline a manual-review case from the underwriter dashboard."""
    if not db_pool:
        raise HTTPException(503, "Database unavailable")
    new_status = "approved" if body.approved else "declined"
    result = await db_pool.execute(
        "UPDATE hp_quote_log SET underwriting_status=$1 WHERE quote_ref=$2",
        new_status, case_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, f"Case {case_id} not found")
    return {"case_id": case_id, "status": new_status, "reviewer_id": body.reviewer_id}


_STATUS_DISPLAY = {
    "submitted":    "Received",
    "in_review":    "Under Review",
    "approved":     "Approved",
    "declined":     "Declined",
    "referred":     "Decision Pending",
    "pending_docs": "On Hold",
}

_STATUS_NOTES = {
    "submitted":    "Your application has been received and is awaiting review.",
    "in_review":    "Your application is currently under review by our underwriting team.",
    "approved":     "Congratulations! Your application has been approved.",
    "declined":     "After careful review, we are unable to offer coverage at this time.",
    "referred":     "Your application requires additional review. We will contact you shortly.",
    "pending_docs": "Additional documentation is required to process your application.",
}

_INITIAL_TIMELINE = [
    ("Application received", True),
    ("Initial review",       False),
    ("Underwriter decision", False),
    ("Policy issued",        False),
]


@app.post("/api/v1/applications", tags=["applications"])
async def create_application(body: ApplicationSubmit):
    case_id = f"DAC-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    if db_pool:
        try:
            await db_pool.execute(
                "INSERT INTO applications(id,status,full_name,date_of_birth,gender,phone,email,region,occupation,national_id,medical_data,document_id,consent_signature)"
                " VALUES($1,'submitted',$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12)",
                case_id,
                body.personal.fullName, body.personal.dateOfBirth, body.personal.gender,
                body.personal.phone, body.personal.email, body.personal.region,
                body.personal.occupation, body.personal.nationalId,
                json.dumps({"height": body.medical.height, "weight": body.medical.weight,
                            "smokingStatus": body.medical.smokingStatus,
                            "alcoholConsumption": body.medical.alcoholConsumption,
                            "exerciseFrequency": body.medical.exerciseFrequency,
                            "bloodPressure": body.medical.bloodPressure,
                            "preexistingConditions": body.medical.preexistingConditions,
                            "familyHistory": body.medical.familyHistory,
                            "currentMedications": body.medical.currentMedications,
                            "coverage": {"tier": body.coverage.tier, "include_opd": body.coverage.include_opd,
                                         "include_dental": body.coverage.include_dental, "include_maternity": body.coverage.include_maternity}}),
                body.documentId, body.consent.signature,
            )
            await db_pool.executemany(
                "INSERT INTO application_events(case_id,event,done,event_at) VALUES($1,$2,$3,$4)",
                [(case_id, ev, done, now if done else None) for ev, done in _INITIAL_TIMELINE],
            )
        except Exception as e:
            log.warning(f"create_application DB: {e}")
    return {"case_id": case_id}


@app.get("/api/v1/applications/{case_id}/status", tags=["applications"])
async def get_application_status(case_id: str):
    if not db_pool:
        raise HTTPException(503, "Database unavailable")
    row = await db_pool.fetchrow("SELECT * FROM applications WHERE id=$1", case_id)
    if not row:
        raise HTTPException(404, f"Case {case_id} not found")
    events = await db_pool.fetch(
        "SELECT event,event_at,done FROM application_events WHERE case_id=$1 ORDER BY id",
        case_id,
    )
    return {
        "case_id":        case_id,
        "status":         _STATUS_DISPLAY.get(row["status"], row["status"].replace("_", " ").title()),
        "submitted_at":   row["submitted_at"].isoformat() if row["submitted_at"] else None,
        "applicant_name": row["full_name"],
        "message":        _STATUS_NOTES.get(row["status"], "Your application is being processed."),
        "timeline": [
            {
                "label": e["event"],
                "date":  e["event_at"].strftime("%d %b %Y") if e["event_at"] else "",
                "note":  "",
                "done":  e["done"],
            }
            for e in events
        ],
    }


@app.get("/api/v1/applications", tags=["applications"])
async def list_applications(status: str = Query("submitted,in_review"), limit: int = Query(50, le=200), _: dict = Depends(get_current_staff)):
    if not db_pool:
        raise HTTPException(503, "Database unavailable")
    statuses = [s.strip() for s in status.split(",") if s.strip()]
    rows = await db_pool.fetch(
        "SELECT id,status,full_name,date_of_birth,gender,phone,email,region,occupation,"
        "medical_data,risk_level,submitted_at,decided_at,reviewer_id FROM applications"
        " WHERE status = ANY($1::text[]) ORDER BY submitted_at DESC LIMIT $2",
        statuses, limit,
    )
    return {
        "applications": [
            {
                "id": r["id"], "status": r["status"], "full_name": r["full_name"],
                "date_of_birth": r["date_of_birth"], "gender": r["gender"],
                "phone": r["phone"], "email": r["email"], "region": r["region"],
                "occupation": r["occupation"],
                "medical_data": r["medical_data"] if isinstance(r["medical_data"], dict) else
                                (json.loads(r["medical_data"]) if r["medical_data"] else {}),
                "risk_level": r["risk_level"],
                "submitted_at": r["submitted_at"].isoformat() if r["submitted_at"] else None,
                "decided_at": r["decided_at"].isoformat() if r["decided_at"] else None,
                "reviewer_id": r["reviewer_id"],
            }
            for r in rows
        ],
        "total": len(rows),
    }


class DecisionBody(BaseModel):
    outcome: str   # approved | declined | referred
    notes: str = ""
    reviewer_id: str


@app.post("/api/v1/applications/{case_id}/decision", tags=["applications"])
async def record_decision(case_id: str, body: DecisionBody, _: dict = Depends(require_roles("admin", "underwriter"))):
    valid = {"approved", "declined", "referred"}
    if body.outcome not in valid:
        raise HTTPException(400, f"outcome must be one of {valid}")
    if not db_pool:
        raise HTTPException(503, "Database unavailable")
    now = datetime.now(timezone.utc)
    result = await db_pool.execute(
        "UPDATE applications SET status=$1,reviewer_id=$2,decision_notes=$3,decided_at=$4,updated_at=$4"
        " WHERE id=$5",
        body.outcome, body.reviewer_id, body.notes, now, case_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, f"Case {case_id} not found")
    await db_pool.execute(
        "INSERT INTO application_events(case_id,event,done,event_at) VALUES($1,$2,TRUE,$3)",
        case_id, f"Decision: {body.outcome} by {body.reviewer_id}", now,
    )
    return {"case_id": case_id, "status": body.outcome, "decided_at": now.isoformat()}


@app.post("/api/v1/documents/upload", tags=["applications"])
async def upload_document(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "image/jpeg", "image/png"):
        raise HTTPException(400, "Only PDF, JPEG, and PNG files are accepted")
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    await file.read()  # consume stream
    if db_pool:
        try:
            await db_pool.execute(
                "INSERT INTO documents(id,filename,upload_status) VALUES($1,$2,'uploaded')",
                doc_id, file.filename,
            )
        except Exception as e:
            log.warning(f"upload_document DB: {e}")
    return {"id": doc_id, "filename": file.filename, "status": "uploaded", "extracted": None}


# ── Public Advisor Chat ──────────────────────────────────────────────────────
ADVISOR_SYSTEM = """You are the DAC HealthPrice AI advisor — a friendly, knowledgeable assistant for customers applying for health insurance in Cambodia.

Your role:
- Help customers understand health insurance plans, pricing, coverage, and the application process
- Answer questions about DAC HealthPrice's specific offerings
- Guide customers through the portal (apply, track, documents)

Key product knowledge:
COVERAGE TIERS (IPD — inpatient hospital):
- Bronze: $18/month, $10,000 annual limit, $500 deductible
- Silver: $32/month, $40,000 annual limit, $250 deductible (most popular)
- Gold: $58/month, $80,000 annual limit, $100 deductible
- Platinum: $95/month, $150,000 annual limit, $0 deductible

OPTIONAL RIDERS (add to any tier):
- OPD (outpatient): +$12/month — doctor visits, lab tests, prescriptions
- Dental: +$6/month — cleanings, fillings, emergency dental
- Maternity: +$14/month — prenatal, delivery, postnatal, newborn care

UNDERWRITING FACTORS that may affect your premium:
- Smoking: +15–25%
- High BMI (>30): +10–20%
- Controlled hypertension: +10%
- Diabetes: may require exclusion or loading
- Cancer (within 5 years): case-by-case review

APPLICATION PROCESS:
1. Fill personal info and health profile (3 min)
2. Choose coverage tier and optional riders
3. Upload documents (National ID required; medical reports optional but speed up review)
4. Sign consent and submit — receive a case reference number immediately
5. Underwriting review: 3–5 business days
6. Decision: Approved / Declined / On Hold

DOCUMENTS NEEDED:
- National ID or Passport (required, front side)
- Medical reports from past 2 years (optional, speeds up review)
- Employer/income letter (optional, helps with group pricing)

CASE TRACKING: Customers use their case reference (format: DAC-XXXXXX) on the "Track My Case" page.

CONTACT: radet@dactuaries.com | +855 85 508 860 | Phnom Penh, Cambodia | Mon–Fri 8am–5pm ICT

Rules:
- Stay focused on health insurance and the DAC platform. Politely decline off-topic requests.
- Never give specific medical advice. Recommend consulting a doctor for medical questions.
- Keep responses concise (2–5 sentences). Use bullet points for structured lists.
- Be warm, professional, and clear — customers may be new to insurance.
- If asked something you don't know, say so and direct to radet@dactuaries.com."""

class AdvisorMessage(BaseModel):
    role: str
    content: str

_ADVISOR_MODELS = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-7",
}

class AdvisorChatRequest(BaseModel):
    messages: List[AdvisorMessage]
    context: dict = {}
    model: str = "haiku"

@app.post("/api/v1/advisor/chat", tags=["advisor"])
async def advisor_chat(body: AdvisorChatRequest, request: Request):
    ip = request.client.host or "anon"
    if not _rl(ip):
        raise HTTPException(429, "Too many requests. Please wait a moment.")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "Advisor service unavailable.")
    messages = [{"role": m.role, "content": m.content} for m in body.messages[-10:]]
    ctx_parts = []
    if body.context.get("tier"): ctx_parts.append(f"Customer selected {body.context['tier']} tier")
    if body.context.get("case_status"): ctx_parts.append(f"Case status: {body.context['case_status']}")
    if body.context.get("case_id"): ctx_parts.append(f"Case reference: {body.context['case_id']}")
    system = ADVISOR_SYSTEM + (f"\n\n[Current context: {'. '.join(ctx_parts)}.]" if ctx_parts else "")
    model_id = _ADVISOR_MODELS.get(body.model, _ADVISOR_MODELS["haiku"])
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "prompt-caching-2024-07-31",
                "content-type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 500,
                "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                "messages": messages,
            },
        )
    if r.status_code != 200:
        log.warning(f"Advisor chat error {r.status_code}: {r.text[:300]}")
        raise HTTPException(502, "Advisor temporarily unavailable.")
    data = r.json()
    reply = data["content"][0]["text"] if data.get("content") else "I'm sorry, I couldn't respond right now. Please try again or email radet@dactuaries.com."
    return {"reply": reply}


# ── Actuarial AI Lab ──────────────────────────────────────────────────────────
AILAB_SYSTEM_PROMPT = """You are DAC Actuarial AI Assistant — a specialized AI for actuarial data science.
You help actuaries clean data, run EDA, build frequency-severity models, calculate premiums, and do experience studies.

RULES:
1. Always load data with: df = pd.read_csv("/tmp/ailab_data/{filename}")
2. For charts, ALWAYS use UNIQUE filenames: plt.savefig("/tmp/ailab_output/chart_01_description.png", dpi=150, bbox_inches="tight") then plt.close()
3. NEVER use plt.show() — always savefig + close
4. Print results clearly with labels
5. Return ONLY ONE python code block — never split into multiple blocks
6. For frequency models: use Poisson GLM (sklearn PoissonRegressor)
7. For severity models: use Gamma GLM or GradientBoostingRegressor
8. Pure premium = E[frequency] × E[severity]
9. Always show model diagnostics: coefficients, feature importance, R², deviance
10. For experience studies: calculate A/E ratios (actual vs expected)
11. Use professional formatting — add titles, axis labels, legends to all charts
12. When cleaning data: show before/after counts, handle missing values, detect outliers

Available data columns will be provided in the user message.
The code will be executed automatically in a Python environment with pandas, numpy, sklearn, statsmodels, matplotlib, seaborn available."""

AILAB_UPLOAD_DIR = "/tmp/ailab_data"
AILAB_OUTPUT_DIR = "/tmp/ailab_output"
_ailab_files: dict = {}

async def _save_ailab_to_db(fname: str, file_bytes: bytes, meta: dict):
    """Save uploaded file to PostgreSQL so it survives Render redeploys."""
    if not db_pool:
        return
    try:
        await db_pool.execute(
            """INSERT INTO ailab_files (filename, file_data, meta)
               VALUES ($1, $2, $3::jsonb)
               ON CONFLICT (filename) DO UPDATE SET file_data=$2, meta=$3::jsonb, uploaded_at=NOW()""",
            fname, file_bytes, json.dumps(meta)
        )
        log.info(f"AI Lab: saved {fname} to DB ({len(file_bytes)} bytes)")
    except Exception as e:
        log.warning(f"AI Lab DB save failed: {e}")

async def _restore_ailab_from_db():
    """On startup, restore AI Lab files from DB to /tmp so they're available for execution."""
    global _ailab_files
    if not db_pool:
        return
    rows = await db_pool.fetch("SELECT filename, file_data, meta FROM ailab_files")
    if not rows:
        return
    os.makedirs(AILAB_UPLOAD_DIR, exist_ok=True)
    for r in rows:
        fname = r["filename"]
        fpath = os.path.join(AILAB_UPLOAD_DIR, fname)
        with open(fpath, "wb") as f:
            f.write(r["file_data"])
        _ailab_files[fname] = json.loads(r["meta"]) if isinstance(r["meta"], str) else dict(r["meta"])
    log.info(f"AI Lab: restored {len(rows)} file(s) from DB")

@app.post("/api/v2/ailab/upload")
async def ailab_upload(file: UploadFile = File(...)):
    import pandas as pd
    os.makedirs(AILAB_UPLOAD_DIR, exist_ok=True)
    os.makedirs(AILAB_OUTPUT_DIR, exist_ok=True)
    fname = file.filename
    content = await file.read()
    if len(content) > 52428800:
        raise HTTPException(413, "File too large (max 50MB)")
    fpath = os.path.join(AILAB_UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        f.write(content)
    meta = {"filename": fname, "size": len(content), "rows": None, "columns": [], "dtypes": {}, "missing": {}, "numeric_summary": {}}
    try:
        if fname.endswith(".csv"):
            df = pd.read_csv(fpath)
        elif fname.endswith((".xlsx", ".xls")):
            df = pd.read_excel(fpath)
        else:
            _ailab_files[fname] = meta
            await _save_ailab_to_db(fname, content, meta)
            return {"status": "uploaded", "meta": meta}
        meta["rows"] = len(df)
        meta["columns"] = list(df.columns)
        meta["dtypes"] = {c: str(df[c].dtype) for c in df.columns}
        meta["missing"] = {c: int(df[c].isnull().sum()) for c in df.columns if df[c].isnull().sum() > 0}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            meta["numeric_summary"] = df[numeric_cols].describe().round(2).to_dict()
        _ailab_files[fname] = meta
        await _save_ailab_to_db(fname, content, meta)
        preview = df.head(10).fillna("").to_dict(orient="records")
        return {"status": "uploaded", "meta": meta, "preview": preview}
    except Exception as e:
        return {"status": "uploaded_parse_error", "meta": meta, "error": str(e)}

@app.post("/api/v2/ailab/analyze")
async def ailab_analyze(request: Request):
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(503, "AI not configured — set ANTHROPIC_API_KEY or GROQ_API_KEY env var")
    body = await request.json()
    user_message = body.get("message", "")
    history = body.get("history", [])
    filename = body.get("filename", "")
    data_context = ""
    if filename and filename in _ailab_files:
        m = _ailab_files[filename]
        data_context = f"\n\nUploaded file: {filename}\nRows: {m.get('rows', '?')}\nColumns: {m.get('columns', [])}\nData types: {m.get('dtypes', {})}\nMissing values: {m.get('missing', {})}\nNumeric summary: {json.dumps(m.get('numeric_summary', {}), indent=2)}"
    system_prompt = AILAB_SYSTEM_PROMPT + data_context

    if os.getenv("ANTHROPIC_API_KEY"):
        messages = []
        for msg in history[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-20250514", "max_tokens": 4096, "system": system_prompt, "messages": messages},
                )
            data = r.json()
            if "error" in data:
                raise HTTPException(502, f"AI error: {data['error'].get('message', 'Unknown')}")
            ai_response = data["content"][0]["text"]
            return {"response": ai_response, "has_code": "```python" in ai_response}
        except httpx.TimeoutException:
            raise HTTPException(504, "AI response timed out")
        except HTTPException: raise
        except Exception as e:
            log.error(f"AI Lab error: {e}"); raise HTTPException(500, "AI analysis failed")
    else:
        openai_msgs = [{"role": "system", "content": system_prompt}]
        for msg in history[-20:]:
            openai_msgs.append({"role": msg["role"], "content": msg["content"]})
        openai_msgs.append({"role": "user", "content": user_message})
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": "llama-3.3-70b-versatile", "messages": openai_msgs, "max_tokens": 2000, "temperature": 0.1},
                )
            data = r.json()
            if "error" in data:
                raise HTTPException(502, f"AI error: {data['error'].get('message', 'Unknown')}")
            ai_response = data["choices"][0]["message"]["content"]
            return {"response": ai_response, "has_code": "```python" in ai_response}
        except httpx.TimeoutException:
            raise HTTPException(504, "AI response timed out")
        except HTTPException: raise
        except Exception as e:
            log.error(f"AI Lab error: {e}"); raise HTTPException(500, "AI analysis failed")

@app.post("/api/v2/ailab/execute")
async def ailab_execute(request: Request):
    body = await request.json()
    code = body.get("code", "")
    if not code: raise HTTPException(400, "No code provided")
    os.makedirs(AILAB_OUTPUT_DIR, exist_ok=True)
    for f in os.listdir(AILAB_OUTPUT_DIR):
        try: os.remove(os.path.join(AILAB_OUTPUT_DIR, f))
        except: pass
    wrapped = f"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')
import os
os.makedirs('/tmp/ailab_output', exist_ok=True)

try:
{chr(10).join('    ' + line for line in code.split(chr(10)))}
except Exception as e:
    print(f"ERROR: {{e}}")
"""
    script_path = os.path.join(tempfile.gettempdir(), "ailab_script.py")
    with open(script_path, "w") as f:
        f.write(wrapped)
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "MPLBACKEND": "Agg"}
        )
        stdout = result.stdout[:50000]
        stderr = result.stderr[:10000] if result.returncode != 0 else ""
        charts = []
        if os.path.exists(AILAB_OUTPUT_DIR):
            for fname in sorted(os.listdir(AILAB_OUTPUT_DIR)):
                fpath = os.path.join(AILAB_OUTPUT_DIR, fname)
                if fname.endswith((".png", ".jpg", ".svg")):
                    with open(fpath, "rb") as img:
                        b64 = base64.b64encode(img.read()).decode()
                        charts.append({"filename": fname, "data": f"data:image/png;base64,{b64}"})
        return {"stdout": stdout, "stderr": stderr, "returncode": result.returncode, "charts": charts, "success": result.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Execution timed out (120s limit)", "returncode": 1, "charts": [], "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": 1, "charts": [], "success": False}

@app.get("/api/v2/ailab/files")
async def ailab_list_files():
    return {"files": list(_ailab_files.values())}


@app.exception_handler(Exception)
async def err(request:Request,exc:Exception):
    rid=getattr(request.state,"rid","?") if hasattr(request,"state") else "?"
    log.error(f"[{rid}] {exc}",exc_info=True)
    return JSONResponse(500,{"detail":"Internal server error","request_id":rid})
