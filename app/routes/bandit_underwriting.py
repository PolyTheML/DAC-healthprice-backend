"""
Adaptive Underwriting Bandit API — Thesis Demo Routes

Provides REST endpoints for running contextual bandit simulations
(LinUCB, LinTS, Epsilon-Greedy, Static XGB) on the Cambodia health
dataset and returning aggregated results for visualisation.
"""
from __future__ import annotations

import time
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/rl", tags=["rl-underwriting"])

# ── Lazy-loaded globals ────────────────────────────────────────────────────
# Render free tier has slow CPU; loading pandas + xgboost + dataset at import
# time can exceed the 30s startup health-check window. We load on first use.

_X = None
_DF_RAW = None
_FEATURES = None
_N_FEATURES = None
_ALGORITHMS = None


def _ensure_loaded():
    """Lazy-load dataset and algorithm factories (thread-safe on CPython GIL)."""
    global _X, _DF_RAW, _FEATURES, _N_FEATURES, _ALGORITHMS
    if _X is not None:
        return
    import pickle
    from pathlib import Path
    cache_path = Path(__file__).parent.parent / "rl" / "data" / "cambodia_cache.pkl"
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            cache = pickle.load(f)
        _X = cache["X"]
        _DF_RAW = cache["df_raw"]
        _FEATURES = cache["features"]
    else:
        from app.rl.underwriting_bandit import preprocess_cambodia_data
        _X, _DF_RAW, _FEATURES = preprocess_cambodia_data()
    _N_FEATURES = _X.shape[1]
    from app.rl.underwriting_bandit import (
        EpsilonGreedy,
        LinTS,
        LinUCB,
        StaticXGBBaseline,
    )
    _ALGORITHMS = {
        "LinUCB": lambda seed=42: LinUCB(n_actions=4, n_features=_N_FEATURES, alpha=1.0),
        "LinTS": lambda seed=42: LinTS(n_actions=4, n_features=_N_FEATURES, v2=1.0, seed=seed),
        "EpsilonGreedy": lambda seed=42: EpsilonGreedy(n_actions=4, n_features=_N_FEATURES, epsilon=0.15, seed=seed),
        "StaticXGB": lambda seed=42: StaticXGBBaseline(),
    }


# ── Request / Response Models ──────────────────────────────────────────────

class SimulateRequest(BaseModel):
    algorithm: Literal["LinUCB", "LinTS", "EpsilonGreedy", "StaticXGB"] = Field("LinUCB")
    n_rounds: int = Field(5000, ge=100, le=20000)
    seed: int = Field(42, ge=0, le=99999)


class SimulateResponse(BaseModel):
    algorithm: str
    n_rounds: int
    seed: int
    total_reward: float
    total_regret: float
    avg_regret_last_500: float
    action_distribution: dict[str, float]
    cumulative_rewards: list[float]
    cumulative_regrets: list[float]
    action_history: list[int]
    reward_history: list[float]
    regret_history: list[float]
    elapsed_ms: float


class DecideRequest(BaseModel):
    algorithm: Literal["LinUCB", "LinTS", "EpsilonGreedy", "StaticXGB"] = Field("LinUCB")
    seed: int = Field(42, ge=0, le=99999)


class DecideResponse(BaseModel):
    applicant_index: int
    algorithm: str
    action: int
    action_name: str
    expected_rewards: list[float]
    context: list[float]
    applicant: dict


class FairnessResponse(BaseModel):
    algorithm: str
    n_rounds: int
    seed: int
    region_psi: float
    region_psi_status: str
    occupation_psi: float
    occupation_psi_status: str
    region_approval_rates: list[dict]
    occupation_approval_rates: list[dict]
    parity_check_passed: bool


# ── Helpers ────────────────────────────────────────────────────────────────


def _compute_psi(expected_dist: np.ndarray, actual_dist: np.ndarray) -> float:
    eps = 1e-8
    expected_dist = expected_dist / (expected_dist.sum() + eps)
    actual_dist = actual_dist / (actual_dist.sum() + eps)
    psi = 0.0
    for e, a in zip(expected_dist, actual_dist):
        if e > eps:
            psi += (a - e) * np.log((a + eps) / (e + eps))
        elif a > eps:
            psi += a - e
    return float(psi)


