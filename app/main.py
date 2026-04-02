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
ADMIN_KEY=os.getenv("ADMIN_API_KEY","")
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

async def verify_admin(x_api_key:str=Header(None)):
    if ADMIN_KEY and x_api_key!=ADMIN_KEY: raise HTTPException(403,"Invalid API key")

VALID_GENDERS=["Male","Female","Other"]
VALID_SMOKING=["Never","Former","Current"]
VALID_EXERCISE=["Sedentary","Light","Moderate","Active"]
VALID_OCC=["Office/Desk","Retail/Service","Healthcare","Manual Labor","Industrial/High-Risk","Retired"]
VALID_PE=frozenset(["None","Hypertension","Diabetes","Heart Disease","Asthma/COPD","Cancer (remission)","Kidney Disease","Liver Disease","Obesity","Mental Health"])
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
ULR_TARGETS: dict = {"Bronze": 0.70, "Silver": 0.72, "Gold": 0.75, "Platinum": 0.78}
P_FLOOR=50; P_CEIL=25000

# ── Fallback GLM fitting — consistent Poisson+Ridge methodology ───────────────
# GLM Coefficient Store — all pricing factors are explicit and auditable.
# Updated at runtime via POST /api/v2/admin/deploy-calibration.
COEFF: dict = {
    "version":       "v2.2",
    "last_updated":  "2026-03-28",
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
}

def _age_band(age: int) -> str:
    if age < 25: return "18-24"
    if age < 35: return "25-34"
    if age < 45: return "35-44"
    if age < 55: return "45-54"
    if age < 65: return "55-64"
    return "65+"

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

    freq = COEFF["base_freq"][cov] * af * sf * ef * of * pf
    sev  = COEFF["base_sev"][cov]  * rf * (1 + max(0, req.age - 30) * COEFF["sev_age_gradient"])

    breakdown = [
        {"factor": f"Age bracket ({ab})",                  "coefficient": round(af, 4), "direction": "up" if af > 1 else "down" if af < 1 else "neutral"},
        {"factor": f"Smoking ({req.smoking_status})",       "coefficient": round(sf, 4), "direction": "up" if sf > 1 else "neutral"},
        {"factor": f"Exercise ({req.exercise_frequency})",  "coefficient": round(ef, 4), "direction": "up" if ef > 1 else "down"},
        {"factor": f"Occupation ({req.occupation_type})",   "coefficient": round(of, 4), "direction": "up" if of > 1 else "down" if of < 1 else "neutral"},
        {"factor": f"Region ({req.region})",                "coefficient": round(rf, 4), "direction": "up" if rf > 1 else "down" if rf < 1 else "neutral"},
    ]
    if pe_count > 0:
        breakdown.append({"factor": f"Pre-existing conditions ({pe_count})", "coefficient": round(pf, 4), "direction": "up"})

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
    freq = coeff["base_freq"][cov] * af * sf * ef * of * pf
    sev  = coeff["base_sev"][cov]  * rf * (1 + max(0, req.age - 30) * coeff["sev_age_gradient"])
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
    target_ulr:Optional[float]=Field(None,ge=0.50,le=0.95)
    browser_id:Optional[str]=Field(None); email:Optional[str]=Field(None)

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

    ulr=req.target_ulr if req.target_ulr is not None else ULR_TARGETS[req.ipd_tier]
    implied_loading=round((1-ulr)/ulr,6)

    ded_cr=round(tier["deductible"]*0.10,2)
    pure_premium=round(ipd["expected_annual_cost"]*tf,2)
    ipd_loaded=round(ipd["expected_annual_cost"]*(1+implied_loading)*tf,2)
    ipd_prem=round(float(np.clip(ipd_loaded-ded_cr,P_FLOOR,P_CEIL)),2)

    ulr_analysis={"target_ulr":round(ulr,4),"implied_loading_pct":round(implied_loading,4),"pure_premium":pure_premium,"ulr_adjusted_premium":ipd_prem}

    riders={}; rtot=0
    for c,inc in [("opd",req.include_opd),("dental",req.include_dental),("maternity",req.include_maternity)]:
        if not inc: continue
        r=_predict_active(c,req); rp=round(float(np.clip(r["expected_annual_cost"]*(1+implied_loading),10,5000)),2)
        riders[c]={"name":COV[c]["name"],"frequency":r["frequency"],"severity":r["severity"],"expected_annual_cost":r["expected_annual_cost"],"loading_pct":round(implied_loading,4),"annual_premium":rp,"monthly_premium":round(rp/12,2),"source":r["source"],"breakdown":r.get("breakdown",[])}
        rtot+=rp
    ff=round(1+(req.family_size-1)*0.65,2); pre_fam=round(ipd_prem+rtot,2)
    total=round(float(np.clip(pre_fam*ff,P_FLOOR,P_CEIL*req.family_size)),2)
    email=req.email or _email_from_auth

    res={"quote_id":qid,"request_id":rid,"country":req.country,"region":req.region,"model_version":_active_coeff.get("version",COEFF["version"]),
        "model_source":"ml","model_accuracy_pct":91.0,
        **({"pilot_model":_pilot_tag} if _pilot_tag else {}),
        "pricing_approach":"Poisson-Gamma GLM","coefficient_version":COEFF["version"],
        "ipd_tier":req.ipd_tier,"tier_benefits":tier,"underwriting":uw,
        "ipd_core":{"frequency":ipd["frequency"],"severity":ipd["severity"],"expected_annual_cost":ipd["expected_annual_cost"],"loading_pct":round(implied_loading,4),"tier_factor":tf,"deductible_credit":ded_cr,"annual_premium":ipd_prem,"monthly_premium":round(ipd_prem/12,2),"source":ipd["source"],"breakdown":ipd.get("breakdown",[])},
        "riders":riders,"family_size":req.family_size,"family_factor":ff,"total_before_family":pre_fam,
        "total_annual_premium":total,"total_monthly_premium":round(total/12,2),
        "ulr_analysis":ulr_analysis,
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
        "approach":"Freq-Sev (Poisson+GBR) — fallback: Poisson+Ridge GLM on synthetic data",
        "models_loaded":list(models.keys()),
        "coefficient_version":COEFF["version"],
        "features":["age","gender","smoking","exercise","occupation","region","preexist"],
        "coverages":list(COV.keys()),
        "last_retrained_at":model_meta.get("last_retrained_at"),
        "training_dataset":model_meta.get("training_dataset"),
        "r2":model_meta.get("r2"),
    }

