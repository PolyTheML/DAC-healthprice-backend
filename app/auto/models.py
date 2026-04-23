"""Pydantic models for Auto Continuous Underwriting."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AutoQuoteRequest(BaseModel):
    """Static GLM quote request for auto insurance."""
    vehicle_type: str = Field(..., description="motorcycle | sedan | suv | truck")
    year_of_manufacture: int = Field(..., ge=1980, le=2025)
    region: str = Field(...)
    driver_age: int = Field(..., ge=18, le=75)
    accident_history: bool = False
    coverage: str = Field("full", description="ctpl_only | full")
    tier: str = Field("standard", description="basic | standard | premium | full")
    family_size: int = Field(1, ge=1, le=6)


class AutoQuoteResponse(BaseModel):
    """Response containing GLM anchor and initial premium."""
    policy_id: str
    glm_anchor: float
    current_premium: float
    deviation_multiplier: float
    breakdown: dict


class TelematicsEvent(BaseModel):
    """Raw telemetry ping from vehicle/device."""
    policy_id: str
    raw_device_id: Optional[str] = None
    gps_lat: float
    gps_lon: float
    speed_kmh: float = Field(..., ge=0, le=300)
    harsh_braking: bool = False
    lane_shifts: int = Field(0, ge=0, le=20)
    timestamp: Optional[datetime] = None


class MaskedTelemetry(BaseModel):
    """Privacy-safe telemetry features after PII stripping."""
    policy_id: str
    gps_hash: str
    speed_kmh: float
    harsh_braking: bool
    lane_shifts: int
    hour_bucket: int = Field(..., ge=0, le=23)
    weather_zone: Optional[str] = None


class PremiumUpdate(BaseModel):
    """Real-time premium push to frontend."""
    new_premium: float
    deviation: float
    trigger: str
    ts: str
