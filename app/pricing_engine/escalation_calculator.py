"""
Escalation Calculator — DAC HealthPrice Platform

Computes the actuarial cost factor and year-by-year schedule for automatic
coverage escalation products (5% annual increase, same premium, no re-check).

Product design (FWD Vietnam model, adapted for Cambodia):
- Customer pays the same level premium every year
- Insurer provides increasing coverage: Year k = base × (1+r)^(k-1), capped at terminal_cap
- Insurer loads a cost factor into Year 1 premium to fund the escalating obligation

Actuarial formula:
    Cost Factor = (PV(escalating benefits) / PV(level benefits) − 1) × cap_utilization

    PV(escalating) = Σ min((1+r)^(k-1), cap) / (1+d)^k  for k=1..n
    PV(level)      = Σ 1 / (1+d)^k                        for k=1..n
    cap_utilization ≈ 0.20 (20% of health policies reach the annual benefit cap)

Default params (r=5%, d=6%, n=20, cap=2.5×, util=0.20) → ~10.1% markup.
IRC-compliant: all parameters disclosed; every output includes full audit trail.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

# ── Parameters ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EscalationParameters:
    escalation_rate: float = 0.05    # 5% annual coverage growth
    discount_rate: float   = 0.06    # 6% actuarial discount (Cambodia conservative)
    duration_years: int    = 20      # Policy duration
    terminal_cap: float    = 2.50    # Max coverage multiple (250% of base)
    cap_utilization: float = 0.20    # Fraction of policies that hit annual limit
    bonus_year_10_pct: float = 0.25  # Loyalty bonus at Year 10 (25% of annual premium)
    bonus_year_20_pct: float = 0.50  # Loyalty bonus at Year 20 (50% of annual premium)

ESCALATION_PARAMS = EscalationParameters()
ESCALATION_VERSION = "v1.0-2026-04-12"

# ── Output models ─────────────────────────────────────────────────────────────

@dataclass
class YearProjection:
    year: int
    coverage_multiple: float
    coverage_amount: float
    annual_premium: float
    monthly_premium: float
    cumulative_escalation_pct: float
    loyalty_bonus: float

@dataclass
class EscalationSchedule:
    base_annual_premium: float
    escalated_annual_premium: float
    escalated_monthly_premium: float
    cost_factor: float
    cost_factor_pct: str
    base_coverage: float
    terminal_coverage: float
    cap_year: int
    projections: List[YearProjection] = field(default_factory=list)
    parameters: EscalationParameters = field(default_factory=EscalationParameters)
    version: str = ESCALATION_VERSION

# ── Core functions ────────────────────────────────────────────────────────────

def compute_cost_factor(params: EscalationParameters = ESCALATION_PARAMS) -> float:
    """
    Return the decimal escalation markup (e.g. 0.101 = 10.1%).

    Formula: (PV_escalating / PV_flat − 1) × cap_utilization
    """
    r, d, n, cap = params.escalation_rate, params.discount_rate, params.duration_years, params.terminal_cap
    pv_flat = sum(1.0 / (1.0 + d) ** k for k in range(1, n + 1))
    pv_esc  = sum(min((1.0 + r) ** (k - 1), cap) / (1.0 + d) ** k for k in range(1, n + 1))
    return round((pv_esc / pv_flat - 1.0) * params.cap_utilization, 6)


def calculate_escalation_schedule(
    base_annual_premium: float,
    base_coverage: float,
    params: EscalationParameters = ESCALATION_PARAMS,
) -> EscalationSchedule:
    """
    Full year-by-year escalation schedule for a policy.

    Args:
        base_annual_premium: Standard (non-escalated) annual premium in USD
        base_coverage:       Year 1 coverage / annual benefit limit in USD
        params:              EscalationParameters (defaults to product defaults)

    Returns:
        EscalationSchedule with escalated premiums, coverage table, and loyalty bonuses
    """
    cf = compute_cost_factor(params)
    escalated_annual  = round(base_annual_premium * (1.0 + cf), 2)
    escalated_monthly = round(escalated_annual / 12.0, 2)

    # Year the terminal cap is first reached
    cap_year = params.duration_years
    for k in range(1, params.duration_years + 1):
        if (1.0 + params.escalation_rate) ** (k - 1) >= params.terminal_cap:
            cap_year = k
            break

    projections: List[YearProjection] = []
    for k in range(1, params.duration_years + 1):
        multiple = round(min((1.0 + params.escalation_rate) ** (k - 1), params.terminal_cap), 6)
        bonus = 0.0
        if k == 10:
            bonus = round(escalated_annual * params.bonus_year_10_pct, 2)
        elif k == 20:
            bonus = round(escalated_annual * params.bonus_year_20_pct, 2)
        projections.append(YearProjection(
            year=k,
            coverage_multiple=multiple,
            coverage_amount=round(base_coverage * multiple, 2),
            annual_premium=escalated_annual,
            monthly_premium=escalated_monthly,
            cumulative_escalation_pct=round((multiple - 1.0) * 100, 2),
            loyalty_bonus=bonus,
        ))

    return EscalationSchedule(
        base_annual_premium=round(base_annual_premium, 2),
        escalated_annual_premium=escalated_annual,
        escalated_monthly_premium=escalated_monthly,
        cost_factor=cf,
        cost_factor_pct=f"{cf * 100:.1f}%",
        base_coverage=round(base_coverage, 2),
        terminal_coverage=round(base_coverage * params.terminal_cap, 2),
        cap_year=cap_year,
        projections=projections,
        parameters=params,
        version=ESCALATION_VERSION,
    )