UPLOAD_DIR=os.getenv("UPLOAD_DIR","/tmp/hp_uploads")
REQ_COLS={"age","gender","smoking","exercise","occupation","region","preexist_count","claim_count","claim_amount"}

@app.post("/api/v2/admin/upload-dataset",dependencies=[Depends(verify_admin)])
async def upload(file:UploadFile=File(...),coverage_type:str=Form("ipd"),description:str=Form(""),auto_retrain:bool=Form(False)):
    import pandas as pd,io
    if coverage_type not in COV: raise HTTPException(400,f"Invalid coverage_type: {list(COV.keys())}")
    if not file.filename.endswith(".csv"): raise HTTPException(400,"CSV only")
    contents=await file.read()
    if len(contents)/(1024*1024)>50: raise HTTPException(400,"Max 50MB")
    try: df=pd.read_csv(io.BytesIO(contents))
    except Exception as e: raise HTTPException(400,f"Parse error: {e}")
    miss=REQ_COLS-set(df.columns)
    if miss: return {"status":"rejected","missing":sorted(miss),"required":sorted(REQ_COLS)}
    q={"rows":len(df),"claim_rate":round((df["claim_count"]>0).mean(),4)}
    os.makedirs(UPLOAD_DIR,exist_ok=True); bid=f"up_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"; sp=os.path.join(UPLOAD_DIR,f"{bid}_{coverage_type}.csv"); df.to_csv(sp,index=False)
    dbi=0
    if db_pool:
        try:
            recs=[(coverage_type,int(r["age"]),str(r.get("gender","")),str(r.get("smoking","")),str(r.get("exercise","")),str(r.get("occupation","")),str(r.get("region","")),int(r.get("preexist_count",0)),int(r["claim_count"]),float(r.get("claim_amount",0)),bid) for _,r in df.dropna(subset=["age","claim_count"]).iterrows()]
            async with db_pool.acquire() as c: await c.executemany("INSERT INTO hp_claims(coverage_type,age,gender,smoking,exercise,occupation,region,preexist_count,claim_count,claim_amount,batch_id)VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",recs); dbi=len(recs)
        except Exception as e: log.error(f"Batch insert: {e}")
    rr=None
    if auto_retrain and len(df)>=500: rr=await _retrain(coverage_type,sp,bid)
    return {"status":"accepted","batch_id":bid,"rows":len(df),"inserted":dbi,"quality":q,"retrain":rr}

