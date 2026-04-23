"""
UnderwritingState: The canonical state model for the medical underwriting agent.

This Pydantic model flows through the LangGraph workflow and maintains:
- Raw extracted medical data
- Actuarial calculations (frequency, severity, premium)
- Audit trail (compliance traceability)
- Confidence metrics and human review flags

Design principles:
1. Immutable by default (used in LangGraph state)
2. Type-safe with Field descriptions
3. Deterministic (same input = same state)
4. Traceable (every change logged in audit_trail)
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from decimal import Decimal


# ========== CAMBODIA-SPECIFIC MODELS ==========

class CambodiaOccupationRisk(BaseModel):
    """Cambodia-specific occupational mortality risk assessment."""
    occupation_type: Optional[str] = Field(
        None,
        description="Office/Desk | Retail/Service | Manual Labor | Construction | Healthcare | Motorbike Courier | Retired"
    )
    motorbike_usage: Optional[str] = Field(
        None,
        description="Never | Occasional | Daily"
    )
    risk_multiplier: float = Field(
        default=1.0,
        description="Composite occupational mortality multiplier from assumptions"
    )
    risk_notes: str = Field(
        default="",
        description="Human-readable explanation of occupational risk"
    )


class CambodiaRegionRisk(BaseModel):
    """Cambodia-specific regional and healthcare infrastructure risk."""
    province: Optional[str] = Field(
        None,
        description="Phnom Penh | Siem Reap | Mondulkiri | Ratanakiri | Kampong Cham | etc."
    )
    healthcare_tier: Optional[str] = Field(
        None,
        description="TierA | TierB | Clinic | Unknown — facility where medical exam was conducted"
    )
    endemic_risk_multiplier: float = Field(
        default=1.0,
        description="Provincial endemic disease multiplier (Dengue/Malaria/TB prevalence)"
    )
    healthcare_reliability_discount: float = Field(
        default=1.0,
        description="Premium discount/surcharge based on exam facility reliability (<1.0 = discount)"
    )
    region_notes: str = Field(
        default="",
        description="Human-readable explanation of regional risk"
    )


class RiskLevel(str, Enum):
    """Classification for underwriting risk tiers."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DECLINE = "decline"


