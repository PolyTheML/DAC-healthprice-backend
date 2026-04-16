"""
JSON-backed versioning layer for pricing assumptions.

The existing calculator consumes a dict of dataclass instances (see
`assumptions.py :: ASSUMPTIONS`). This module loads versioned JSON files and
materializes them into the same shape, so `calculator.py` remains unchanged.

Version ID format: `vMAJOR.MINOR-cambodia-YYYY-MM-DD`.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medical_reader.pricing.assumptions import (
    CambodiaEndemicMultipliers,
    CambodiaHealthcareTierDiscount,
    CambodiaOccupationalMultipliers,
    LoadingFactors,
    MortalityAssumptions,
    RiskFactorMultipliers,
    RiskTierThresholds,
)

VERSIONS_DIR = Path(__file__).resolve().parent / "assumptions_versions"
MANIFEST_PATH = VERSIONS_DIR / "VERSION_MANIFEST.json"
VERSION_ID_RE = re.compile(r"^v\d+\.\d+(?:\.\d+)?-[a-z0-9-]+-\d{4}-\d{2}-\d{2}$")


class VersionNotFoundError(KeyError):
    """Raised when a requested version ID is not on disk."""


class InvalidVersionError(ValueError):
    """Raised when a version ID fails format validation."""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _version_path(version_id: str) -> Path:
    return VERSIONS_DIR / f"{version_id}.json"


def validate_version_id(version_id: str) -> None:
    if not VERSION_ID_RE.match(version_id):
        raise InvalidVersionError(
            f"version id {version_id!r} does not match vMAJOR.MINOR-slug-YYYY-MM-DD"
        )


# ---------------------------------------------------------------------------
# Manifest operations
# ---------------------------------------------------------------------------

def read_manifest() -> dict[str, Any]:
    return _read_json(MANIFEST_PATH)


def write_manifest(manifest: dict[str, Any]) -> None:
    _write_json(MANIFEST_PATH, manifest)


def list_versions() -> list[dict[str, Any]]:
    return list(read_manifest().get("versions", []))


def get_active_version_id() -> str:
    return read_manifest()["active_version"]


# ---------------------------------------------------------------------------
# Load / materialize
# ---------------------------------------------------------------------------

def load_version_raw(version_id: str) -> dict[str, Any]:
    path = _version_path(version_id)
    if not path.exists():
        raise VersionNotFoundError(version_id)
    return _read_json(path)


def materialize_assumptions(version_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a version JSON payload into the dataclass-keyed dict that
    `medical_reader.pricing.calculator.calculate_annual_premium` expects.
    """
    params = version_payload["parameters"]
    return {
        "mortality": MortalityAssumptions(
            base_rate_male=dict(params["mortality"]["base_rate_male"]),
            base_rate_female=dict(params["mortality"]["base_rate_female"]),
        ),
        "risk_factors": RiskFactorMultipliers(**params["risk_factors"]),
        "loading": LoadingFactors(**params["loading"]),
        "tiers": RiskTierThresholds(**params["tiers"]),
        "cambodia_occupational": CambodiaOccupationalMultipliers(
            **params["cambodia_occupational"]
        ),
        "cambodia_endemic": CambodiaEndemicMultipliers(**params["cambodia_endemic"]),
        "cambodia_healthcare_tier": CambodiaHealthcareTierDiscount(
            **params["cambodia_healthcare_tier"]
        ),
        "cambodia_mortality_adj": float(params["cambodia_mortality_adj"]),
        "version": version_payload["version"],
    }


def load_active_assumptions() -> dict[str, Any]:
    payload = load_version_raw(get_active_version_id())
    return materialize_assumptions(payload)


def load_assumptions(version_id: str) -> dict[str, Any]:
    return materialize_assumptions(load_version_raw(version_id))


# ---------------------------------------------------------------------------
# Write (promote / rollback / create)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def promote_version(version_id: str, *, reason: str = "manual promote") -> dict[str, Any]:
    """
    Set `active_version = version_id`. Marks prior active as 'archived' and
    the target as 'active'. Returns the updated manifest.
    """
    validate_version_id(version_id)
    if not _version_path(version_id).exists():
        raise VersionNotFoundError(version_id)

    manifest = read_manifest()
    prior_active = manifest.get("active_version")
    if prior_active == version_id:
        return manifest

    manifest["active_version"] = version_id
    for entry in manifest.get("versions", []):
        if entry["version"] == version_id:
            entry["status"] = "active"
        elif entry["version"] == prior_active:
            entry["status"] = "archived"

    manifest.setdefault("recalibration_log", []).append(
        {
            "timestamp": _now_iso(),
            "action": "promote",
            "from_version": prior_active,
            "to_version": version_id,
            "reason": reason,
        }
    )
    write_manifest(manifest)
    return manifest


def rollback_to(version_id: str, *, reason: str = "manual rollback") -> dict[str, Any]:
    """Identical to promote, but logged with `action=rollback` for audit clarity."""
    validate_version_id(version_id)
    if not _version_path(version_id).exists():
        raise VersionNotFoundError(version_id)

    manifest = read_manifest()
    prior_active = manifest.get("active_version")
    manifest["active_version"] = version_id
    for entry in manifest.get("versions", []):
        if entry["version"] == version_id:
            entry["status"] = "active"
        elif entry["version"] == prior_active:
            entry["status"] = "archived"

    manifest.setdefault("recalibration_log", []).append(
        {
            "timestamp": _now_iso(),
            "action": "rollback",
            "from_version": prior_active,
            "to_version": version_id,
            "reason": reason,
        }
    )
    write_manifest(manifest)
    return manifest


def register_candidate_version(
    *,
    version_id: str,
    payload: dict[str, Any],
    reason: str,
    parent_version: str | None,
    auto_promote: bool = False,
) -> dict[str, Any]:
    """
    Write a new version JSON to disk and append a manifest entry.

    - `payload` is the full version document (must include parameters, validation, etc.).
    - `auto_promote=True` flips active_version to this new id (caller is
      responsible for checking fairness before calling with True).
    """
    validate_version_id(version_id)
    path = _version_path(version_id)
    if path.exists():
        raise FileExistsError(f"version {version_id} already exists")

    _write_json(path, payload)

    manifest = read_manifest()
    manifest.setdefault("versions", []).append(
        {
            "version": version_id,
            "created_at": payload.get("created_at", _now_iso()),
            "status": "candidate",
            "parent_version": parent_version,
            "reason": reason,
        }
    )
    write_manifest(manifest)

    if auto_promote:
        return promote_version(version_id, reason=f"auto-promote: {reason}")
    return manifest