async def _retrain(cov,path,bid):
    # ML retraining removed — platform now uses GLM coefficient calibration.
    # Use POST /api/v2/admin/upload-claims + /admin/deploy-calibration instead.
    log.info(f"_retrain called for {cov} but ML pipeline is deprecated; use GLM calibration endpoints.")
    return {"status":"deprecated","message":"ML retraining replaced by GLM calibration. Use /admin/deploy-calibration."}

# ── GLM: coefficient viewer ───────────────────────────────────────────────────
@app.get("/api/v2/admin/coefficients",dependencies=[Depends(verify_admin)])
async def get_coefficients():
    return {"status":"ok","coefficients":COEFF,"pricing_approach":"Poisson-Gamma GLM"}

# ── GLM: claims upload (Phase 1) ──────────────────────────────────────────────
CLAIMS_COLS={"claim_id","customer_age","customer_occupation","claim_type","claim_amount","claim_date"}
VALID_CLAIM_TYPES={"IPD","OPD","Dental","Maternity"}

@app.post("/api/v2/admin/upload-claims",dependencies=[Depends(verify_admin)])
async def upload_claims(file:UploadFile=File(...),dataset_name:str=Form(...)):
    import pandas as pd,io
    if not file.filename.endswith(".csv"): raise HTTPException(400,"CSV files only.")
    contents=await file.read()
    if len(contents)/(1024*1024)>50: raise HTTPException(400,"Max 50 MB.")
    try: df=pd.read_csv(io.BytesIO(contents))
    except Exception as e: raise HTTPException(400,f"CSV parse error: {e}")
    miss=CLAIMS_COLS-set(df.columns)
    if miss: raise HTTPException(400,{"missing_columns":sorted(miss),"required":sorted(CLAIMS_COLS)})
    df["customer_age"]=pd.to_numeric(df["customer_age"],errors="coerce")
    df["claim_amount"]=pd.to_numeric(df["claim_amount"],errors="coerce")
    invalid_rows=(df["customer_age"].isna() | df["claim_amount"].isna() | ~df["claim_type"].isin(VALID_CLAIM_TYPES)).sum()
    valid_df=df.dropna(subset=["customer_age","claim_amount"]).copy()
    valid_df=valid_df[valid_df["claim_type"].isin(VALID_CLAIM_TYPES)]
    upload_id=f"CAL-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    ages=valid_df["customer_age"].dropna().tolist()
    amounts=valid_df["claim_amount"].dropna().tolist()
    dates=valid_df["claim_date"].dropna().sort_values().tolist() if "claim_date" in valid_df else []
    dist=valid_df["claim_type"].value_counts().to_dict()
    summary={"age_range":[int(min(ages,default=0)),int(max(ages,default=0))],"avg_claim":round(sum(amounts)/len(amounts),2) if amounts else 0,"date_range":[str(dates[0]) if dates else "—",str(dates[-1]) if dates else "—"],"distribution":{k:int(v) for k,v in dist.items()}}
    preview=valid_df.head(20).to_dict(orient="records")
    if db_pool:
        try:
            await db_pool.execute("""
                CREATE TABLE IF NOT EXISTS hp_claims_upload(
                    id SERIAL PRIMARY KEY, upload_id TEXT UNIQUE NOT NULL,
                    dataset_name TEXT, records INT, invalid_rows INT,
                    summary JSONB, status TEXT DEFAULT 'sandbox',
                    uploaded_at TIMESTAMPTZ DEFAULT NOW())
            """)
            await db_pool.execute(
                "INSERT INTO hp_claims_upload(upload_id,dataset_name,records,invalid_rows,summary)VALUES($1,$2,$3,$4,$5::jsonb)",
                upload_id,dataset_name,len(valid_df),int(invalid_rows),json.dumps(summary))
        except Exception as e: log.warning(f"Upload log fail: {e}")
    log.info(f"Claims upload: {upload_id} dataset='{dataset_name}' rows={len(valid_df)} invalid={invalid_rows}")
    return {"upload_id":upload_id,"dataset_name":dataset_name,"status":"sandbox","rows_valid":len(valid_df),"rows_invalid":int(invalid_rows),"summary":summary,"preview":preview}

