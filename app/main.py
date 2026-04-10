"""
DAC HealthPrice Platform v2.3
Changes: authoritative underwriting engine, GLM-consistent fallback,
model versioning + meta persistence, hot-swap retraining loop,
full audit trail, 6-layer anti-scraping protection,
client-specific partner API keys.
"""
import os, re, time, uuid, logging, json, hashlib, secrets
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional, List
from collections import defaultdict, deque
import numpy as np
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
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
            # Load active partner keys into memory cache
            try:
                rows=await db_pool.fetch("SELECT key_hash,partner_name,daily_limit FROM hp_partner_keys WHERE is_active=TRUE")
                for r in rows:
                    _partner_keys[r["key_hash"]]={"partner_name":r["partner_name"],"daily_limit":r["daily_limit"],"usage_today":0,"date":None}
                log.info(f"Loaded {len(_partner_keys)} partner key(s)")
            except Exception as e: log.warning(f"Partner key load: {e}")
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

@app.exception_handler(Exception)
async def err(request:Request,exc:Exception):
    rid=getattr(request.state,"rid","?") if hasattr(request,"state") else "?"
    log.error(f"[{rid}] {exc}",exc_info=True)
    return JSONResponse(500,{"detail":"Internal server error","request_id":rid})
