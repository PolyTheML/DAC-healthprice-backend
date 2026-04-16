"""
Smoke tests for the ETL pipeline and the JSON assumption versioning layer.

Uses a fake ProductionDataFetcher that returns canned records so the test
does not hit the Render backend.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from etl.config import ETLConfig
from etl.fetch import ProductionDataFetcher
from etl.pipeline import ETLPipeline
from etl.storage import LocalDatasetWriter
from etl.validate import OutlierDetector, SchemaValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config(tmp_path: Path) -> ETLConfig:
    dataset = tmp_path / "synced"
    dataset.mkdir(parents=True, exist_ok=True)
    assumptions = tmp_path / "assumptions_versions"
    assumptions.mkdir(parents=True, exist_ok=True)
    return ETLConfig(
        production_api_url="https://example.test",
        production_api_key="test-key",
        dataset_dir=dataset,
        sqlite_path=dataset / "quotes.db",
        audit_log_path=dataset / "etl_audit_log.json",
        assumptions_dir=assumptions,
    )


class _FakeFetcher(ProductionDataFetcher):
    def __init__(self, config: ETLConfig, records: list[dict[str, Any]]):
        super().__init__(config)
        self._records = records

    async def fetch_quotes(self, since=None, *, client=None):  # type: ignore[override]
        return list(self._records)


def _quote(id_: int, premium: float, *, age: int = 35, mr: float = 1.2, bmi: float = 22.0) -> dict[str, Any]:
    return {
        "id": id_,
        "created_at": f"2026-04-{15 + (id_ % 2):02d}T10:00:00Z",
        "applicant_profile": {"age": age, "gender": "M", "bmi": bmi},
        "extracted_from": {"province": "phnom_penh"},
        "mortality_ratio": mr,
        "total_annual_premium": premium,
        "underwriting_status": "approved",
    }


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestETLPipeline:
    def test_happy_path_inserts_valid_rows(self, tmp_config):
        records = [_quote(i, premium=500.0) for i in range(1, 11)]
        pipeline = ETLPipeline(tmp_config, fetcher=_FakeFetcher(tmp_config, records))

        result = asyncio.run(pipeline.run_sync())

        assert result.status == "success"
        assert result.rows_fetched == 10
        assert result.rows_validated == 10
        assert result.rows_quarantined == 0
        assert result.rows_invalid == 0
        assert tmp_config.sqlite_path.exists()
        assert tmp_config.audit_log_path.exists()

    def test_outliers_are_quarantined(self, tmp_config):
        records = [_quote(i, premium=500.0) for i in range(1, 10)]
        records.append(_quote(99, premium=100_000.0))  # 200x median → outlier
        pipeline = ETLPipeline(tmp_config, fetcher=_FakeFetcher(tmp_config, records))

        result = asyncio.run(pipeline.run_sync())

        assert result.rows_fetched == 10
        assert result.rows_quarantined == 1
        assert result.rows_validated == 9

    def test_invalid_rows_are_rejected(self, tmp_config):
        records = [_quote(i, premium=500.0) for i in range(1, 6)]
        records.append({"id": 50, "created_at": "2026-04-15", "mortality_ratio": 1.0})  # missing premium
        records.append({"id": 51, "created_at": "2026-04-15", "mortality_ratio": -1.0, "total_annual_premium": 100})  # bad MR
        pipeline = ETLPipeline(tmp_config, fetcher=_FakeFetcher(tmp_config, records))

        result = asyncio.run(pipeline.run_sync())

        assert result.rows_invalid == 2
        assert result.rows_validated == 5
        assert len(result.errors_sample) == 2

    def test_duplicate_rows_skipped_on_rerun(self, tmp_config):
        records = [_quote(i, premium=500.0) for i in range(1, 6)]
        pipeline = ETLPipeline(tmp_config, fetcher=_FakeFetcher(tmp_config, records))

        first = asyncio.run(pipeline.run_sync())
        second = asyncio.run(pipeline.run_sync())

        assert first.rows_validated == 5
        assert second.rows_validated == 0
        assert second.rows_duplicate == 5

    def test_fetch_error_writes_failed_audit_entry(self, tmp_config):
        from etl.fetch import ProductionAPIError

        class _BrokenFetcher(ProductionDataFetcher):
            async def fetch_quotes(self, since=None, *, client=None):  # type: ignore[override]
                raise ProductionAPIError("simulated outage")

        pipeline = ETLPipeline(tmp_config, fetcher=_BrokenFetcher(tmp_config))
        result = asyncio.run(pipeline.run_sync())

        assert result.status == "failed"
        assert result.error == "simulated outage"
        log = json.loads(tmp_config.audit_log_path.read_text(encoding="utf-8"))
        assert log[-1]["status"] == "failed"

    def test_load_valid_quotes_round_trips_profile(self, tmp_config):
        records = [_quote(i, premium=500.0) for i in range(1, 4)]
        pipeline = ETLPipeline(tmp_config, fetcher=_FakeFetcher(tmp_config, records))
        asyncio.run(pipeline.run_sync())

        writer = LocalDatasetWriter(tmp_config)
        rows = writer.load_valid_quotes()

        assert len(rows) == 3
        assert rows[0]["applicant_profile"]["age"] == 35
        assert rows[0]["extracted_from"]["province"] == "phnom_penh"


# ---------------------------------------------------------------------------
# Validator / outlier unit tests
# ---------------------------------------------------------------------------

class TestValidator:
    def test_accepts_well_formed_quote(self, tmp_config):
        ok, err = SchemaValidator(tmp_config).validate_quote(_quote(1, premium=500.0))
        assert ok and err is None

    def test_rejects_missing_required_field(self, tmp_config):
        rec = _quote(1, premium=500.0)
        del rec["mortality_ratio"]
        ok, err = SchemaValidator(tmp_config).validate_quote(rec)
        assert not ok and "mortality_ratio" in (err or "")

    def test_rejects_out_of_range_bmi(self, tmp_config):
        rec = _quote(1, premium=500.0, bmi=500.0)
        ok, err = SchemaValidator(tmp_config).validate_quote(rec)
        assert not ok and "bmi" in (err or "")


class TestOutlierDetector:
    def test_returns_empty_below_min_batch(self, tmp_config):
        recs = [_quote(i, premium=100.0) for i in range(1, 4)]
        assert OutlierDetector(tmp_config).detect_outliers(recs) == set()

    def test_flags_premium_above_threshold(self, tmp_config):
        recs = [_quote(i, premium=100.0) for i in range(1, 10)]
        recs.append(_quote(99, premium=100_000.0))
        flagged = OutlierDetector(tmp_config).detect_outliers(recs)
        assert flagged == {9}


# ---------------------------------------------------------------------------
# Versioning layer
# ---------------------------------------------------------------------------

class TestVersioning:
    def test_active_version_loads_and_materializes(self):
        from medical_reader.pricing import versioning
        from medical_reader.pricing.calculator import calculate_annual_premium

        active_id = versioning.get_active_version_id()
        assert active_id == "v3.0-cambodia-2026-04-14"

        assumptions = versioning.load_active_assumptions()
        assert assumptions["version"] == active_id

        # Smoke-test that the materialized dict drives the existing calculator.
        breakdown = calculate_annual_premium(
            face_amount=100_000,
            policy_term_years=20,
            age=35, gender="M", bmi=22.0,
            smoker=False, alcohol_use="none",
            diabetes=False, hypertension=False,
            hyperlipidemia=False, family_history_chd=False,
            systolic=115, diastolic=75,
            assumptions=assumptions,
        )
        assert breakdown.assumption_version == active_id
        assert breakdown.gross_annual_premium > 0

    def test_version_id_validator_rejects_bad_format(self):
        from medical_reader.pricing import versioning
        with pytest.raises(versioning.InvalidVersionError):
            versioning.validate_version_id("not-a-version")
        versioning.validate_version_id("v3.1-cambodia-2026-04-16")  # ok