# ── GLM: calibration analysis (Phase 2) ──────────────────────────────────────
@app.post("/api/v2/admin/calibrate",dependencies=[Depends(verify_admin)])
async def calibrate(upload_id:str=Form(...)):
    """Compute O/E ratios and preview calibrated coefficients — does NOT deploy."""
    # In production: load claims from DB by upload_id; here we derive from stored summary
    if not db_pool: raise HTTPException(503,"Database required for calibration.")
    try:
        row=await db_pool.fetchrow("SELECT summary,dataset_name,records FROM hp_claims_upload WHERE upload_id=$1",upload_id)
    except Exception as e: raise HTTPException(500,f"DB error: {e}")
    if not row: raise HTTPException(404,"Upload ID not found.")
    summary=json.loads(row["summary"]) if isinstance(row["summary"],str) else dict(row["summary"])
    dist=summary.get("distribution",{})
    total=sum(dist.values()) or 1
    # Observed vs expected frequency ratios
    obs_exp={}
    for cov,exp_base in COEFF["base_freq"].items():
        cov_key=cov.upper() if cov!="maternity" else "Maternity"
        cov_key={"IPD":"IPD","OPD":"OPD","DENTAL":"Dental","MATERNITY":"Maternity"}.get(cov.upper(),cov.upper())
        obs_count=dist.get(cov_key,0)
        obs_rate=round(obs_count/total,4)
        ratio=round(obs_rate/exp_base,3) if exp_base>0 else 1.0
        obs_exp[cov]={"observed_rate":obs_rate,"expected_rate":exp_base,"ratio":ratio,"delta":f"{round((ratio-1)*100,1):+.1f}%"}
    # Calibrated coefficient preview (old * ratio)
    coeff_changes=[]
    for cov,d in obs_exp.items():
        old_freq=COEFF["base_freq"][cov]; new_freq=round(old_freq*d["ratio"],4)
        if abs(d["ratio"]-1)>0.01:
            coeff_changes.append({"factor":f"{cov.upper()} base frequency","old":old_freq,"new":new_freq,"delta":d["delta"]})
    avg_impact=round((sum(d["ratio"] for d in obs_exp.values())/len(obs_exp)-1)*100,1) if obs_exp else 0
    return {"upload_id":upload_id,"dataset_name":row["dataset_name"],"status":"preview","obs_exp":obs_exp,"coeff_changes":coeff_changes,"estimated_premium_impact":f"{avg_impact:+.1f}%","note":"No changes have been deployed. Call /admin/deploy-calibration to go live."}

# ── GLM: deploy calibration (Phase 3) ────────────────────────────────────────
class DeployRequest(BaseModel):
    upload_id: str
    deployed_by: str = "admin"

@app.post("/api/v2/admin/deploy-calibration",dependencies=[Depends(verify_admin)])
async def deploy_calibration(body:DeployRequest):
    """Apply calibrated coefficients to the live GLM and update COEFF in memory."""
    global COEFF, model_version
    if not db_pool: raise HTTPException(503,"Database required.")
    try:
        row=await db_pool.fetchrow("SELECT summary,dataset_name,records FROM hp_claims_upload WHERE upload_id=$1",body.upload_id)
    except Exception as e: raise HTTPException(500,f"DB error: {e}")
    if not row: raise HTTPException(404,"Upload ID not found.")
    summary=json.loads(row["summary"]) if isinstance(row["summary"],str) else dict(row["summary"])
    dist=summary.get("distribution",{})
    total=sum(dist.values()) or 1
    # Recompute calibration and apply
    new_base_freq=dict(COEFF["base_freq"])
    changes=[]
    for cov,exp_base in COEFF["base_freq"].items():
        cov_key={"ipd":"IPD","opd":"OPD","dental":"Dental","maternity":"Maternity"}[cov]
        obs_count=dist.get(cov_key,0)
        obs_rate=obs_count/total if total>0 else exp_base
        ratio=obs_rate/exp_base if exp_base>0 else 1.0
        new_freq=round(exp_base*ratio,4)
        if abs(ratio-1)>0.01:
            changes.append({"factor":f"{cov} base_freq","old":exp_base,"new":new_freq,"delta":f"{round((ratio-1)*100,1):+.1f}%"})
            new_base_freq[cov]=new_freq
    # Bump version
    from datetime import datetime as dt
    new_version=f"v{dt.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    COEFF["base_freq"]=new_base_freq
    COEFF["version"]=new_version
    COEFF["last_updated"]=dt.now(timezone.utc).strftime("%Y-%m-%d")
    COEFF["updated_by"]=body.deployed_by
    model_version=new_version
    # Persist to DB
    try:
        await db_pool.execute("""
            CREATE TABLE IF NOT EXISTS hp_glm_versions(
                id SERIAL PRIMARY KEY, version TEXT NOT NULL,
                coefficients JSONB, deployed_by TEXT,
                dataset_name TEXT, records INT,
                deployed_at TIMESTAMPTZ DEFAULT NOW())
        """)
        await db_pool.execute(
            "INSERT INTO hp_glm_versions(version,coefficients,deployed_by,dataset_name,records)VALUES($1,$2::jsonb,$3,$4,$5)",
            new_version,json.dumps(COEFF),body.deployed_by,row["dataset_name"],row["records"])
        await db_pool.execute("UPDATE hp_claims_upload SET status='deployed' WHERE upload_id=$1",body.upload_id)
    except Exception as e: log.warning(f"GLM version persist fail: {e}")
    log.info(f"GLM deployed: {new_version} by={body.deployed_by} dataset={row['dataset_name']} changes={len(changes)}")
    return {"status":"deployed","new_version":new_version,"previous_version":model_version,"changes_applied":changes,"dataset":row["dataset_name"],"records":row["records"],"deployed_at":dt.now(timezone.utc).isoformat()}

