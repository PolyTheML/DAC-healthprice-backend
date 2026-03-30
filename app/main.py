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
import joblib, numpy as np
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Depends, Header
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
_fallback_models={}   # GLM fallback — consistent methodology with main models
_partner_keys: dict={}  # key_hash → {partner_name, daily_limit, is_active, usage_today, date}

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
P_FLOOR=50; P_CEIL=25000

# ── Fallback GLM fitting — consistent Poisson+Ridge methodology ───────────────
def _fit_fallback_models():
    """Fit lightweight GLMs on synthetic data so fallback uses same methodology as main models."""
    try:
        from sklearn.linear_model import PoissonRegressor, Ridge
        rng=np.random.RandomState(42); n=2000
        ages=rng.randint(18,71,n); genders=rng.randint(0,3,n); smoking=rng.randint(0,3,n)
        exercise=rng.randint(0,4,n); occupation=rng.randint(0,6,n); region=rng.randint(0,11,n); pe=rng.randint(0,5,n)
        X=np.column_stack([ages,genders,smoking,exercise,occupation,region,pe])
        age_f=1+np.maximum(0,ages-35)*0.008
        smoke_f=np.array([1,1.15,1.40])[np.clip(smoking,0,2)]
        ex_f=np.array([1.20,1.05,0.90,0.80])[np.clip(exercise,0,3)]
        occ_f=np.array([0.85,1.0,1.05,1.15,1.30,1.10])[np.clip(occupation,0,5)]
        pe_f=1+pe*0.20
        reg_f_arr=np.array([1.20,1.05,0.90,1.10,0.85,0.75,1.25,1.20,1.05,0.90,0.95])[np.clip(region,0,10)]
        fb={}
        for cov,base_rate,base_sev in [("ipd",0.12,2500),("opd",2.5,60),("dental",0.8,120),("maternity",0.15,3500)]:
            yf=np.clip(base_rate*age_f*smoke_f*ex_f*occ_f*pe_f+rng.normal(0,0.01,n),0.001,20)
            fm=PoissonRegressor(alpha=0.1,max_iter=300); fm.fit(X,yf)
            ys=np.clip(base_sev*reg_f_arr*(1+np.maximum(0,ages-30)*0.006)*(1+pe*0.15)+rng.normal(0,base_sev*0.05,n),10,100000)
            sm=Ridge(alpha=1.0); sm.fit(X,ys)
            fb[f"{cov}_freq"]=fm; fb[f"{cov}_sev"]=sm
        log.info("Fallback GLMs fitted (Poisson+Ridge on synthetic data)")
        return fb
    except Exception as e:
        log.warning(f"Fallback GLM fit failed: {e}"); return {}

@asynccontextmanager
async def lifespan(app):
    global db_pool,models,model_version,model_meta,_fallback_models
    # Load primary ML models
    for c in ["ipd","opd","dental","maternity"]:
        for t in ["freq","sev"]:
            try: models[f"{c}_{t}"]=joblib.load(os.path.join(MODEL_DIR,f"{c}_{t}.pkl")); log.info(f"Loaded {c}_{t}")
            except Exception as e: log.warning(f"Skip {c}_{t}: {e}")
    try:
        meta=joblib.load(os.path.join(MODEL_DIR,"model_meta.pkl"))
        model_version=meta.get("version","v1.0.0"); model_meta.update(meta)
    except: pass
    log.info(f"Models: {list(models.keys())} ({model_version})")
    # Always fit fallback GLMs for consistent methodology
    _fallback_models=_fit_fallback_models()
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

def _enc(req):
    return np.array([[req.age,G_ENC.get(req.gender,0),S_ENC.get(req.smoking_status,0),E_ENC.get(req.exercise_frequency,1),O_ENC.get(req.occupation_type,0),R_ENC.get(req.region,0),len([p for p in req.preexist_conditions if p!="None"])]])

