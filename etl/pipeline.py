"""
ETL orchestrator: fetch → validate → store → audit.

The pipeline is the single entry point for a sync. Callers (admin API,
future scheduler) should invoke `ETLPipeline.run_sync()` and consume the
returned `SyncResult`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from etl.config import ETLConfig, get_config
from etl.fetch import ProductionAPIError, ProductionDataFetcher
from etl.storage import LocalDatasetWriter, compute_batch_hash
from etl.validate import OutlierDetector, SchemaValidator

logger = logging.getLogger(__name__)


def _new_sync_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    return f"sync_{ts}"


@dataclass
class SyncResult:
    sync_id: str
    sync_start: str
    sync_end: str
    status: str                         # "success" | "failed"
    source: str
    rows_fetched: int = 0
    rows_validated: int = 0              # newly inserted valid rows
    rows_quarantined: int = 0
    rows_invalid: int = 0
    rows_duplicate: int = 0
    data_hash: str | None = None
    error: str | None = None
    errors_sample: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ETLPipeline:
    def __init__(
        self,
        config: ETLConfig | None = None,
        *,
        fetcher: ProductionDataFetcher | None = None,
        writer: LocalDatasetWriter | None = None,
        validator: SchemaValidator | None = None,
        outlier_detector: OutlierDetector | None = None,
    ):
        self._config = config or get_config()
        self._fetcher = fetcher or ProductionDataFetcher(self._config)
        self._writer = writer or LocalDatasetWriter(self._config)
        self._validator = validator or SchemaValidator(self._config)
        self._outliers = outlier_detector or OutlierDetector(self._config)

    async def run_sync(
        self,
        *,
        since: datetime | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> SyncResult:
        """
        Run a full sync. `since` defaults to the last successful sync timestamp.
        Always writes an audit log entry (success or failure).
        """
        sync_id = _new_sync_id()
        start = datetime.now(timezone.utc)
        source = f"{self._config.production_api_url}/admin/etl/quotes"

        if since is None:
            since = self._writer.get_last_sync_timestamp()

        result = SyncResult(
            sync_id=sync_id,
            sync_start=start.isoformat(),
            sync_end=start.isoformat(),
            status="success",
            source=source,
        )

        try:
            records = await self._fetcher.fetch_quotes(since=since, client=client)
        except ProductionAPIError as exc:
            logger.error("ETL fetch failed: %s", exc)
            result.status = "failed"
            result.error = str(exc)
            result.sync_end = datetime.now(timezone.utc).isoformat()
            self._writer.append_audit_entry(result.to_dict())
            return result

        result.rows_fetched = len(records)
        result.data_hash = compute_batch_hash(records) if records else None

        validation_errors: dict[int, str] = {}
        for idx, rec in enumerate(records):
            ok, err = self._validator.validate_quote(rec)
            if not ok and err is not None:
                validation_errors[idx] = err

        valid_indices = [i for i in range(len(records)) if i not in validation_errors]
        valid_records = [records[i] for i in valid_indices]
        outlier_local = self._outliers.detect_outliers(valid_records)
        outlier_global = {valid_indices[i] for i in outlier_local}

        stats = self._writer.write_quotes(
            records,
            sync_id=sync_id,
            outlier_indices=outlier_global,
            validation_errors=validation_errors,
        )

        result.rows_validated = stats["inserted"]
        result.rows_quarantined = stats["quarantined"]
        result.rows_invalid = stats["invalid"]
        result.rows_duplicate = stats["duplicates"]
        result.errors_sample = list(validation_errors.values())[:5]
        result.sync_end = datetime.now(timezone.utc).isoformat()

        self._writer.append_audit_entry(result.to_dict())
        logger.info(
            "ETL sync %s complete: fetched=%d valid=%d quarantined=%d invalid=%d duplicates=%d",
            sync_id,
            result.rows_fetched,
            result.rows_validated,
            result.rows_quarantined,
            result.rows_invalid,
            result.rows_duplicate,
        )
        return result