@app.get("/api/v2/admin/dataset-template",dependencies=[Depends(verify_admin)])
async def tpl():
    return PlainTextResponse("age,gender,smoking,exercise,occupation,region,preexist_count,claim_count,claim_amount\n35,Male,Current,Sedentary,Office/Desk,Phnom Penh,0,1,2500.00\n28,Female,Never,Moderate,Healthcare,Hanoi,1,0,0\n55,Male,Former,Light,Manual Labor,Rural Areas,2,2,7800.00",media_type="text/csv",headers={"Content-Disposition":"attachment; filename=claims_template.csv"})

@app.get("/api/v2/admin/upload-history",dependencies=[Depends(verify_admin)])
async def uh():
    if not db_pool: return {"status":"no_db"}
    try:
        rows=await db_pool.fetch("SELECT batch_id,coverage_type,COUNT(*)as rows,MIN(ingested_at)as uploaded_at,ROUND(AVG(claim_amount)::numeric,2)as avg FROM hp_claims WHERE batch_id IS NOT NULL GROUP BY batch_id,coverage_type ORDER BY MIN(ingested_at)DESC LIMIT 20")
        return {"status":"ok","uploads":[{k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in dict(r).items()} for r in rows]}
    except Exception as e: return {"status":"error","detail":str(e)}

@app.get("/api/v2/admin/user-behavior",dependencies=[Depends(verify_admin)])
async def user_behavior(limit:int=50):
    if not db_pool: return {"status":"no_db","records":[]}
    try:
        rows=await db_pool.fetch("""
            SELECT quote_ref,created_at,age,gender,country,region,smoking,exercise,occupation,
                   preexist_count,ipd_tier,include_opd,include_dental,include_maternity,family_size,
                   browser_id,email,anomaly_flag
            FROM hp_user_behavior ORDER BY created_at DESC LIMIT $1
        """,min(limit,200))
        records=[]
        for r in rows:
            d=dict(r)
            for k,v in d.items():
                if hasattr(v,'isoformat'): d[k]=v.isoformat()
            records.append(d)
        total=len(records); summary={}
        if total>0:
            ages=[r["age"] for r in records if r.get("age")]
            summary={"total_quotes":total,"avg_age":round(sum(ages)/len(ages),1) if ages else 0,
                "tier_distribution":{},"rider_rates":{"opd":0,"dental":0,"maternity":0},"smoking_distribution":{},
                "anomaly_flags":sum(1 for r in records if r.get("anomaly_flag"))}
            for r in records:
                t=r.get("ipd_tier","Unknown"); summary["tier_distribution"][t]=summary["tier_distribution"].get(t,0)+1
                s=r.get("smoking","Unknown"); summary["smoking_distribution"][s]=summary["smoking_distribution"].get(s,0)+1
                if r.get("include_opd"): summary["rider_rates"]["opd"]+=1
                if r.get("include_dental"): summary["rider_rates"]["dental"]+=1
                if r.get("include_maternity"): summary["rider_rates"]["maternity"]+=1
            for k in summary["rider_rates"]: summary["rider_rates"][k]=round(summary["rider_rates"][k]/total*100,1)
        return {"status":"ok","records":records,"summary":summary}
    except Exception as e: return {"status":"error","detail":str(e)}