def _predict(cov,feat):
    fm,sm=models.get(f"{cov}_freq"),models.get(f"{cov}_sev")
    if fm and sm:
        f=float(np.clip(fm.predict(feat)[0],0.001,20)); s=float(np.clip(sm.predict(feat)[0],10,100000)); src="ml"
    else:
        # Use GLM fallback (Poisson+Ridge) — same methodology as primary models
        ffm,fsm=_fallback_models.get(f"{cov}_freq"),_fallback_models.get(f"{cov}_sev")
        if ffm and fsm:
            f=float(np.clip(ffm.predict(feat)[0],0.001,20)); s=float(np.clip(fsm.predict(feat)[0],10,100000)); src="fallback_glm"
        else:
            f=_fb_f(cov,feat); s=_fb_s(cov,feat); src="fallback"
    return {"frequency":round(f,4),"severity":round(s,2),"expected_annual_cost":round(f*s,2),"source":src}

def _fb_f(c,feat):
    a,g,sm,ex,oc,rg,pe=feat[0]; base={"ipd":0.12,"opd":2.5,"dental":0.8,"maternity":0.15}.get(c,0.12)
    return max(0.001,base*(1+max(0,(a-35))*0.008)*[1,1.15,1.40][int(min(sm,2))]*[1.20,1.05,0.90,0.80][int(min(ex,3))]*[0.85,1,1.05,1.15,1.30,1.10][int(min(oc,5))]*(1+pe*0.20))

