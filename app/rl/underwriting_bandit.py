"""
Core underwriting bandit module (ported from thesis for DAC platform demo).

Implements contextual bandit algorithms for adaptive health insurance underwriting:
- LinUCB (Li et al. 2010)
- Linear Thompson Sampling (Agrawal & Goyal 2013)
- Epsilon-Greedy

Also includes:
- Cambodia dataset preprocessor
- Actuarial reward simulator (4 actions: standard, rated, decline, refer)
- Static XGBoost baseline for benchmarking
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

# Resolve paths relative to this file (inside app/rl/)
_DATA_PATH = Path(__file__).parent / "data" / "cambodia_dataset.csv"
_MODELS_DIR = Path(__file__).parent / "models"

# ── Actions ────────────────────────────────────────────────────────────────
ACTION_STANDARD = 0
ACTION_RATED = 1
ACTION_DECLINE = 2
ACTION_REFER = 3
ACTION_NAMES = ["STANDARD", "RATED", "DECLINE", "REFER"]

# ── Data preprocessor ──────────────────────────────────────────────────────


def preprocess_cambodia_data() -> tuple[np.ndarray, pd.DataFrame, list[str]]:
    """Load Cambodia dataset and return feature matrix X, raw DataFrame, feature names."""
    df = pd.read_csv(_DATA_PATH)

    conditions = ["Hypertension", "Diabetes", "Heart Disease", "COPD/Asthma", "Arthritis", "TB", "Hepatitis B"]
    for cond in conditions:
        col = f"has_{cond.lower().replace('/', '_').replace(' ', '_')}"
        df[col] = df["pre_existing_conditions"].fillna("").str.contains(cond, regex=False).astype(int)

    df["condition_count"] = df[[f"has_{c.lower().replace('/', '_').replace(' ', '_')}" for c in conditions]].sum(axis=1)

    # One-hot encode region and occupation (critical for linear models)
    region_dummies = pd.get_dummies(df["region"], prefix="region")
    occ_dummies = pd.get_dummies(df["occupation"], prefix="occ")
    df = pd.concat([df, region_dummies, occ_dummies], axis=1)

    features = (
        ["age", "bmi", "is_smoking", "is_exercise", "has_family_history",
         "monthly_income_usd", "condition_count"]
        + [f"has_{c.lower().replace('/', '_').replace(' ', '_')}" for c in conditions]
        + list(region_dummies.columns)
        + list(occ_dummies.columns)
    )

    # Normalize all features to mean 0, std 1 for linear bandits
    X = df[features].copy().astype(float)
    for col in features:
        mean, std = X[col].mean(), X[col].std()
        X[col] = (X[col] - mean) / (std if std > 0 else 1)

    return X.values, df, features


# ── Reward simulator ───────────────────────────────────────────────────────


def make_reward_simulator(rng: np.random.Generator) -> Callable:
    """Return a function reward(action, row) that computes stochastic reward."""

    def reward(action: int, row: pd.Series) -> float:
        mort = row["mortality_multiplier"]
        income = row["monthly_income_usd"]

        # Annual premium and expected claims (USD)
        base_premium = 200 * mort
        expected_claims = 150 * mort

        # Adverse selection: high-risk applicants underpriced at standard terms
        adverse_factor = 1.0 if mort <= 2.0 else 1.35

        # Customer acceptance probability (premium-to-income ratio)
        def p_accept(premium: float) -> float:
            ratio = (premium / 12) / income  # monthly premium / monthly income
            return max(0.05, 0.95 - 3.5 * ratio)

        p_std = p_accept(base_premium)
        p_rtd = p_accept(base_premium * 1.25)

        if action == ACTION_STANDARD:
            claims = expected_claims * adverse_factor * rng.uniform(0.92, 1.08)
            if rng.random() < p_std:
                return base_premium - claims
            return -20.0  # processing cost if customer walks

        if action == ACTION_RATED:
            claims = expected_claims * rng.uniform(0.92, 1.08)
            if rng.random() < p_rtd:
                return base_premium * 1.25 - claims
            return -20.0

        if action == ACTION_DECLINE:
            return -10.0  # small opportunity cost

        if action == ACTION_REFER:
            # Manual underwriter captures 70% of optimal value minus $35 admin
            r_std = p_std * (base_premium - expected_claims * adverse_factor) + (1 - p_std) * (-25)
            r_rtd = p_rtd * (base_premium * 1.25 - expected_claims) + (1 - p_rtd) * (-25)
            r_dcl = -10.0
            optimal = max(r_std, r_rtd, r_dcl)
            return 0.70 * optimal - 35.0

        raise ValueError(f"Unknown action: {action}")

    return reward


def expected_rewards(row: pd.Series) -> np.ndarray:
    """Compute expected rewards for all 4 actions (deterministic, for oracle/baseline)."""
    mort = row["mortality_multiplier"]
    income = row["monthly_income_usd"]

    base_premium = 200 * mort
    expected_claims = 150 * mort
    adverse_factor = 1.0 if mort <= 2.0 else 1.35

    def p_accept(premium: float) -> float:
        ratio = (premium / 12) / income
        return max(0.05, 0.95 - 3.5 * ratio)

    p_std = p_accept(base_premium)
    p_rtd = p_accept(base_premium * 1.25)

    r_std = p_std * (base_premium - expected_claims * adverse_factor) + (1 - p_std) * (-25)
    r_rtd = p_rtd * (base_premium * 1.25 - expected_claims) + (1 - p_rtd) * (-25)
    r_dcl = -10.0
    optimal = max(r_std, r_rtd, r_dcl)
    r_ref = 0.70 * optimal - 35.0

    return np.array([r_std, r_rtd, r_dcl, r_ref])


# ── Bandit algorithms ──────────────────────────────────────────────────────

class LinUCB:
    """Linear Upper Confidence Bound for contextual bandits."""

    def __init__(self, n_actions: int, n_features: int, alpha: float = 1.0):
        self.n_actions = n_actions
        self.n_features = n_features
        self.alpha = alpha
        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.theta = [np.zeros(n_features) for _ in range(n_actions)]

    def select_action(self, context: np.ndarray) -> int:
        p = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            self.theta[a] = A_inv @ self.b[a]
            p[a] = self.theta[a] @ context + self.alpha * np.sqrt(context @ A_inv @ context)
        return int(np.argmax(p))

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        self.A[action] += np.outer(context, context)
        self.b[action] += reward * context


class LinTS:
    """Linear Thompson Sampling with Gaussian priors."""

    def __init__(self, n_actions: int, n_features: int, v2: float = 1.0, seed: int = 42):
        self.n_actions = n_actions
        self.n_features = n_features
        self.v2 = v2
        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.rng = np.random.default_rng(seed=seed)

    def select_action(self, context: np.ndarray) -> int:
        p = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            mu_hat = A_inv @ self.b[a]
            cov = self.v2 * A_inv
            mu_tilde = self.rng.multivariate_normal(mu_hat, cov)
            p[a] = mu_tilde @ context
        return int(np.argmax(p))

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        self.A[action] += np.outer(context, context)
        self.b[action] += reward * context


class EpsilonGreedy:
    """Epsilon-greedy with linear regression per action."""

    def __init__(self, n_actions: int, n_features: int, epsilon: float = 0.1, seed: int = 42):
        self.n_actions = n_actions
        self.n_features = n_features
        self.epsilon = epsilon
        self.A = [np.eye(n_features) for _ in range(n_actions)]
        self.b = [np.zeros(n_features) for _ in range(n_actions)]
        self.theta = [np.zeros(n_features) for _ in range(n_actions)]
        self.rng = np.random.default_rng(seed=seed)

    def select_action(self, context: np.ndarray) -> int:
        if self.rng.random() < self.epsilon:
            return self.rng.integers(self.n_actions)
        p = np.zeros(self.n_actions)
        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            self.theta[a] = A_inv @ self.b[a]
            p[a] = self.theta[a] @ context
        return int(np.argmax(p))

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        self.A[action] += np.outer(context, context)
        self.b[action] += reward * context


# ── Static baseline ────────────────────────────────────────────────────────

class StaticXGBBaseline:
    """Pre-trained XGBoost model + deterministic rule baseline."""

    def __init__(self):
        # Delay heavy xgboost import until actually needed
        try:
            import xgboost as _  # noqa: F401
        except ImportError:
            pass
        with open(_MODELS_DIR / "cambodia_life_xgb.pkl", "rb") as f:
            self.model = pickle.load(f)
        df = pd.read_csv(_DATA_PATH)
        self.region_map = {r: i for i, r in enumerate(sorted(df["region"].unique()))}
        self.occ_map = {o: i for i, o in enumerate(sorted(df["occupation"].unique()))}

    def _preprocess_row(self, row: pd.Series) -> np.ndarray:
        """Create the original 16 features the XGB model was trained on."""
        conds = str(row.get("pre_existing_conditions", ""))
        cond_count = sum(1 for c in ["Hypertension", "Diabetes", "Heart Disease", "COPD/Asthma", "Arthritis", "TB", "Hepatitis B"] if c in conds)
        x = np.array([
            row["age"], row["bmi"], row["is_smoking"], row["is_exercise"],
            row["has_family_history"], row["monthly_income_usd"], cond_count,
            int("Hypertension" in conds),
            int("Diabetes" in conds),
            int("Heart Disease" in conds),
            int("COPD/Asthma" in conds),
            int("Arthritis" in conds),
            int("TB" in conds),
            int("Hepatitis B" in conds),
            self.region_map.get(row["region"], 0),
            self.occ_map.get(row["occupation"], 0),
        ], dtype=float)
        return x.reshape(1, -1)

    def select_action(self, context: np.ndarray, row: pd.Series | None = None) -> int:
        if row is not None:
            mort_pred = self.model.predict(self._preprocess_row(row))[0]
        else:
            mort_pred = self.model.predict(context.reshape(1, -1))[0]
        if mort_pred <= 1.5:
            return ACTION_STANDARD
        if mort_pred <= 2.2:
            return ACTION_RATED
        if mort_pred <= 2.6:
            return ACTION_REFER
        return ACTION_DECLINE

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        pass  # Static baseline does not learn


# ── Runner ─────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    algorithm: str
    actions: np.ndarray
    rewards: np.ndarray
    regrets: np.ndarray
    cumulative_rewards: np.ndarray
    cumulative_regrets: np.ndarray


def run_bandit(
    algorithm_name: str,
    bandit,
    contexts: np.ndarray,
    df_raw: pd.DataFrame,
    n_rounds: int,
    seed: int = 42,
) -> RunResult:
    """Run a bandit algorithm for n_rounds and return metrics."""
    rng = np.random.default_rng(seed)
    reward_fn = make_reward_simulator(rng)

    actions = np.zeros(n_rounds, dtype=int)
    rewards = np.zeros(n_rounds)
    regrets = np.zeros(n_rounds)

    n_samples = len(contexts)
    indices = np.arange(n_samples)
    for t in range(n_rounds):
        idx = indices[t % n_samples]
        if t > 0 and t % n_samples == 0:
            rng.shuffle(indices)

        context = contexts[idx]
        row = df_raw.iloc[idx]
        if hasattr(bandit, '_preprocess_row'):
            action = bandit.select_action(context, row)
        else:
            action = bandit.select_action(context)
        reward = reward_fn(action, row)

        expected = expected_rewards(df_raw.iloc[idx])
        optimal_reward = expected.max()

        actions[t] = action
        rewards[t] = reward
        regrets[t] = optimal_reward - reward

        bandit.update(action, context, reward)

    return RunResult(
        algorithm=algorithm_name,
        actions=actions,
        rewards=rewards,
        regrets=regrets,
        cumulative_rewards=np.cumsum(rewards),
        cumulative_regrets=np.cumsum(regrets),
    )