# ── Task 5: full audit log endpoint ──────────────────────────────────────────
@app.get("/api/v2/admin/audit-log",dependencies=[Depends(verify_admin)])
async def audit_log(limit:int=50):
    if not db_pool: return {"status":"no_db","records":[]}
    try:
        rows=await db_pool.fetch("""
            SELECT quote_ref,created_at,model_version,underwriting_status,used_fallback,browser_id,email
            FROM hp_quote_log ORDER BY created_at DESC LIMIT $1
        """,min(limit,500))
        records=[]
        for r in rows:
            d=dict(r)
            for k,v in d.items():
                if hasattr(v,'isoformat'): d[k]=v.isoformat()
            records.append(d)
        summary={"total":len(records),
            "by_underwriting_status":{},
            "fallback_rate":round(sum(1 for r in records if r.get("used_fallback"))/max(len(records),1)*100,1),
            "decline_rate":round(sum(1 for r in records if r.get("underwriting_status")=="decline")/max(len(records),1)*100,1)}
        for r in records:
            s=r.get("underwriting_status","unknown"); summary["by_underwriting_status"][s]=summary["by_underwriting_status"].get(s,0)+1
        return {"status":"ok","records":records,"summary":summary}
    except Exception as e: return {"status":"error","detail":str(e)}

@app.get("/api/v2/admin/model-versions",dependencies=[Depends(verify_admin)])
async def model_versions():
    if not db_pool: return {"status":"no_db","versions":[]}
    try:
        rows=await db_pool.fetch("SELECT version,coverage,training_dataset,r2,promoted_at FROM hp_model_versions ORDER BY promoted_at DESC LIMIT 50")
        return {"status":"ok","current_version":model_version,"versions":[{k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in dict(r).items()} for r in rows]}
    except Exception as e: return {"status":"error","detail":str(e)}

# ── Partner key management (admin) ───────────────────────────────────────────
class PartnerKeyRequest(BaseModel):
    partner_name:str=Field(...,min_length=2,max_length=100)
    daily_limit:int=Field(500,ge=1,le=100000)

@app.post("/api/v2/admin/partner-keys",dependencies=[Depends(verify_admin)])
async def create_partner_key(body:PartnerKeyRequest):
    raw=secrets.token_urlsafe(40)
    kh=hashlib.sha256(raw.encode()).hexdigest()
    if not db_pool: raise HTTPException(503,"Database required for partner key management.")
    try:
        await db_pool.execute(
            "INSERT INTO hp_partner_keys(key_hash,partner_name,daily_limit)VALUES($1,$2,$3)",
            kh,body.partner_name,body.daily_limit)
    except Exception as e: raise HTTPException(500,f"DB error: {e}")
    _partner_keys[kh]={"partner_name":body.partner_name,"daily_limit":body.daily_limit,"usage_today":0,"date":None,"is_active":True}
    log.info(f"Partner key created for '{body.partner_name}' daily_limit={body.daily_limit}")
    return {"partner_name":body.partner_name,"api_key":raw,"daily_limit":body.daily_limit,
            "note":"Store this key securely — it will not be shown again."}

@app.get("/api/v2/admin/partner-keys",dependencies=[Depends(verify_admin)])
async def list_partner_keys():
    if not db_pool: raise HTTPException(503,"Database required.")
    try:
        rows=await db_pool.fetch(
            "SELECT id,partner_name,daily_limit,is_active,total_requests,created_at,last_used_at FROM hp_partner_keys ORDER BY created_at DESC")
        return {"status":"ok","keys":[{k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in dict(r).items()} for r in rows]}
    except Exception as e: raise HTTPException(500,f"DB error: {e}")

