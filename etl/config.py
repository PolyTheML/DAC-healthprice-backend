"""
ETL configuration loaded from environment variables.

All paths resolve relative to the repository root so the module works
regardless of the current working directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class ETLConfig:
    production_api_url: str
    production_api_key: str | None
    dataset_dir: Path
    sqlite_path: Path
    audit_log_path: Path
    assumptions_dir: Path

    # Validation / outlier thresholds
    outlier_premium_multiplier: float = 10.0
    min_age: int = 0
    max_age: int = 120
    min_bmi: float = 10.0
    max_bmi: float = 60.0

    # Recalibration guardrails (consumed by the calibration engine)
    recalibration_min_quotes: int = 20
    recalibration_max_change_pct: float = 20.0

    # HTTP
    request_timeout_seconds: float = 30.0


def get_config() -> ETLConfig:
    """Read ETL settings from env with repo-rooted defaults."""
    dataset_dir = Path(
        os.getenv("LOCAL_DATASET_PATH", REPO_ROOT / "data" / "synced")
    ).resolve()
    assumptions_dir = Path(
        os.getenv(
            "ASSUMPTIONS_PATH",
            REPO_ROOT / "medical_reader" / "pricing" / "assumptions_versions",
        )
    ).resolve()

    dataset_dir.mkdir(parents=True, exist_ok=True)
    assumptions_dir.mkdir(parents=True, exist_ok=True)

    return ETLConfig(
        production_api_url=os.getenv(
            "PRODUCTION_API_URL", "https://dac-healthprice-api.onrender.com"
        ).rstrip("/"),
        production_api_key=os.getenv("PRODUCTION_API_KEY"),
        dataset_dir=dataset_dir,
        sqlite_path=dataset_dir / "quotes.db",
        audit_log_path=dataset_dir / "etl_audit_log.json",
        assumptions_dir=assumptions_dir,
        outlier_premium_multiplier=float(os.getenv("OUTLIER_PREMIUM_MULTIPLIER", "10.0")),
        recalibration_min_quotes=int(os.getenv("RECALIBRATION_MIN_QUOTES", "20")),
        recalibration_max_change_pct=float(os.getenv("RECALIBRATION_MAX_CHANGE_PCT", "20.0")),
        request_timeout_seconds=float(os.getenv("ETL_REQUEST_TIMEOUT", "30.0")),
    )
