"""
Tests for medical_reader/calibration.py.

Seeds the local SQLite with synthetic quote rows, then runs the engine.
Versioning side-effects (reading/writing the real assumptions_versions/
directory) are isolated by monkeypatching versioning module paths at the
start of each test.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path
from typing import Any

import pytest

from etl.config import ETLConfig
from etl.storage import LocalDatasetWriter
from medical_reader import calibration as cal_module
from medical_reader.pricing import versioning


REPO_ROOT = Path(__file__).resolve().parent
REAL_VERSIONS_DIR = REPO_ROOT / "medical_reader" / "pricing" / "assumptions_versions"


@pytest.fixture
def tmp_config(tmp_path: Path) -> ETLConfig:
    dataset = tmp_path / "synced"
    dataset.mkdir()
    assumptions = tmp_path / "assumptions_versions"
    assumptions.mkdir()
    return ETLConfig(
        production_api_url="https://example.test",
        production_api_key=None,
        dataset_dir=dataset,
        sqlite_path=dataset / "quotes.db",
        audit_log_path=dataset / "etl_audit_log.json",
        assumptions_dir=assumptions,
        recalibration_min_quotes=10,
        recalibration_max_change_pct=20.0,
    )


@pytest.fixture
def isolated_versions(tmp_path: Path, monkeypatch):
    """Copy the real v3.0 JSON + manifest into a tmp dir and repoint versioning."""
    target = tmp_path / "assumptions_versions"
    target.mkdir(exist_ok=True)
    for name in ("v3.0-cambodia-2026-04-14.json", "VERSION_MANIFEST.json"):
        shutil.copy(REAL_VERSIONS_DIR / name, target / name)
    monkeypatch.setattr(versioning, "VERSIONS_DIR", target)
    monkeypatch.setattr(versioning, "MANIFEST_PATH", target / "VERSION_MANIFEST.json")
    return target


def _seed_quote(
    id_: int,
    *,
    occupation: str = "office_desk",
    province: str = "phnom_penh",
    healthcare_tier: str = "tier_b",
    gender: str = "M",
    age: int = 35,
    bmi: float = 22.0,
    mr: float = 1.2,
    premium: float = 500.0,
    status: str = "approved",
    manual_override: bool = False,
) -> dict[str, Any]:
    return {
        "id": id_,
        "created_at": "2026-04-15T10:00:00Z",
        "applicant_profile": {"age": age, "gender": gender, "bmi": bmi},
        "extracted_from": {
            "province": province,
            "occupation": occupation,
            "healthcare_tier": healthcare_tier,
        },
        "mortality_ratio": mr,
        "total_annual_premium": premium,
        "underwriting_status": status,
        "manual_override": manual_override,
    }


def _seed_db(writer: LocalDatasetWriter, quotes: list[dict[str, Any]]) -> None:
    writer.write_quotes(
        quotes,
        sync_id="seed",
        outlier_indices=set(),
        validation_errors={},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCalibrationEngine:
    def test_insufficient_data_short_circuits(self, tmp_config, isolated_versions):
        writer = LocalDatasetWriter(tmp_config)
        _seed_db(writer, [_seed_quote(i) for i in range(1, 4)])   # only 3 < threshold 10

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.run_analysis(trigger="manual", days_back=90)

        assert report.status == "insufficient_data"
        assert report.candidate_version is None
        assert report.total_valid_quotes == 3

    def test_analysis_produces_cohort_stats(self, tmp_config, isolated_versions):
        writer = LocalDatasetWriter(tmp_config)
        quotes = []
        # 15 office_desk baseline quotes (MR ~1.0)
        for i in range(1, 16):
            quotes.append(_seed_quote(i, occupation="office_desk", mr=1.05))
        # 8 motorbike_courier quotes with HIGHER observed MR
        for i in range(16, 24):
            quotes.append(_seed_quote(i, occupation="motorbike_courier", mr=1.55))
        _seed_db(writer, quotes)

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.run_analysis(trigger="manual", days_back=90)

        assert report.status in ("candidate_ready", "no_change_needed")
        assert report.total_valid_quotes == 23

        cohorts_by_key = {(c.cohort_type, c.cohort): c for c in report.cohort_stats}
        assert ("occupation", "office_desk") in cohorts_by_key
        assert ("occupation", "motorbike_courier") in cohorts_by_key
        assert cohorts_by_key[("occupation", "motorbike_courier")].n == 8

    def test_proposal_auto_promotes_when_fairness_passes(self, tmp_config, isolated_versions):
        writer = LocalDatasetWriter(tmp_config)
        # Balanced approval rates across genders + occupations → fairness passes
        quotes = []
        id_ = 1
        # office_desk baseline MR ~1.0; motorbike_courier MR ~2.0 → empirical ~2.0×
        # baseline, which swings the proposed multiplier well past the 0.5% threshold.
        for occ, mr in [("office_desk", 1.00), ("motorbike_courier", 2.00)]:
            for gender in ("M", "F"):
                for _ in range(10):
                    quotes.append(
                        _seed_quote(id_, occupation=occ, gender=gender, mr=mr, status="approved")
                    )
                    id_ += 1
        _seed_db(writer, quotes)

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.propose_candidate_version(trigger="manual", days_back=90)

        assert report.fairness is not None
        assert report.fairness.status == "pass"
        assert report.candidate_version is not None
        assert report.candidate_version.startswith("v3.1-cambodia-")
        assert report.auto_promoted is True

        # Active version flipped to candidate
        assert versioning.get_active_version_id() == report.candidate_version

        # File materialized
        payload = versioning.load_version_raw(report.candidate_version)
        assert payload["parent_version"] == "v3.0-cambodia-2026-04-14"
        assert "cambodia_occupational" in payload["parameters"]

        # Courier multiplier should have moved toward empirical (but stability-capped)
        courier_old = 1.45
        courier_new = payload["parameters"]["cambodia_occupational"]["motorbike_courier"]
        assert courier_new != courier_old
        assert 0.75 <= courier_new <= 1.50
        # Stability weighting (0.9 current + 0.1 empirical) and ±20% cap both apply
        assert abs(courier_new - courier_old) / courier_old <= 0.20 + 1e-6

    def test_proposal_blocked_on_fairness_fail(self, tmp_config, isolated_versions):
        writer = LocalDatasetWriter(tmp_config)
        quotes = []
        id_ = 1
        # Wildly imbalanced approval rates: males 100% approved, females 10% approved → DI < 0.80.
        # Separately, courier MR (2.0) vs office_desk baseline MR (1.0) triggers a proposed change.
        for _ in range(15):
            quotes.append(_seed_quote(id_, occupation="motorbike_courier", gender="M", mr=2.0, status="approved"))
            id_ += 1
        for idx in range(15):
            st = "approved" if idx == 0 else "declined"
            quotes.append(_seed_quote(id_, occupation="motorbike_courier", gender="F", mr=2.0, status=st))
            id_ += 1
        for _ in range(15):
            quotes.append(_seed_quote(id_, occupation="office_desk", gender="M", mr=1.0, status="approved"))
            id_ += 1
        _seed_db(writer, quotes)

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.propose_candidate_version(trigger="manual", days_back=90)

        assert report.fairness is not None
        assert report.fairness.status == "fail"
        assert report.status == "candidate_created_fairness_fail"
        assert report.candidate_version is not None
        assert report.auto_promoted is False
        # Active version unchanged
        assert versioning.get_active_version_id() == "v3.0-cambodia-2026-04-14"

    def test_no_change_when_cohorts_all_match_baseline(self, tmp_config, isolated_versions):
        writer = LocalDatasetWriter(tmp_config)
        # Everyone office_desk with similar MRs → no occupation cohort diverges
        quotes = [_seed_quote(i, occupation="office_desk", mr=1.0 + (i % 3) * 0.02) for i in range(1, 21)]
        _seed_db(writer, quotes)

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.propose_candidate_version(trigger="manual", days_back=90)

        assert report.status == "no_change_needed"
        assert report.candidate_version is None
        assert report.auto_promoted is False

    def test_candidate_version_preserves_unchanged_groups(self, tmp_config, isolated_versions):
        """Endemic (province) multipliers are never proposed for change."""
        writer = LocalDatasetWriter(tmp_config)
        quotes = []
        id_ = 1
        for _ in range(15):
            quotes.append(_seed_quote(id_, occupation="office_desk", province="mondulkiri", mr=1.05))
            id_ += 1
        for _ in range(10):
            quotes.append(_seed_quote(id_, occupation="motorbike_courier", province="phnom_penh", mr=1.55))
            id_ += 1
        _seed_db(writer, quotes)

        engine = cal_module.CalibrationEngine(tmp_config, writer=writer)
        report = engine.propose_candidate_version(trigger="manual", days_back=90)

        if report.candidate_version:
            payload = versioning.load_version_raw(report.candidate_version)
            # Endemic multipliers unchanged from parent
            parent_payload = json.loads(
                (REAL_VERSIONS_DIR / "v3.0-cambodia-2026-04-14.json").read_text(encoding="utf-8")
            )
            assert (
                payload["parameters"]["cambodia_endemic"]
                == parent_payload["parameters"]["cambodia_endemic"]
            )