def _psi_status(psi: float) -> str:
    if psi < 0.10:
        return "GREEN"
    if psi < 0.25:
        return "AMBER"
    return "RED"


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/algorithms")
async def list_algorithms():
    """List available bandit algorithms."""
    return {
        "algorithms": [
            {"id": "LinUCB", "name": "Linear Upper Confidence Bound", "type": "contextual_bandit"},
            {"id": "LinTS", "name": "Linear Thompson Sampling", "type": "contextual_bandit"},
            {"id": "EpsilonGreedy", "name": "Epsilon-Greedy", "type": "contextual_bandit"},
            {"id": "StaticXGB", "name": "Static XGBoost Baseline", "type": "static_rule"},
        ]
    }


@router.get("/applicants")
async def get_applicants(page: int = 1, limit: int = 50):
    """Paginated view of the synthetic Cambodia dataset."""
    _ensure_loaded()
    total = len(_DF_RAW)
    start = (page - 1) * limit
    end = min(start + limit, total)
    if start >= total:
        raise HTTPException(status_code=400, detail="Page out of range")

    rows = _DF_RAW.iloc[start:end].copy()
    rows = rows.fillna("")  # JSON serialisation safety
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "applicants": rows.to_dict(orient="records"),
    }


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(body: SimulateRequest):
    """Run a bandit simulation and return time-series metrics."""
    _ensure_loaded()
    if body.algorithm not in _ALGORITHMS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {body.algorithm}")

    from app.rl.underwriting_bandit import ACTION_NAMES, run_bandit

    t0 = time.perf_counter()
    bandit = _ALGORITHMS[body.algorithm](seed=body.seed)
    result = run_bandit(body.algorithm, bandit, _X.copy(), _DF_RAW, body.n_rounds, seed=body.seed)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    action_dist = {
        ACTION_NAMES[i]: int(np.bincount(result.actions, minlength=4)[i])
        for i in range(4)
    }
    action_dist_pct = {
        ACTION_NAMES[i]: round(action_dist[ACTION_NAMES[i]] / body.n_rounds, 4)
        for i in range(4)
    }

    return SimulateResponse(
        algorithm=result.algorithm,
        n_rounds=body.n_rounds,
        seed=body.seed,
        total_reward=float(result.cumulative_rewards[-1]),
        total_regret=float(result.cumulative_regrets[-1]),
        avg_regret_last_500=float(np.mean(result.regrets[-500:])),
        action_distribution=action_dist_pct,
        cumulative_rewards=result.cumulative_rewards.tolist(),
        cumulative_regrets=result.cumulative_regrets.tolist(),
        action_history=result.actions.tolist(),
        reward_history=result.rewards.tolist(),
        regret_history=result.regrets.tolist(),
        elapsed_ms=elapsed_ms,
    )


@router.post("/decide", response_model=DecideResponse)
async def decide(body: DecideRequest):
    """Run a single decision for one applicant (step-through mode)."""
    _ensure_loaded()
    if body.algorithm not in _ALGORITHMS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {body.algorithm}")

    from app.rl.underwriting_bandit import ACTION_NAMES, expected_rewards

    # For decide endpoint, applicant_index comes from frontend (0-1999)
    # Validate bounds manually since we can't use len(_DF_RAW) in Field at import time
    if not (0 <= body.applicant_index < len(_DF_RAW)):
        raise HTTPException(status_code=400, detail=f"applicant_index must be between 0 and {len(_DF_RAW)-1}")

    context = _X[body.applicant_index]
    row = _DF_RAW.iloc[body.applicant_index]
    bandit = _ALGORITHMS[body.algorithm](seed=body.seed)

    if hasattr(bandit, '_preprocess_row'):
        action = bandit.select_action(context, row)
    else:
        action = bandit.select_action(context)

    exp_rewards = expected_rewards(row)

    applicant = row.to_dict()
    for k, v in applicant.items():
        if isinstance(v, (np.integer, np.floating)):
            applicant[k] = float(v)
        elif pd.isna(v):
            applicant[k] = None

    return DecideResponse(
        applicant_index=body.applicant_index,
        algorithm=body.algorithm,
        action=int(action),
        action_name=ACTION_NAMES[action],
        expected_rewards=exp_rewards.tolist(),
        context=context.tolist(),
        applicant=applicant,
    )


