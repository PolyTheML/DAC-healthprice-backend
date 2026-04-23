"""
Streaming Risk Model — Online learning deviation layer.

Learns the residual between static GLM predictions and actual
observed risk from telemetry.  Falls back to a simple heuristic
if the ``river`` library is not installed.
"""
from __future__ import annotations
import logging
import warnings
from typing import Optional

log = logging.getLogger(__name__)

try:
    from river import compose, preprocessing, linear_model, metrics
    RIVER_AVAILABLE = True
except ImportError:  # pragma: no cover
    RIVER_AVAILABLE = False
    warnings.warn("river not installed — StreamingRiskModel will use heuristic fallback")


class StreamingRiskModel:
    """
    Online-learning deviation model.

    Formula used downstream:
        Final Premium = GLM_Anchor × deviation
        where deviation = clamp(1.0 + raw_prediction, 0.5, 2.0)
    """

    def __init__(self):
        self.model: Optional[object] = None
        self.metric: Optional[object] = None

        if RIVER_AVAILABLE:
            self.model = compose.Pipeline(
                preprocessing.StandardScaler(),
                linear_model.LinearRegression(intercept_lr=0.01)
            )
            self.metric = metrics.MAE()
            log.info("StreamingRiskModel initialised with river LinearRegression")
        else:
            log.warning("StreamingRiskModel running in heuristic fallback mode")

        # Heuristic weights used when river is absent
        self._heuristic_weights = {
            "speed_kmh": 0.001,
            "harsh_braking": 0.15,
            "lane_shifts": 0.05,
            "night_driving": 0.10,
        }

    # ── Feature engineering ──────────────────────────────────────────────────

    @staticmethod
    def _to_features(x: dict) -> dict:
        """Convert raw/masked telemetry dict into numeric features."""
        hour = x.get("hour_bucket", 12)
        return {
            "speed_kmh": float(x.get("speed_kmh", 0)),
            "harsh_braking": 1.0 if x.get("harsh_braking") else 0.0,
            "lane_shifts": float(x.get("lane_shifts", 0)),
            "night_driving": 1.0 if hour in (0, 1, 2, 3, 4, 5, 6, 22, 23) else 0.0,
        }

    # ── Public API ───────────────────────────────────────────────────────────

    def predict_deviation(self, x: dict) -> float:
        """Return a multiplier (1.0 = baseline, 1.15 = +15% risk)."""
        features = self._to_features(x)

        if self.model is not None:
            raw = self.model.predict_one(features)
            return max(0.5, min(2.0, 1.0 + raw))

        # Heuristic fallback
        delta = 0.0
        delta += features["speed_kmh"] * self._heuristic_weights["speed_kmh"]
        delta += features["harsh_braking"] * self._heuristic_weights["harsh_braking"]
        delta += features["lane_shifts"] * self._heuristic_weights["lane_shifts"]
        delta += features["night_driving"] * self._heuristic_weights["night_driving"]
        return max(0.5, min(2.0, 1.0 + delta))

    def update_one(self, x: dict, y: float) -> float:
        """
        Learn from one observation.

        *x*  — telemetry features  
        *y*  — observed residual (actual_loss / glm_anchor − 1.0) or similar target
        """
        features = self._to_features(x)

        if self.model is not None:
            pred = self.model.predict_one(features)
            self.model.learn_one(features, y)
            if self.metric is not None:
                self.metric.update(y, pred)
            return pred

        return self.predict_deviation(x)

    def get_metric(self) -> Optional[float]:
        """Return current MAE if river is available."""
        if self.metric is not None:
            return self.metric.get()
        return None


# Singleton instance shared across requests (single-process on Render free tier)
_global_streaming_model = StreamingRiskModel()
