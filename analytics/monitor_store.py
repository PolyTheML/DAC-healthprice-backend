"""
SQLite-backed persistence for PSI snapshots.

Replaces the mock fallback in analytics.monitor._mock_psi_series
with real historical data. Schema is minimal so it works on Render's
free tier without requiring PostgreSQL schema migrations.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "psi_monitor.db"


@dataclass
class PSISnapshot:
    id: int | None
    timestamp: str
    model_scope: str          # e.g. "vietnam", "cambodia_health", "auto"
    metric_name: str          # e.g. "mortality_multiplier", "health_score"
    psi_score: float
    status: str               # "green" | "amber" | "red"
    n_samples: int
    season_window: str | None # e.g. "same_month_yoy:rainy"
    cohort_segment: str | None # e.g. "region:Southwest"


class MonitorStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _ensure_table(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS psi_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model_scope TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    psi_score REAL NOT NULL,
                    status TEXT NOT NULL,
                    n_samples INTEGER NOT NULL DEFAULT 0,
                    season_window TEXT,
                    cohort_segment TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_scope_metric ON psi_snapshots(model_scope, metric_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_timestamp ON psi_snapshots(timestamp)"
            )
            conn.commit()

    def save(self, snapshot: PSISnapshot) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO psi_snapshots
                (timestamp, model_scope, metric_name, psi_score, status, n_samples, season_window, cohort_segment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.timestamp,
                    snapshot.model_scope,
                    snapshot.metric_name,
                    snapshot.psi_score,
                    snapshot.status,
                    snapshot.n_samples,
                    snapshot.season_window,
                    snapshot.cohort_segment,
                ),
            )
            conn.commit()
            return cur.lastrowid or 0

    def save_report(self, model_scope: str, report_dict: dict[str, Any]) -> list[int]:
        """Persist all entries from a MonitoringReport dict. Returns inserted IDs."""
        ts = report_dict.get("generated_at", datetime.now(timezone.utc).isoformat())
        ids: list[int] = []

        primary = report_dict.get("primary", {})
        ids.append(self.save(PSISnapshot(
            id=None,
            timestamp=ts,
            model_scope=model_scope,
            metric_name=primary.get("metric", "unknown"),
            psi_score=primary.get("psi", 0.0),
            status=primary.get("status", "green"),
            n_samples=primary.get("n_samples", 0),
            season_window=None,
            cohort_segment=None,
        )))

        for sec in report_dict.get("secondary", []):
            ids.append(self.save(PSISnapshot(
                id=None,
                timestamp=ts,
                model_scope=model_scope,
                metric_name=sec.get("metric", "unknown"),
                psi_score=sec.get("psi", 0.0),
                status=sec.get("status", "green"),
                n_samples=sec.get("n_samples", 0),
                season_window=None,
                cohort_segment=None,
            )))

        for cohort in report_dict.get("cohorts", []):
            ids.append(self.save(PSISnapshot(
                id=None,
                timestamp=ts,
                model_scope=model_scope,
                metric_name=cohort.get("metric", "unknown"),
                psi_score=cohort.get("psi", 0.0),
                status=cohort.get("status", "green"),
                n_samples=cohort.get("n_samples", 0),
                season_window=None,
                cohort_segment=f"{cohort.get('segment_column')}:{cohort.get('segment_value')}",
            )))

        seasonal = report_dict.get("seasonal")
        if seasonal:
            ids.append(self.save(PSISnapshot(
                id=None,
                timestamp=ts,
                model_scope=model_scope,
                metric_name=seasonal.get("metric", "unknown"),
                psi_score=seasonal.get("psi", 0.0),
                status=seasonal.get("status", "green"),
                n_samples=seasonal.get("n_current", 0),
                season_window=seasonal.get("season_window"),
                cohort_segment=None,
            )))

        return ids

    def get_time_series(
        self,
        model_scope: str,
        metric_name: str,
        window_days: int = 30,
        cohort_segment: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return daily aggregated PSI for the last N days."""
        since = datetime.now(timezone.utc).isoformat()[:10]  # placeholder; SQLite date math below
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if cohort_segment:
                rows = conn.execute(
                    """
                    SELECT date(timestamp) as date, AVG(psi_score) as psi, COUNT(*) as n
                    FROM psi_snapshots
                    WHERE model_scope = ? AND metric_name = ? AND cohort_segment = ?
                          AND timestamp >= datetime('now', '-{} days')
                    GROUP BY date(timestamp)
                    ORDER BY date(timestamp)
                    """.format(window_days),
                    (model_scope, metric_name, cohort_segment),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT date(timestamp) as date, AVG(psi_score) as psi, COUNT(*) as n
                    FROM psi_snapshots
                    WHERE model_scope = ? AND metric_name = ?
                          AND timestamp >= datetime('now', '-{} days')
                    GROUP BY date(timestamp)
                    ORDER BY date(timestamp)
                    """.format(window_days),
                    (model_scope, metric_name),
                ).fetchall()
            return [
                {"date": r["date"], "psi": round(r["psi"], 6), "n_cases": r["n"]}
                for r in rows
            ]

    def get_latest(
        self,
        model_scope: str,
        metric_name: str,
        cohort_segment: str | None = None,
    ) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if cohort_segment:
                row = conn.execute(
                    """
                    SELECT * FROM psi_snapshots
                    WHERE model_scope = ? AND metric_name = ? AND cohort_segment = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (model_scope, metric_name, cohort_segment),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM psi_snapshots
                    WHERE model_scope = ? AND metric_name = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                    """,
                    (model_scope, metric_name),
                ).fetchone()
            return dict(row) if row else None
