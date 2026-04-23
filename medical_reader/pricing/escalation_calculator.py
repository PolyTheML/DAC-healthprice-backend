"""
Escalation Calculator Module

Computes the actuarial cost factor and year-by-year schedule for automatic
coverage escalation products (e.g., 5% annual increase with no health re-check).

Product design (FWD Vietnam model, adapted for Cambodia):
- Customer pays the same level premium every year
- Insurer provides increasing coverage: Year k = base × (1 + r)^(k-1), capped at terminal_cap
- Insurer loads a cost factor into Year 1 premium to fund the escalating obligation

Actuarial formula:
    Cost Factor = (PV(escalating benefits) / PV(level benefits) - 1) × cap_utilization

Where:
    PV(escalating) = Σ min((1+r)^(k-1), terminal_cap) / (1+d)^k  for k=1..n
    PV(level)      = Σ 1 / (1+d)^k                                 for k=1..n
    cap_utilization = fraction of policies that actually reach the annual benefit cap
                      (~20% for health insurance — most customers don't hit limits)

This gives ≈8–12% markup for standard parameters (r=5%, d=6%, n=20, cap=2.5×, util=0.20),
which is actuarially defensible and IRC-disclosable.

IRC compliance: All parameters stored in EscalationParameters; every calculation
returns EscalationSchedule with full year-by-year audit trail.
"""

from dataclasses import dataclass, field
from typing import List


# ============= PARAMETERS =============

@dataclass(frozen=True)
class EscalationParameters:
    """
    Configurable parameters for the escalation product.

    All parameters must be disclosed to IRC per Prakas 093 transparency requirements.
    To change product design, modify these values and increment ESCALATION_VERSION.
    """

    escalation_rate: float = 0.05
    """Annual coverage escalation rate (5% = FWD Vietnam benchmark)."""

    discount_rate: float = 0.06
    """Actuarial discount rate (6% = conservative Cambodia investment return assumption)."""

    duration_years: int = 20
    """Maximum policy duration over which escalation applies."""

    terminal_cap: float = 2.50
    """Maximum coverage multiple vs. base amount (250% = conservative vs. FWD's 400%)."""

    cap_utilization: float = 0.20
    """
    Fraction of policies where customer ever reaches the annual benefit cap.
    ~20% for health insurance (most customers don't exhaust annual limits).
    Adjusts raw actuarial cost factor to health insurance context.
    """

    bonus_year_10_pct: float = 0.25
    """
    Loyalty bonus at Year 10: 25% of annual premium as health credit.
    Simplified vs. FWD's 50% (lower Cambodia premium base).
    """

    bonus_year_20_pct: float = 0.50
    """Loyalty bonus at Year 20: 50% of annual premium as renewal incentive."""


ESCALATION_PARAMS = EscalationParameters()
"""Default escalation parameters. Override for what-if scenarios."""

ESCALATION_VERSION = "v1.0-2026-04-12"


# ============= OUTPUT MODELS =============

@dataclass
class YearProjection:
    """Single year in the escalation schedule."""

    year: int
    coverage_multiple: float     # Coverage as multiple of base (e.g. 1.05 = 5% above base)
    coverage_amount: float       # Absolute coverage amount (USD)
    annual_premium: float        # Level premium (same every year)
    monthly_premium: float
    cumulative_escalation_pct: float   # Total % increase from Year 1 (e.g. 21.6% by Year 5)
    loyalty_bonus: float         # Cash bonus paid to customer this year (0 most years)


@dataclass
class EscalationSchedule:
    """
    Complete escalation schedule for a policy.

    Returned by calculate_escalation_schedule().
    Suitable for API responses, frontend projection charts, and IRC audit trail.
    """

    # Core product parameters
    base_annual_premium: float       # Year 1 premium without escalation loading
    escalated_annual_premium: float  # Year 1 premium with escalation loading applied
    escalated_monthly_premium: float
    cost_factor: float               # Escalation markup (e.g. 0.103 = 10.3%)
    cost_factor_pct: str             # Human-readable (e.g. "10.3%")

    # Coverage details
    base_coverage: float             # Face amount / annual benefit limit (USD)
    terminal_coverage: float         # Maximum coverage (base × terminal_cap)
    cap_year: int                    # Year terminal cap is first reached

    # Year-by-year schedule
    projections: List[YearProjection] = field(default_factory=list)

    # Metadata
    parameters: EscalationParameters = field(default_factory=EscalationParameters)
    version: str = ESCALATION_VERSION


