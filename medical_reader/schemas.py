"""Pydantic models for medical data extraction and validation"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, validator


class TobaccoStatus(str, Enum):
    """Tobacco use status"""
    NEVER = "never"
    FORMER = "former"
    CURRENT = "current"
    UNKNOWN = "unknown"


class ExtractionMeta(BaseModel):
    """Metadata about the extraction process"""
    method: str = Field(..., description="Extraction method used")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence (0-1)")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    source_document: str = Field(..., description="Source PDF filename")


class VitalSigns(BaseModel):
    """Core vital signs and anthropometric data"""
    age: Optional[int] = Field(None, ge=18, le=120, description="Age in years")
    bmi: Optional[float] = Field(None, ge=10.0, le=60.0, description="Body Mass Index")
    systolic_bp: Optional[int] = Field(None, ge=70, le=200, description="Systolic blood pressure (mmHg)")
    diastolic_bp: Optional[int] = Field(None, ge=40, le=120, description="Diastolic blood pressure (mmHg)")
    heart_rate: Optional[int] = Field(None, ge=40, le=150, description="Resting heart rate (bpm)")

    @validator("bmi")
    def validate_bmi_reasonableness(cls, v):
        """Additional check for extreme BMI values that might be extraction errors"""
        if v is not None and v > 50:
            # Flag but don't reject - will be caught by consistency validation
            pass
        return v


class LabValues(BaseModel):
    """Laboratory test results"""
    blood_glucose_fasting: Optional[float] = Field(None, ge=60.0, le=500.0, description="Fasting glucose (mg/dL)")
    total_cholesterol: Optional[float] = Field(None, ge=100.0, le=400.0, description="Total cholesterol (mg/dL)")
    hdl_cholesterol: Optional[float] = Field(None, ge=10.0, le=150.0, description="HDL cholesterol (mg/dL)")
    ldl_cholesterol: Optional[float] = Field(None, ge=10.0, le=350.0, description="LDL cholesterol (mg/dL)")
    triglycerides: Optional[float] = Field(None, ge=20.0, le=800.0, description="Triglycerides (mg/dL)")
    lab_date: Optional[str] = Field(None, description="Lab test date (YYYY-MM-DD)")


class MedicalHistory(BaseModel):
    """Medical conditions, medications, and history"""
    conditions: List[str] = Field(default_factory=list, description="Medical conditions (e.g., Diabetes, Hypertension)")
    medications: List[str] = Field(default_factory=list, description="Current medications with dosages")
    tobacco_status: TobaccoStatus = Field(default=TobaccoStatus.UNKNOWN, description="Tobacco use status")
    family_history: List[str] = Field(default_factory=list, description="Notable family medical history")


class ValidationResult(BaseModel):
    """Results of validation checks"""
    schema_valid: bool = Field(..., description="Pydantic schema validation passed")
    domain_valid: bool = Field(..., description="Physiological range validation passed")
    consistency_valid: bool = Field(..., description="Cross-field consistency checks passed")
    flags: List[str] = Field(default_factory=list, description="Validation warnings/issues found")
    routing: str = Field(default="human_review", description="Routing decision: stp, human_review, or reject")


class MedicalRecord(BaseModel):
    """Complete medical record extracted from PDF"""
    policy_id: str = Field(..., description="Unique policy identifier")
    extraction_meta: ExtractionMeta
    vitals: VitalSigns
    labs: LabValues
    history: MedicalHistory
    validation: Optional[ValidationResult] = None

    def to_glm_input(self) -> dict:
        """Convert to format suitable for GLM pricing model"""
        return {
            "age": self.vitals.age,
            "bmi": self.vitals.bmi,
            "systolic_bp": self.vitals.systolic_bp,
            "diastolic_bp": self.vitals.diastolic_bp,
            "heart_rate": self.vitals.heart_rate,
            "blood_glucose_fasting": self.labs.blood_glucose_fasting,
            "total_cholesterol": self.labs.total_cholesterol,
            "conditions": self.history.conditions,
            "tobacco_status": self.history.tobacco_status.value,
            "confidence": self.extraction_meta.confidence,
        }
