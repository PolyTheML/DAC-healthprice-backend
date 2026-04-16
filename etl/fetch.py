"""
HTTP client for fetching production quote data from the Render backend.

Uses the admin ETL endpoint (API-only access, API-key auth) per the agreed
design. The endpoint `/admin/etl/quotes` must be implemented on the Render
side; until then, fetch_quotes() will raise a clear ConnectionError.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from etl.config import ETLConfig


class ProductionAPIError(RuntimeError):
    """Raised when the Render admin ETL endpoint cannot be reached or authed."""


class ProductionDataFetcher:
    """Pull quote rows from the Render backend via the admin ETL endpoint."""

    def __init__(self, config: ETLConfig):
        self._config = config
        self._base_url = config.production_api_url
        self._headers: dict[str, str] = {"Accept": "application/json"}
        if config.production_api_key:
            self._headers["X-API-Key"] = config.production_api_key

    async def fetch_quotes(
        self,
        since: datetime | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        """
        GET {base}/admin/etl/quotes?since=<iso>

        Expected response: JSON array of hp_quote_log rows. Each row should
        contain at minimum: id, created_at, applicant_profile, extracted_from,
        mortality_ratio, total_annual_premium, underwriting_status.

        Raises ProductionAPIError on transport or auth failure.
        """
        params: dict[str, str] = {}
        if since is not None:
            params["since"] = since.isoformat()

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self._config.request_timeout_seconds)
            close_client = True

        try:
            response = await client.get(
                f"{self._base_url}/admin/etl/quotes",
                params=params,
                headers=self._headers,
            )
        except httpx.HTTPError as exc:
            raise ProductionAPIError(f"ETL fetch failed: {exc}") from exc
        finally:
            if close_client:
                await client.aclose()

        if response.status_code == 401 or response.status_code == 403:
            raise ProductionAPIError(
                f"Admin ETL auth failed ({response.status_code}); check PRODUCTION_API_KEY"
            )
        if response.status_code == 404:
            raise ProductionAPIError(
                "/admin/etl/quotes not found on production backend; "
                "endpoint must be deployed before ETL can run"
            )
        if response.status_code >= 400:
            raise ProductionAPIError(
                f"ETL fetch returned {response.status_code}: {response.text[:200]}"
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise ProductionAPIError(
                f"Expected list of quote rows, got {type(payload).__name__}"
            )
        return payload