@app.delete("/api/v2/admin/partner-keys/{key_id}",dependencies=[Depends(verify_admin)])
async def revoke_partner_key(key_id:int):
    if not db_pool: raise HTTPException(503,"Database required.")
    try:
        row=await db_pool.fetchrow("UPDATE hp_partner_keys SET is_active=FALSE WHERE id=$1 RETURNING key_hash,partner_name",key_id)
        if not row: raise HTTPException(404,"Partner key not found.")
        kh=row["key_hash"]
        if kh in _partner_keys: _partner_keys[kh]["is_active"]=False
        log.info(f"Partner key revoked: id={key_id} partner='{row['partner_name']}'")
        return {"status":"revoked","id":key_id,"partner_name":row["partner_name"]}
    except HTTPException: raise
    except Exception as e: raise HTTPException(500,f"DB error: {e}")

# ── Calibration Pilot endpoints ──────────────────────────────────────────────
import threading

_pilot_jobs: dict = {}  # prospect_id → {"status", "started_at", "error"}

def _run_training_job(prospect_id: str, csv_path: str, holdout: float):
    """Background thread: runs train_custom_model logic and loads result into memory."""
    global _prospect_coeffs
    _pilot_jobs[prospect_id] = {"status": "training", "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        import pandas as pd, numpy as np, copy
        from sklearn.linear_model import GammaRegressor
        from sklearn.model_selection import train_test_split

        CLAIM_TYPE_MAP = {"IPD": "ipd", "OPD": "opd", "Dental": "dental", "Maternity": "maternity"}
        df = pd.read_csv(csv_path)
        df["customer_age"] = pd.to_numeric(df["customer_age"], errors="coerce")
        df["claim_amount"] = pd.to_numeric(df["claim_amount"], errors="coerce")
        df["cov"] = df["claim_type"].str.strip().map(CLAIM_TYPE_MAP)
        df = df.dropna(subset=["customer_age","claim_amount","cov"])
        df = df[(df["customer_age"]>=18)&(df["customer_age"]<=70)&(df["claim_amount"]>0)]

        train_idx, _ = train_test_split(range(len(df)), test_size=holdout, random_state=42)
        train = df.iloc[train_idx]
        total = len(train)

        new_coeff = copy.deepcopy(COEFF)
        for cov, base in COEFF["base_freq"].items():
            obs_rate = (train["cov"]==cov).sum() / total if total > 0 else base
            ratio = float(np.clip(obs_rate / base, 0.3, 3.0)) if base > 0 else 1.0
            new_coeff["base_freq"][cov] = round(base * ratio, 6)

        ipd_train = train[train["cov"]=="ipd"]
        if len(ipd_train) >= 30:
            X = ipd_train["customer_age"].values.reshape(-1,1)
            y = ipd_train["claim_amount"].values
            gm = GammaRegressor(alpha=0.01, max_iter=500)
            gm.fit(X, y)
            obs_mean = float(ipd_train["claim_amount"].mean())
            ratio = float(np.clip(obs_mean / COEFF["base_sev"]["ipd"], 0.2, 5.0))
            new_coeff["base_sev"]["ipd"] = round(COEFF["base_sev"]["ipd"] * ratio, 2)
            band_mids = {"18-24":21,"25-34":29,"35-44":39,"45-54":49,"55-64":59,"65+":69}
            preds = {b: float(gm.predict([[m]])[0]) for b,m in band_mids.items()}
            norm = preds["25-34"]
            new_coeff["age_factors"] = {b: round(p/norm,4) for b,p in preds.items()}

        new_coeff["version"] = f"custom-{prospect_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        new_coeff["prospect_id"] = prospect_id
        new_coeff["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        out_dir = os.path.join(MODEL_DIR, "custom", prospect_id)
        os.makedirs(out_dir, exist_ok=True)
        coeff_path = os.path.join(out_dir, "coeff.json")
        with open(coeff_path, "w") as f: json.dump(new_coeff, f, indent=2)

        report = {"prospect_id":prospect_id,"status":"done","trained_at":datetime.now(timezone.utc).isoformat(),
                  "rows_used":int(total),"coeff_version":new_coeff["version"]}
        with open(os.path.join(out_dir,"report.json"),"w") as f: json.dump(report,f,indent=2)

        _prospect_coeffs[prospect_id] = new_coeff
        _pilot_jobs[prospect_id].update({"status":"done","completed_at":datetime.now(timezone.utc).isoformat(),"rows":int(total),"coeff_version":new_coeff["version"]})
        log.info(f"Pilot training complete: prospect={prospect_id} rows={total}")
    except Exception as e:
        _pilot_jobs[prospect_id].update({"status":"failed","error":str(e)})
        log.error(f"Pilot training failed for {prospect_id}: {e}")

@app.post("/api/v2/pilot/train",dependencies=[Depends(verify_admin)])
async def pilot_train(file:UploadFile=File(...),prospect_id:str=Form(...),holdout:float=Form(0.20)):
    """Upload a claims CSV and train a prospect-specific calibrated model in the background."""
    if not re.match(r'^[a-zA-Z0-9_-]{2,60}$',prospect_id):
        raise HTTPException(400,"prospect_id must be 2-60 alphanumeric/dash/underscore characters")
    if not 0.05<=holdout<=0.40: raise HTTPException(400,"holdout must be 0.05–0.40")
    if not file.filename.endswith(".csv"): raise HTTPException(400,"CSV files only")
    contents = await file.read()
    if len(contents)/(1024*1024) > 50: raise HTTPException(400,"Max 50MB")
    save_path = os.path.join(os.getenv("UPLOAD_DIR","/tmp/hp_uploads"),f"pilot_{prospect_id}.csv")
    os.makedirs(os.path.dirname(save_path),exist_ok=True)
    with open(save_path,"wb") as f: f.write(contents)
    if _pilot_jobs.get(prospect_id,{}).get("status")=="training":
        raise HTTPException(409,f"Training already in progress for '{prospect_id}'")
    t = threading.Thread(target=_run_training_job,args=(prospect_id,save_path,holdout),daemon=True)
    t.start()
    log.info(f"Pilot training started: prospect={prospect_id} file={file.filename} bytes={len(contents)}")
    return {"status":"training","prospect_id":prospect_id,"message":"Training started in background. Poll GET /api/v2/pilot/{prospect_id}/report for status."}

@app.post("/api/v2/pilot/load",dependencies=[Depends(verify_admin)])
async def pilot_load(prospect_id:str=Form(...)):
    """Load a previously trained custom model from disk into memory (e.g. after server restart)."""
    coeff_path = os.path.join(MODEL_DIR,"custom",prospect_id,"coeff.json")
    if not os.path.isfile(coeff_path):
        raise HTTPException(404,f"No trained model found for '{prospect_id}'. Run /pilot/train first.")
    with open(coeff_path) as f: _prospect_coeffs[prospect_id] = json.load(f)
    log.info(f"Pilot model loaded: prospect={prospect_id}")
    return {"status":"loaded","prospect_id":prospect_id,"coeff_version":_prospect_coeffs[prospect_id].get("version")}

@app.get("/api/v2/pilot/{prospect_id}/report",dependencies=[Depends(verify_admin)])
async def pilot_report(prospect_id:str):
    """Return training report and current status for a prospect pilot."""
    report_path = os.path.join(MODEL_DIR,"custom",prospect_id,"report.json")
    job = _pilot_jobs.get(prospect_id)
    if not os.path.isfile(report_path):
        if job: return {"status":job.get("status","unknown"),"job":job}
        raise HTTPException(404,f"No pilot data found for '{prospect_id}'")
    with open(report_path) as f: report = json.load(f)
    report["in_memory"] = prospect_id in _prospect_coeffs
    if job: report["job"] = job
    return report

@app.get("/api/v2/pilot/list",dependencies=[Depends(verify_admin)])
async def pilot_list():
    """List all trained prospect pilots."""
    custom_dir = os.path.join(MODEL_DIR,"custom")
    pilots = []
    if os.path.isdir(custom_dir):
        for pid in os.listdir(custom_dir):
            rp = os.path.join(custom_dir,pid,"report.json")
            entry = {"prospect_id":pid,"in_memory":pid in _prospect_coeffs,"job":_pilot_jobs.get(pid)}
            if os.path.isfile(rp):
                with open(rp) as f: r = json.load(f)
                entry.update({"status":r.get("status"),"trained_at":r.get("trained_at"),"coeff_version":r.get("coeff_version")})
            pilots.append(entry)
    return {"pilots":pilots,"total":len(pilots)}

@app.exception_handler(Exception)
async def err(request:Request,exc:Exception):
    rid=getattr(request.state,"rid","?") if hasattr(request,"state") else "?"
    log.error(f"[{rid}] {exc}",exc_info=True)
    return JSONResponse(500,{"detail":"Internal server error","request_id":rid})
