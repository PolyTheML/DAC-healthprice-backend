"""ORM table definitions for the underwriting platform."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, JSON, String, Text

from api.database import Base


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True)
    full_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="submitted", index=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    region = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    date_of_birth = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    medical_data = Column(JSON, nullable=False, default=dict)
    timeline = Column(JSON, nullable=False, default=list)
    decision = Column(JSON, nullable=True)


class CaseRecord(Base):
    __tablename__ = "cases"

    # --- Indexed columns for fast PSI / province / queue queries ---
    case_id = Column(String, primary_key=True)
    status = Column(String, nullable=False, index=True)
    risk_level = Column(String, nullable=False, default="medium")
    risk_score = Column(Float, nullable=False, default=0.0)
    overall_confidence = Column(Float, nullable=False, default=0.0)
    final_premium = Column(Float, nullable=False, default=0.0)
    mortality_ratio = Column(Float, nullable=False, default=1.0)
    province = Column(String, nullable=True)
    requires_review = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    # --- Full Pydantic state blob for lossless reconstruction ---
    state_json = Column(JSON, nullable=False, default=dict)

    # --- A/E analysis: AI's original assessment vs human decision ---
    ai_risk_score = Column(Float, nullable=True)
    ai_risk_level = Column(String, nullable=True)
    human_override = Column(Boolean, default=False)
    human_decision = Column(String, nullable=True)   # approved | declined | referred
    human_reviewer_id = Column(String, nullable=True)
    human_notes = Column(Text, nullable=True)
    human_reviewed_at = Column(DateTime, nullable=True)
