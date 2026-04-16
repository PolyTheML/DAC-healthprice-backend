"""
Local SQLite dataset for synced quote rows, plus the JSON audit log.

Design deviation from ETL_PIPELINE_DESIGN.md: we use a single `quotes.db`
rather than per-day database files. A `synced_at` column preserves the
daily-partitioning signal while keeping the rolling-window query (used by
recalibration) trivial. Audit log is still append-only JSON.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from etl.config import ETLConfig

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    applicant_profile TEXT,
    extracted_from TEXT,
    mortality_ratio REAL NOT NULL,
    total_annual_premium REAL NOT NULL,
    underwriting_status TEXT,
    manual_override INTEGER,
    override_reason TEXT,

    synced_at TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    validation_status TEXT NOT NULL,
    validation_error TEXT,
    sync_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON quotes(created_at);
CREATE INDEX IF NOT EXISTS idx_quotes_synced_at ON quotes(synced_at);
CREATE INDEX IF NOT EXISTS idx_quotes_validation_status ON quotes(validation_status);
"""


def compute_source_hash(record: dict[str, Any]) -> str:
    """Deterministic hash for dedup. Uses id + created_at + premium."""
    payload = json.dumps(
        {
            "id": record.get("id"),
            "created_at": record.get("created_at"),
            "total_annual_premium": record.get("total_annual_premium"),
        },
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_batch_hash(records: Iterable[dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for rec in records:
        hasher.update(compute_source_hash(rec).encode("utf-8"))
    return "sha256:" + hasher.hexdigest()


@contextmanager
def _connect(path: Path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


class LocalDatasetWriter:
    def __init__(self, config: ETLConfig):
        self._config = config
        self._db_path = config.sqlite_path
        self._audit_path = config.audit_log_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA_SQL)

    # ---- Write ----

    def write_quotes(
        self,
        records: list[dict[str, Any]],
        *,
        sync_id: str,
        outlier_indices: set[int],
        validation_errors: dict[int, str],
    ) -> dict[str, int]:
        """
        Insert rows, skipping duplicates (by source_hash).

        Returns stats: {inserted, duplicates, quarantined, invalid}.
        """
        now = datetime.now(timezone.utc).isoformat()
        inserted = duplicates = quarantined = invalid = 0

        with _connect(self._db_path) as conn:
            for idx, rec in enumerate(records):
                source_hash = compute_source_hash(rec)

                if idx in validation_errors:
                    validation_status = "invalid"
                    validation_error: str | None = validation_errors[idx]
                    invalid += 1
                elif idx in outlier_indices:
                    validation_status = "quarantined"
                    validation_error = "outlier: premium exceeds outlier threshold"
                    quarantined += 1
                else:
                    validation_status = "valid"
                    validation_error = None

                profile = rec.get("applicant_profile")
                extracted = rec.get("extracted_from")
                try:
                    conn.execute(
                        """
                        INSERT INTO quotes (
                            id, created_at, applicant_profile, extracted_from,
                            mortality_ratio, total_annual_premium, underwriting_status,
                            manual_override, override_reason,
                            synced_at, source_hash, validation_status, validation_error, sync_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rec.get("id"),
                            rec.get("created_at"),
                            json.dumps(profile) if profile is not None else None,
                            json.dumps(extracted) if extracted is not None else None,
                            float(rec.get("mortality_ratio") or 0.0),
                            float(rec.get("total_annual_premium") or 0.0),
                            rec.get("underwriting_status"),
                            1 if rec.get("manual_override") else 0,
                            rec.get("override_reason"),
                            now,
                            source_hash,
                            validation_status,
                            validation_error,
                            sync_id,
                        ),
                    )
                    if validation_status == "valid":
                        inserted += 1
                except sqlite3.IntegrityError:
                    # UNIQUE(source_hash) collision → already have this row
                    duplicates += 1

        return {
            "inserted": inserted,
            "duplicates": duplicates,
            "quarantined": quarantined,
            "invalid": invalid,
        }

    # ---- Read ----

    def load_valid_quotes(self, *, days_back: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM quotes WHERE validation_status = 'valid'"
        params: tuple[Any, ...] = ()
        if days_back is not None:
            query += " AND datetime(created_at) >= datetime('now', ?)"
            params = (f"-{int(days_back)} days",)
        query += " ORDER BY created_at ASC"

        with _connect(self._db_path) as conn:
            rows = conn.execute(query, params).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            for field in ("applicant_profile", "extracted_from"):
                if item.get(field):
                    try:
                        item[field] = json.loads(item[field])
                    except (TypeError, json.JSONDecodeError):
                        pass
            result.append(item)
        return result

    def get_last_sync_timestamp(self) -> datetime | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT MAX(synced_at) AS last FROM quotes"
            ).fetchone()
        last = row["last"] if row else None
        if not last:
            return None
        try:
            return datetime.fromisoformat(last)
        except ValueError:
            return None

    def count_valid_since(self, since: datetime) -> int:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n FROM quotes
                WHERE validation_status = 'valid' AND datetime(synced_at) >= datetime(?)
                """,
                (since.isoformat(),),
            ).fetchone()
        return int(row["n"] if row else 0)

    # ---- Audit log ----

    def append_audit_entry(self, entry: dict[str, Any]) -> None:
        log = self._read_audit()
        log.append(entry)
        self._audit_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    def read_audit_log(self) -> list[dict[str, Any]]:
        return self._read_audit()

    def _read_audit(self) -> list[dict[str, Any]]:
        if not self._audit_path.exists():
            return []
        try:
            data = json.loads(self._audit_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return []
