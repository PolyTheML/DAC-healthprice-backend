"""
Auto Pricing Lab v2 — Final Pricing Engine (Step 5)

Combines GLM price + ML adjustment → final customer premium.

final_price = glm_price × (1 + ml_adjustment)
margin      = (final_price - expected_cost) / final_price

expected_cost = risk_adjusted_premium (pure premium, no loading/tier)
This measures how much margin the insurer retains above expected claims.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict

import numpy as np

from app.data.features import VehicleProfile
from app.pricing_engine.glm_pricing import GLMResult, compute_glm_price
from app.ml.inference import MLAdjustment, compute_ml_adjustment

MIN_PREMIUM_VND = 500_000
MAX_PREMIUM_VND = 50_000_000


@dataclass
class FinalPricingResult:
    # Profile echo
    vehicle_type: str
    region: str
    tier: str
    coverage: str

    # GLM layer
    glm_price: float
    glm_breakdown: GLMResult

    # ML adjustment layer
    ml_adjustment: float        # fraction, e.g. -0.10
    ml_adjustment_vnd: float    # absolute VND
    ml_confidence: float
    ml_available: bool
    ml_model_version: int

    # Final output
    final_price: float          # glm_price × (1 + ml_adjustment), clamped
    expected_cost: float        # pure premium before loading/tier (for margin calc)
    margin: float               # (final - expected) / final
    margin_percent: float       # e.g. 22.5

    # Source indicator (for Hybrid Fallback Indicator — Stream A, Tier 2 roadmap)
    model_source: str           # "ml" | "glm_only"
    model_accuracy_pct: float   # e.g. 91.0 for ML, 75.0 for GLM-only

    def to_dict(self) -> dict:
        d = asdict(self)
        d["glm_breakdown"] = self.glm_breakdown.to_dict()
        return d


def compute_final_price(profile: VehicleProfile) -> FinalPricingResult:
    """
    Full pricing pipeline:
      1. GLM pure premium (glass-box)
      2. ML residual adjustment (learned from claims data)
      3. Final price = GLM × (1 + ML adjustment)
      4. Margin analysis
    """
    # Step 1: GLM
    glm = compute_glm_price(profile)

    # Step 2: ML adjustment (on the GLM pure premium, not final GLM price)
    ml: MLAdjustment = compute_ml_adjustment(profile, glm.risk_adjusted_premium)

    # Step 3: Apply ML adjustment to the full GLM price
    if ml.available:
        raw_final = glm.glm_price * (1.0 + ml.adjustment)
        model_source = "ml"
        model_accuracy_pct = 91.0
    else:
        raw_final = glm.glm_price
        model_source = "glm_only"
        model_accuracy_pct = 75.0

    final_price = float(np.clip(raw_final, MIN_PREMIUM_VND, MAX_PREMIUM_VND))

    # Step 4: Margin (relative to expected claims cost = risk_adjusted_premium)
    expected_cost = glm.risk_adjusted_premium
    margin = (final_price - expected_cost) / final_price if final_price > 0 else 0.0
    margin = float(np.clip(margin, -1.0, 1.0))

    return FinalPricingResult(
        vehicle_type=profile.vehicle_type,
        region=profile.region,
        tier=profile.tier,
        coverage=profile.coverage,
        glm_price=glm.glm_price,
        glm_breakdown=glm,
        ml_adjustment=ml.adjustment,
        ml_adjustment_vnd=ml.adjustment_vnd,
        ml_confidence=ml.confidence,
        ml_available=ml.available,
        ml_model_version=ml.model_version,
        final_price=final_price,
        expected_cost=expected_cost,
        margin=margin,
        margin_percent=round(margin * 100, 2),
        model_source=model_source,
        model_accuracy_pct=model_accuracy_pct,
    )
