"""FastAPI application for DAC-UW Underwriting API."""

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import engine
from api.db_models import Base
from api.routers import applications, auth, calibration, cases, dashboard, portfolio, pricing


def _seed_demo_applications() -> None:
    """Seed three demo applications on first startup (skipped if table is non-empty)."""
    from sqlalchemy.orm import Session
    from api import crud

    with Session(engine) as db:
        if crud.count_applications(db) > 0:
            return

        now = datetime.utcnow()
        seeds = [
            {
                "id": "DAC-DEMO0001",
                "full_name": "Sovann Pich", "status": "submitted",
                "submitted_at": now, "region": "Phnom Penh", "occupation": "Office/Desk",
                "date_of_birth": "1980-05-15", "gender": "Male",
                "phone": "+855 12 345 678", "email": "sovann@example.com",
                "medical_data": {
                    "smokingStatus": "Never", "preexistingConditions": ["Hypertension"],
                    "exerciseFrequency": "Light", "height": 170, "weight": 80,
                    "bloodPressure": "130/85", "familyHistory": "Heart Disease",
                    "currentMedications": "Amlodipine 5mg", "alcoholConsumption": "Occasional",
                },
                "timeline": [
                    {"event": "Application received", "done": True,  "timestamp": now.isoformat()},
                    {"event": "Initial review",        "done": False, "timestamp": None},
                    {"event": "Underwriter decision",  "done": False, "timestamp": None},
                    {"event": "Policy issued",         "done": False, "timestamp": None},
                ],
            },
            {
                "id": "DAC-DEMO0002",
                "full_name": "Channary Kim", "status": "in_review",
                "submitted_at": now, "region": "Siem Reap", "occupation": "Healthcare",
                "date_of_birth": "1975-11-28", "gender": "Female",
                "phone": "+855 92 876 543", "email": "channary@example.com",
                "medical_data": {
                    "smokingStatus": "Current",
                    "preexistingConditions": ["Diabetes", "Hypertension"],
                    "exerciseFrequency": "Sedentary", "height": 158, "weight": 75,
                    "bloodPressure": "145/92", "familyHistory": "Diabetes, Heart Disease",
                    "currentMedications": "Metformin, Lisinopril", "alcoholConsumption": "Never",
                },
                "timeline": [
                    {"event": "Application received", "done": True,  "timestamp": now.isoformat()},
                    {"event": "Initial review",        "done": True,  "timestamp": now.isoformat()},
                    {"event": "Underwriter decision",  "done": False, "timestamp": None},
                    {"event": "Policy issued",         "done": False, "timestamp": None},
                ],
            },
            {
                "id": "DAC-DEMO0003",
                "full_name": "Dara Meas", "status": "submitted",
                "submitted_at": now, "region": "Battambang", "occupation": "Retail/Service",
                "date_of_birth": "1995-03-10", "gender": "Male",
                "phone": "+855 78 234 567", "email": "dara@example.com",
                "medical_data": {
                    "smokingStatus": "Never", "preexistingConditions": ["None"],
                    "exerciseFrequency": "Active", "height": 175, "weight": 68,
                    "bloodPressure": "118/75", "familyHistory": "None",
                    "currentMedications": "None", "alcoholConsumption": "Never",
                },
                "timeline": [
                    {"event": "Application received", "done": True,  "timestamp": now.isoformat()},
                    {"event": "Initial review",        "done": False, "timestamp": None},
                    {"event": "Underwriter decision",  "done": False, "timestamp": None},
                    {"event": "Policy issued",         "done": False, "timestamp": None},
                ],
            },
        ]
        for seed in seeds:
            app_id = seed.pop("id")
            crud.create_application(db, app_id, seed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_demo_applications()
    yield


app = FastAPI(
    title="DAC-UW Underwriting API",
    description="Agentic medical underwriting platform for life insurance",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(applications.router, prefix="/api/v1/applications", tags=["applications"])
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(pricing.router, prefix="/pricing", tags=["pricing"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(calibration.router, prefix="/api/v1/calibration", tags=["calibration"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