# ============= CORE FUNCTIONS =============

def compute_cost_factor(params: EscalationParameters = ESCALATION_PARAMS) -> float:
    """
    Compute the actuarial escalation cost factor.

    Formula:
        raw_factor = (PV_escalating / PV_flat) - 1.0
        cost_factor = raw_factor × cap_utilization

    Args:
        params: EscalationParameters (rate, discount rate, duration, cap, utilization)

    Returns:
        cost_factor: Decimal markup to apply to base premium (e.g. 0.103 = 10.3%)

    Example:
        >>> compute_cost_factor()  # default params
        0.103   # ≈10.3% markup
    """
    r = params.escalation_rate
    d = params.discount_rate
    n = params.duration_years
    cap = params.terminal_cap

    pv_flat = sum(1.0 / (1.0 + d) ** k for k in range(1, n + 1))

    pv_escalating = sum(
        min((1.0 + r) ** (k - 1), cap) / (1.0 + d) ** k
        for k in range(1, n + 1)
    )

    raw_factor = (pv_escalating / pv_flat) - 1.0
    return round(raw_factor * params.cap_utilization, 6)


def calculate_escalation_schedule(
    base_annual_premium: float,
    base_coverage: float,
    params: EscalationParameters = ESCALATION_PARAMS,
) -> EscalationSchedule:
    """
    Calculate the complete escalation schedule for a policy.

    Args:
        base_annual_premium: The standard (non-escalated) annual premium in USD
        base_coverage:       The Year 1 coverage amount in USD
        params:              EscalationParameters (defaults to ESCALATION_PARAMS)

    Returns:
        EscalationSchedule with cost factor, escalated premiums, and year-by-year projections

    Example:
        schedule = calculate_escalation_schedule(
            base_annual_premium=500.00,
            base_coverage=50_000.00,
        )
        # schedule.cost_factor ≈ 0.103
        # schedule.escalated_annual_premium ≈ 551.50
        # schedule.projections[4].coverage_amount ≈ 60,776 (Year 5)
    """
    cost_factor = compute_cost_factor(params)

    escalated_annual_premium = round(base_annual_premium * (1.0 + cost_factor), 2)
    escalated_monthly_premium = round(escalated_annual_premium / 12.0, 2)

    terminal_coverage = base_coverage * params.terminal_cap

    # Find the year the terminal cap is first reached
    cap_year = params.duration_years
    for k in range(1, params.duration_years + 1):
        if (1.0 + params.escalation_rate) ** (k - 1) >= params.terminal_cap:
            cap_year = k
            break

    # Build year-by-year projections
    projections: List[YearProjection] = []
    for k in range(1, params.duration_years + 1):
        raw_multiple = (1.0 + params.escalation_rate) ** (k - 1)
        coverage_multiple = round(min(raw_multiple, params.terminal_cap), 6)
        coverage_amount = round(base_coverage * coverage_multiple, 2)
        cumulative_pct = round((coverage_multiple - 1.0) * 100, 2)

        # Loyalty bonuses (paid in cash to customer)
        loyalty_bonus = 0.0
        if k == 10:
            loyalty_bonus = round(escalated_annual_premium * params.bonus_year_10_pct, 2)
        elif k == 20:
            loyalty_bonus = round(escalated_annual_premium * params.bonus_year_20_pct, 2)

        projections.append(YearProjection(
            year=k,
            coverage_multiple=coverage_multiple,
            coverage_amount=coverage_amount,
            annual_premium=escalated_annual_premium,
            monthly_premium=escalated_monthly_premium,
            cumulative_escalation_pct=cumulative_pct,
            loyalty_bonus=loyalty_bonus,
        ))

    return EscalationSchedule(
        base_annual_premium=round(base_annual_premium, 2),
        escalated_annual_premium=escalated_annual_premium,
        escalated_monthly_premium=escalated_monthly_premium,
        cost_factor=cost_factor,
        cost_factor_pct=f"{cost_factor * 100:.1f}%",
        base_coverage=round(base_coverage, 2),
        terminal_coverage=round(terminal_coverage, 2),
        cap_year=cap_year,
        projections=projections,
        parameters=params,
        version=ESCALATION_VERSION,
    )
