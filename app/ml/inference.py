"""
Auto Pricing Lab v2 — ML Inference (Step 4b)

Loads the latest trained ML model and computes the adjustment to apply on top of GLM.

ml_adjustment: fractional change  (e.g. -0.10 = reduce GLM price by 10%)
confidence:    0.0–1.0 model certainty (based on prediction interval width)
"""
from __future__ import annotations
import os, pickle, json, warnings
from pathlib import Path
from dataclasses import dataclass

import numpy as np

from app.data.features import VehicleProfile, extract_features

MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))

# Module-level cache — loaded once at startup
_cached_model = None
_cached_version: int | None = None


@dataclass
class MLAdjustment:
    adjustment: float       # fractional: -0.15 means "reduce GLM by 15%"
    adjustment_vnd: float   # absolute VND amount of the adjustment
    confidence: float       # 0.0–1.0
    model_version: int
    available: bool         # False if no model trained yet


def _load_latest_model() -> dict | None:
    global _cached_model, _cached_version
    existing = sorted(MODEL_DIR.glob("auto_ml_v*.pkl"), key=lambda p: int(p.stem.split("v")[1]))
    if not existing:
        return None
    latest = existing[-1]
    version = int(latest.stem.split("v")[1])
    if _cached_version == version and _cached_model is not None:
        return _cached_model
    with open(latest, "rb") as f:
        _cached_model = pickle.load(f)
    _cached_version = version
    return _cached_model


def compute_ml_adjustment(profile: VehicleProfile, glm_pure_premium: float) -> MLAdjustment:
    """
    Predict the residual correction for this profile, expressed as a fraction of glm_pure_premium.
    Clamped to [-0.30, +0.40] to prevent extreme adjustments.
    """
    bundle = _load_latest_model()
    if bundle is None:
        return MLAdjustment(
            adjustment=0.0,
            adjustment_vnd=0.0,
            confidence=0.0,
            model_version=0,
            available=False,
        )

    model = bundle["model"]
    feature_names = bundle["feature_names"]
    version = bundle["version"]

    feats = extract_features(profile)
    X = np.array(feats.to_list()).reshape(1, -1)

    predicted_residual = float(model.predict(X)[0])

    # Clamp: cap adjustment at ±30% of GLM pure premium
    max_adj = 0.30 * glm_pure_premium
    predicted_residual = float(np.clip(predicted_residual, -max_adj, max_adj * 1.33))

    adjustment = predicted_residual / glm_pure_premium if glm_pure_premium > 0 else 0.0
    adjustment = float(np.clip(adjustment, -0.30, 0.40))

    # Confidence: simple heuristic based on how far adjustment is from 0
    # High confidence if adjustment is small (GLM was already accurate)
    confidence = float(np.clip(1.0 - abs(adjustment) * 2, 0.50, 0.97))

    return MLAdjustment(
        adjustment=adjustment,
        adjustment_vnd=predicted_residual,
        confidence=confidence,
        model_version=version,
        available=True,
    )


def reload_model():
    """Force reload of cached model (call after retraining)."""
    global _cached_model, _cached_version
    _cached_model = None
    _cached_version = None