def _fb_s(c,feat):
    a,g,sm,ex,oc,rg,pe=feat[0]; base={"ipd":2500,"opd":60,"dental":120,"maternity":3500}.get(c,2500)
    rf=[1.20,1.05,0.90,1.10,0.85,0.75,1.25,1.20,1.05,0.90,0.95]; ri=int(min(rg,10))
    return max(10,base*(rf[ri] if ri<len(rf) else 1)*(1+max(0,(a-30))*0.006)*(1+pe*0.15))

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
    return {"status":"healthy","service":"DAC HealthPrice v2.3","models_loaded":list(models.keys()),"fallback_models_loaded":list(_fallback_models.keys()),"model_version":model_version,"database_connected":db_pool is not None,"countries":list(CTY_REG.keys()),"timestamp":datetime.now(timezone.utc).isoformat()}

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
async def calc(req:PricingRequest,request:Request,auth:dict=Depends(verify_pricing_auth)):
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

    t0=time.monotonic(); feat=_enc(req); qid=_qid(); rid=getattr(request.state,"rid","?")
    ipd=_predict("ipd",feat); tier=TIERS[req.ipd_tier]; tf=T_F[req.ipd_tier]; ld=COV["ipd"]["load"]
    ipd_loaded=round(ipd["expected_annual_cost"]*(1+ld)*tf,2)
    ded_cr=round(tier["deductible"]*0.10,2)
    ipd_prem=round(float(np.clip(ipd_loaded-ded_cr,P_FLOOR,P_CEIL)),2)
    riders={}; rtot=0
    for c,inc in [("opd",req.include_opd),("dental",req.include_dental),("maternity",req.include_maternity)]:
        if not inc: continue
        r=_predict(c,feat); rp=round(float(np.clip(r["expected_annual_cost"]*(1+COV[c]["load"]),10,5000)),2)
        riders[c]={"name":COV[c]["name"],"frequency":r["frequency"],"severity":r["severity"],"expected_annual_cost":r["expected_annual_cost"],"loading_pct":COV[c]["load"],"annual_premium":rp,"monthly_premium":round(rp/12,2),"source":r["source"]}
        rtot+=rp
    ff=round(1+(req.family_size-1)*0.65,2); pre_fam=round(ipd_prem+rtot,2)
    total=round(float(np.clip(pre_fam*ff,P_FLOOR,P_CEIL*req.family_size)),2)

    used_fallback=ipd.get("source","ml")!="ml" or any(v.get("source","ml")!="ml" for v in riders.values())
    email=req.email or _email_from_auth

    res={"quote_id":qid,"request_id":rid,"country":req.country,"region":req.region,"model_version":model_version,
        "ipd_tier":req.ipd_tier,"tier_benefits":tier,"underwriting":uw,
        "ipd_core":{"frequency":ipd["frequency"],"severity":ipd["severity"],"expected_annual_cost":ipd["expected_annual_cost"],"loading_pct":ld,"tier_factor":tf,"deductible_credit":ded_cr,"annual_premium":ipd_prem,"monthly_premium":round(ipd_prem/12,2),"source":ipd["source"]},
        "riders":riders,"family_size":req.family_size,"family_factor":ff,"total_before_family":pre_fam,
        "total_annual_premium":total,"total_monthly_premium":round(total/12,2),
        "risk_profile":{"age":req.age,"gender":req.gender,"smoking":req.smoking_status,"exercise":req.exercise_frequency,"occupation":req.occupation_type,"preexist_conditions":req.preexist_conditions,"preexist_count":len([p for p in req.preexist_conditions if p!="None"])},
        "calculated_at":datetime.now(timezone.utc).isoformat()}

    res=_apply_banding(res)
    if _tok and _tok in _sessions: _sessions[_tok]["uses_remaining"]-=1
    if is_partner: res["partner"]=auth.get("partner_name","")

    await _log_q(qid,req.model_dump(),res,uw_status=uw["status"],used_fallback=used_fallback,browser_id=bid,email=email)
    await _log_b(qid,req,bid,email,is_sweep)
    ms=round((time.monotonic()-t0)*1000,1)
    log.info(f"[{rid}] {qid}|{req.ipd_tier}+{'+'.join(riders) or 'none'}|age={req.age}|${total:,.0f}/yr|uw={uw['status']}|fallback={used_fallback}|sweep={is_sweep}|{ms}ms")
    return res

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
        "fallback_models_loaded":list(_fallback_models.keys()),
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
    global models,model_version,model_meta
    import pandas as pd
    from sklearn.linear_model import PoissonRegressor
    from sklearn.ensemble import GradientBoostingRegressor
    df=pd.read_csv(path)
    enc={"gender":G_ENC,"smoking":S_ENC,"exercise":E_ENC,"occupation":O_ENC,"region":R_ENC}
    for col,m in enc.items():
        if col in df.columns: df[col]=df[col].map(m).fillna(0).astype(int)
    feat=["age","gender","smoking","exercise","occupation","region","preexist_count"]
    X=df[feat].values; yf=df["claim_count"].values
    cf=PoissonRegressor(alpha=0.01,max_iter=500); cf.fit(X,yf)
    mask=df["claim_count"]>0
    if mask.sum()<50: return {"status":"insufficient","claimants":int(mask.sum())}
    Xs=X[mask]; ys=(df.loc[mask,"claim_amount"]/df.loc[mask,"claim_count"]).values
    cs=GradientBoostingRegressor(n_estimators=150,max_depth=4,learning_rate=0.07,random_state=42); cs.fit(Xs,ys)
    cr2=round(cs.score(Xs,ys),4)
    champ=models.get(f"{cov}_sev"); promote=True; champ_r2=None
    if champ:
        try: champ_r2=round(champ.score(Xs,ys),4); promote=cr2>=champ_r2-0.02
        except: pass
    nv=f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    if promote:
        import shutil
        for t in ["freq","sev"]:
            p=os.path.join(MODEL_DIR,f"{cov}_{t}.pkl")
            if os.path.exists(p): shutil.copy2(p,p.replace(".pkl","_bak.pkl"))
        joblib.dump(cf,os.path.join(MODEL_DIR,f"{cov}_freq.pkl")); joblib.dump(cs,os.path.join(MODEL_DIR,f"{cov}_sev.pkl"))
        # Task 3+4: persist model metadata and hot-swap into live engine
        now_iso=datetime.now(timezone.utc).isoformat()
        new_meta={"version":nv,"last_retrained_at":now_iso,"training_dataset":bid,"coverage":cov,"r2":cr2}
        joblib.dump(new_meta,os.path.join(MODEL_DIR,"model_meta.pkl"))
        models[f"{cov}_freq"]=cf; models[f"{cov}_sev"]=cs; model_version=nv; model_meta.update(new_meta)
        log.info(f"Hot-swapped {cov} models → {nv} (R²={cr2})")
        if db_pool:
            try: await db_pool.execute("INSERT INTO hp_model_versions(version,coverage,training_dataset,r2)VALUES($1,$2,$3,$4)",nv,cov,bid,cr2)
            except Exception as e: log.warning(f"Model version log fail: {e}")
    return {"status":"promoted" if promote else "rejected","version":nv,"r2":cr2,"champion_r2":champ_r2,"rows":len(df)}

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

@app.exception_handler(Exception)
async def err(request:Request,exc:Exception):
    rid=getattr(request.state,"rid","?") if hasattr(request,"state") else "?"
    log.error(f"[{rid}] {exc}",exc_info=True)
    return JSONResponse(500,{"detail":"Internal server error","request_id":rid})