class AuditEntry(BaseModel):
    """Single entry in the audit trail. Immutable record of each decision."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    node: str = Field(..., description="Which node generated this entry (intake, pricing, review, etc.)")
    action: str = Field(..., description="What happened (e.g., 'extracted_bmi', 'calculated_frequency')")
    details: Dict[str, Any] = Field(default_factory=dict, description="Key-value pairs for the action")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in this entry (0.0-1.0)")

    def __str__(self) -> str:
        """Human-readable format for logging."""
        return f"[{self.timestamp.isoformat()}] {self.node}/{self.action} (confidence: {self.confidence:.2f})"


class ExtractedMedicalData(BaseModel):
    """Structured medical data extracted from PDF or user input."""

    # Demographics
    age: Optional[int] = Field(None, ge=0, le=150, description="Age in years")
    gender: Optional[str] = Field(None, description="M/F/Other")

    # Vitals
    bmi: Optional[float] = Field(None, ge=10.0, le=60.0, description="Body Mass Index")
    blood_pressure_systolic: Optional[int] = Field(None, ge=60, le=250, description="Systolic BP in mmHg")
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=150, description="Diastolic BP in mmHg")

    # Lifestyle
    smoker: Optional[bool] = Field(None, description="Current smoker?")
    alcohol_use: Optional[str] = Field(None, description="None/Moderate/Heavy")

    # Medical History
    diabetes: Optional[bool] = Field(None)
    hypertension: Optional[bool] = Field(None)
    hyperlipidemia: Optional[bool] = Field(None)
    family_history_chd: Optional[bool] = Field(None, description="Coronary Heart Disease")

    # Medications
    medications: List[str] = Field(default_factory=list, description="List of current medications")

    # Product information
    face_amount: Optional[float] = Field(None, ge=1000.0, le=1000000.0, description="Coverage face amount (USD)")
    policy_term_years: Optional[int] = Field(None, ge=1, le=40, description="Policy term in years")
    product_type: Optional[str] = Field(None, description="term/whole_life/endowment")

    # Cambodia-specific extraction fields
    province: Optional[str] = Field(None, description="Cambodian province extracted from document")
    occupation_type: Optional[str] = Field(None, description="Extracted occupation / job type")
    motorbike_usage: Optional[str] = Field(None, description="Never | Occasional | Daily")
    healthcare_tier: Optional[str] = Field(None, description="Hospital/clinic tier from document header (TierA | TierB | Clinic)")

    # Confidence scores (per field)
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="Confidence in each extracted field (0.0-1.0)"
    )

    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all extracted fields."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores.values()) / len(self.confidence_scores)

    def missing_fields(self) -> List[str]:
        """Return list of critical fields that are None."""
        critical = ['age', 'bmi', 'blood_pressure_systolic', 'blood_pressure_diastolic']
        return [field for field in critical if getattr(self, field) is None]


class ActuarialCalculation(BaseModel):
    """Actuarial calculations for premium pricing using Mortality Ratio method."""

    # ========== LEGACY FIELDS (v1.0 GLM) ==========
    # Kept for backwards compatibility; new calculations populate new fields instead
    base_frequency: float = Field(default=0.0, description="Expected claims/year (base rate) — DEPRECATED")
    frequency_score: float = Field(default=0.0, description="Frequency modifier (0.5 - 3.0x) — DEPRECATED")
    adjusted_frequency: float = Field(default=0.0, description="base_frequency * frequency_score — DEPRECATED")
    base_severity: float = Field(default=0.0, description="Average claim cost (USD) — DEPRECATED")
    severity_score: float = Field(default=0.0, description="Severity modifier (0.5 - 2.0x) — DEPRECATED")
    adjusted_severity: float = Field(default=0.0, description="base_severity * severity_score — DEPRECATED")
    base_premium: float = Field(default=0.0, description="Annual premium (before adjustments) — DEPRECATED")

    # ========== NEW FIELDS (v2.0 MORTALITY RATIO) ==========
    face_amount: float = Field(default=0.0, description="Coverage face amount (USD)")
    policy_term_years: int = Field(default=1, description="Policy term in years")

    # Base mortality and risk adjustment
    base_mortality_rate: float = Field(
        default=0.0,
        description="q(x) per 1,000 per year from actuarial tables"
    )
    mortality_ratio: float = Field(
        default=1.0,
        description="Cumulative risk adjustment (1.0 = standard, 2.0 = +100%)"
    )

    # Pure premium (before loadings)
    pure_premium: float = Field(
        default=0.0,
        description="Expected cost before expenses/commissions (face_amount × q(x) × mortality_ratio)"
    )

    # Loading breakdown
    expense_loading: float = Field(default=0.0, description="Admin/underwriting expenses")
    commission_loading: float = Field(default=0.0, description="Agent commission")
    profit_loading: float = Field(default=0.0, description="Profit margin")
    contingency_loading: float = Field(default=0.0, description="Catastrophe buffer")
    total_loading_amount: float = Field(default=0.0, description="Sum of all loadings")

    # Final premiums
    gross_premium: float = Field(
        default=0.0,
        description="Final annual premium (pure + loadings)"
    )
    monthly_premium: float = Field(default=0.0, description="Annual premium ÷ 12")

    # Risk factor detail (for audit trail)
    factor_breakdown: Dict[str, float] = Field(
        default_factory=dict,
        description="Which risk factors were applied: {factor_name: multiplier}"
    )

    # Backwards compatibility: final_premium = gross_premium (both populated during calculation)
    final_premium: float = Field(default=0.0, description="Final premium after all adjustments (alias for gross_premium)")

    # Metadata
    model_version: str = Field(default="v2.0-mortality-ratio", description="Actuarial model used")
    assumption_version: str = Field(default="", description="Assumptions set version (e.g., v2.0-2026-04-10)")
    calculation_notes: str = Field(default="", description="Human-readable explanation of pricing")


class ReviewNotes(BaseModel):
    """Human review decision (populated by review node)."""
    required: bool = Field(default=True, description="Does this case need human review?")
    reason: Optional[str] = Field(None, description="Why review is needed (if required=True)")
    reviewer_id: Optional[str] = Field(None, description="Who reviewed it")
    approved: Optional[bool] = Field(None, description="Approved/Declined/Pending")
    reviewer_notes: Optional[str] = Field(None, description="Additional context from reviewer")
    timestamp: Optional[datetime] = Field(None)


class UnderwritingState(BaseModel):
    """
    Master state object for the medical underwriting workflow.

    Flows through LangGraph nodes: intake → pricing → review → decision

    Each node:
    1. Reads current state
    2. Performs its task
    3. Appends to audit_trail
    4. Returns updated state (immutable pattern)
    """

    # ========== INPUT ==========
    case_id: str = Field(..., description="Unique identifier for this underwriting case")
    source_document_path: Optional[str] = Field(None, description="Path to source PDF/image")
    source_document_raw: Optional[bytes] = Field(None, description="Raw PDF bytes (for re-processing)")

    # ========== INTAKE NODE OUTPUT ==========
    extracted_data: ExtractedMedicalData = Field(
        default_factory=ExtractedMedicalData,
        description="Structured medical data extracted from source document"
    )

    # ========== PRICING NODE OUTPUT ==========
    actuarial: ActuarialCalculation = Field(
        default_factory=ActuarialCalculation,
        description="Frequency-Severity GLM calculations"
    )

    # ========== RISK ASSESSMENT ==========
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, description="LOW/MEDIUM/HIGH/DECLINE")
    risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall risk score (0-100, higher = riskier)"
    )

    # ========== REVIEW NODE OUTPUT ==========
    review: ReviewNotes = Field(
        default_factory=ReviewNotes,
        description="Human review decision"
    )

    # ========== CAMBODIA-SPECIFIC RISK ASSESSMENT ==========
    occupation_risk: CambodiaOccupationRisk = Field(
        default_factory=CambodiaOccupationRisk,
        description="Cambodia occupational risk assessment"
    )
    region_risk: CambodiaRegionRisk = Field(
        default_factory=CambodiaRegionRisk,
        description="Cambodia regional and healthcare-tier risk assessment"
    )
    reasoning_trace: str = Field(
        default="",
        description="SHAP-style AI explanation: why each risk factor was flagged, where found"
    )

    # ========== WORKFLOW STATUS ==========
    current_node: str = Field(default="start", description="Which node is processing this state")
    status: str = Field(
        default="pending",
        description="pending/intake/pricing/review/approved/declined/error"
    )

    # ========== AUDIT & COMPLIANCE ==========
    audit_trail: List[AuditEntry] = Field(
        default_factory=list,
        description="Complete trace of every decision (compliance requirement)"
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in final decision (weighted average)"
    )

    # ========== METADATA ==========
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list, description="Non-fatal errors encountered")

    # ========== CONFIG ==========
    min_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence below this triggers human review"
    )

    # ========== VALIDATORS ==========

    @validator('case_id')
    def case_id_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('case_id cannot be empty')
        return v.strip()

    @validator('updated_at', pre=True, always=True)
    def update_timestamp(cls, v):
        """Automatically update timestamp on state mutation."""
        return datetime.utcnow()

    # ========== COMPUTED PROPERTIES ==========

    @property
    def is_intake_complete(self) -> bool:
        """Has the intake node successfully extracted data?"""
        return len(self.extracted_data.confidence_scores) > 0

    @property
    def is_pricing_complete(self) -> bool:
        """Has the pricing node calculated a premium?"""
        return self.actuarial.gross_premium > 0.0 or self.actuarial.final_premium > 0.0

    @property
    def requires_human_review(self) -> bool:
        """Does this case need human review?"""
        triggers = [
            self.overall_confidence < self.min_confidence_threshold,
            len(self.extracted_data.missing_fields()) > 0,
            self.risk_level in [RiskLevel.HIGH, RiskLevel.DECLINE],
            len(self.errors) > 0,
        ]
        return any(triggers)

    @property
    def is_complete(self) -> bool:
        """Has the workflow completed?"""
        return self.status in ["approved", "declined", "error"]

    # ========== METHODS ==========

    def add_audit_entry(
        self,
        node: str,
        action: str,
        details: Dict[str, Any],
        confidence: float = 1.0
    ) -> None:
        """
        Append an audit entry. Called by each node during processing.

        Example:
            state.add_audit_entry(
                node="intake",
                action="extracted_bmi",
                details={"bmi": 24.5, "method": "vision"},
                confidence=0.95
            )
        """
        entry = AuditEntry(
            node=node,
            action=action,
            details=details,
            confidence=confidence
        )
        self.audit_trail.append(entry)

    def add_error(self, error_msg: str) -> None:
        """Log a non-fatal error."""
        self.errors.append(error_msg)

    def to_audit_report(self) -> str:
        """Generate human-readable audit trail for compliance."""
        report_lines = [
            f"=== AUDIT REPORT: {self.case_id} ===",
            f"Created: {self.created_at.isoformat()}",
            f"Status: {self.status}",
            f"Overall Confidence: {self.overall_confidence:.2%}",
            "",
            "Audit Trail:",
            "-" * 60,
        ]

        for entry in self.audit_trail:
            report_lines.append(str(entry))
            for key, value in entry.details.items():
                report_lines.append(f"  {key}: {value}")

        if self.errors:
            report_lines.extend(["", "Errors Encountered:", "-" * 60])
            for error in self.errors:
                report_lines.append(f"  - {error}")

        return "\n".join(report_lines)

    def to_summary(self) -> Dict[str, Any]:
        """Return a JSON-safe summary for Streamlit dashboard."""
        return {
            "case_id": self.case_id,
            "status": self.status,
            "risk_level": self.risk_level.value,
            "final_premium": round(self.actuarial.final_premium, 2),
            "overall_confidence": round(self.overall_confidence, 2),
            "requires_review": self.requires_human_review,
            "extracted_data": {
                "age": self.extracted_data.age,
                "bmi": self.extracted_data.bmi,
                "blood_pressure": f"{self.extracted_data.blood_pressure_systolic}/{self.extracted_data.blood_pressure_diastolic}",
                "smoker": self.extracted_data.smoker,
                "province": self.extracted_data.province,
                "occupation_type": self.extracted_data.occupation_type,
                "motorbike_usage": self.extracted_data.motorbike_usage,
            },
            "cambodia_risk": {
                "occupation_multiplier": round(self.occupation_risk.risk_multiplier, 4),
                "endemic_multiplier": round(self.region_risk.endemic_risk_multiplier, 4),
                "healthcare_discount": round(self.region_risk.healthcare_reliability_discount, 4),
            },
            "reasoning_trace": self.reasoning_trace,
            "audit_entries": len(self.audit_trail),
            "created_at": self.created_at.isoformat(),
        }


# ========== EXAMPLE USAGE & VALIDATION ==========

if __name__ == "__main__":
    # Example 1: Initialize empty state
    state = UnderwritingState(case_id="CASE-2025-001")
    print(f"Empty state created: {state.status}")

    # Example 2: Add extracted medical data
    state.extracted_data = ExtractedMedicalData(
        age=45,
        bmi=26.5,
        blood_pressure_systolic=135,
        blood_pressure_diastolic=85,
        smoker=False,
        confidence_scores={
            "age": 0.95,
            "bmi": 0.90,
            "blood_pressure_systolic": 0.92,
            "blood_pressure_diastolic": 0.92,
        }
    )
    state.add_audit_entry(
        node="intake",
        action="extracted_vitals",
        details={"fields_extracted": 4, "method": "vision_api"},
        confidence=0.91
    )
    print(f"Intake complete: {state.is_intake_complete}")

    # Example 3: Add actuarial calculation
    state.actuarial = ActuarialCalculation(
        base_frequency=0.15,
        frequency_score=1.2,
        adjusted_frequency=0.18,
        base_severity=5000.0,
        severity_score=1.1,
        adjusted_severity=5500.0,
        base_premium=900.0,
        final_premium=1050.0,
        calculation_notes="Frequency adjusted +20% for elevated BP. Severity adjusted +10% for age+smoking."
    )
    state.add_audit_entry(
        node="pricing",
        action="calculated_premium",
        details={"final_premium": 1050.0, "risk_level": "medium"},
        confidence=0.95
    )
    print(f"Pricing complete: {state.is_pricing_complete}")

    # Example 4: Check compliance
    state.overall_confidence = state.extracted_data.average_confidence
    print(f"\nAudit Report:\n{state.to_audit_report()}")

    # Example 5: Dashboard summary
    print(f"\nDashboard Summary: {state.to_summary()}")