@router.get("/fairness")
async def fairness(
    algorithm: Literal["LinUCB", "LinTS", "EpsilonGreedy", "StaticXGB"] = "LinUCB",
    n_rounds: int = 5000,
    seed: int = 42,
):
    """Run a bandit simulation and compute fairness metrics (PSI + parity)."""
    _ensure_loaded()
    if algorithm not in _ALGORITHMS:
        raise HTTPException(status_code=400, detail=f"Unknown algorithm: {algorithm}")

    from app.rl.underwriting_bandit import ACTION_STANDARD, ACTION_RATED, run_bandit

    bandit = _ALGORITHMS[algorithm](seed=seed)
    result = run_bandit(algorithm, bandit, _X.copy(), _DF_RAW, n_rounds, seed=seed)

    decisions = pd.DataFrame({
        "round": np.arange(n_rounds),
        "action": result.actions,
        "region": [_DF_RAW.iloc[i % len(_DF_RAW)]["region"] for i in range(n_rounds)],
        "occupation": [_DF_RAW.iloc[i % len(_DF_RAW)]["occupation"] for i in range(n_rounds)],
    })
    decisions["approved"] = decisions["action"].isin([ACTION_STANDARD, ACTION_RATED])

    # Region approval rates
    region_labels = sorted(_DF_RAW["region"].unique())
    region_stats = []
    for region in region_labels:
        subset = decisions[decisions["region"] == region]
        total = len(subset)
        approved = int(subset["approved"].sum())
        rate = approved / total if total > 0 else 0.0
        region_stats.append({"region": region, "total": total, "approved": approved, "rate": round(rate, 4)})

    max_region_rate = max(r["rate"] for r in region_stats)
    for r in region_stats:
        r["parity_ok"] = r["rate"] >= 0.5 * max_region_rate

    # Occupation approval rates
    occ_labels = sorted(_DF_RAW["occupation"].unique())
    occ_stats = []
    for occ in occ_labels:
        subset = decisions[decisions["occupation"] == occ]
        total = len(subset)
        approved = int(subset["approved"].sum())
        rate = approved / total if total > 0 else 0.0
        occ_stats.append({"occupation": occ, "total": total, "approved": approved, "rate": round(rate, 4)})

    max_occ_rate = max(r["rate"] for r in occ_stats)
    for r in occ_stats:
        r["parity_ok"] = r["rate"] >= 0.5 * max_occ_rate

    # PSI
    full_r = np.array([_DF_RAW["region"].value_counts().get(r, 0) for r in region_labels])
    app_r = np.array([decisions[decisions["approved"]]["region"].value_counts().get(r, 0) for r in region_labels])
    region_psi = _compute_psi(full_r, app_r)

    full_o = np.array([_DF_RAW["occupation"].value_counts().get(o, 0) for o in occ_labels])
    app_o = np.array([decisions[decisions["approved"]]["occupation"].value_counts().get(o, 0) for o in occ_labels])
    occ_psi = _compute_psi(full_o, app_o)

    parity_passed = (
        all(r["parity_ok"] for r in region_stats)
        and all(r["parity_ok"] for r in occ_stats)
        and region_psi < 0.25
        and occ_psi < 0.25
    )

    return FairnessResponse(
        algorithm=algorithm,
        n_rounds=n_rounds,
        seed=seed,
        region_psi=round(region_psi, 4),
        region_psi_status=_psi_status(region_psi),
        occupation_psi=round(occ_psi, 4),
        occupation_psi_status=_psi_status(occ_psi),
        region_approval_rates=region_stats,
        occupation_approval_rates=occ_stats,
        parity_check_passed=parity_passed,
    )
