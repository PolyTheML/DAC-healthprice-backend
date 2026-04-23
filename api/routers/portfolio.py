"""API routes for /portfolio endpoints (claims analysis and pricing calibration)."""

from pathlib import Path
from fastapi import APIRouter, HTTPException

from portfolio.generator import load_portfolio, generate_portfolio, save_portfolio
from portfolio.analysis import ClaimsAnalyzer
from portfolio.calibration import calibrate_assumptions

router = APIRouter()

_PORTFOLIO_PATH = str(Path(__file__).parent.parent.parent / "data" / "synthetic_portfolio.parquet")


def _get_analyzer() -> ClaimsAnalyzer:
    """Load portfolio from parquet and return a ClaimsAnalyzer."""
    if not Path(_PORTFOLIO_PATH).exists():
        # Auto-generate on first call if not present
        df = generate_portfolio()
        save_portfolio(df, _PORTFOLIO_PATH)
    df = load_portfolio(_PORTFOLIO_PATH)
    return ClaimsAnalyzer(df)


@router.get("/summary")
async def portfolio_summary():
    """
    High-level KPIs for the claims portfolio.

    Returns: total policies, exposure, claim rate, loss ratio, risk tier distribution.
    """
    try:
        analyzer = _get_analyzer()
        return analyzer.portfolio_summary().to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis")
async def portfolio_analysis():
    """
    Full claims experience analysis.

    Returns:
    - portfolio_summary: KPI metrics
    - cohort_mortality: Observed vs. assumed q(x) by age band / gender
    - risk_factor_lifts: Observed vs. assumed mortality multiplier per flag
    - ae_table: Actual/Expected ratios by (age_band, gender, risk_tier)
    - overall_ae_ratio: Aggregate A/E (expected ~0.85 for Cambodia hypothesis)
    """
    try:
        analyzer = _get_analyzer()
        return {
            "portfolio_summary": analyzer.portfolio_summary().to_dict(),
            "cohort_mortality": analyzer.cohort_mortality_rates().to_dict(orient="records"),
            "risk_factor_lifts": analyzer.risk_factor_lift().to_dict(orient="records"),
            "ae_table": analyzer.experience_vs_expected().to_dict(orient="records"),
            "overall_ae_ratio": analyzer.overall_ae_ratio(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration")
async def portfolio_calibration():
    """
    Pricing calibration proposal.

    Compares observed claims experience against assumed risk factor multipliers
    and proposes updated values with 95% Poisson confidence intervals.

    Returns:
    - overall_ae_ratio: Aggregate actual/expected mortality ratio
    - factor_calibrations: Per-factor current vs. proposed multipliers
    - recommendation_summary: Plain-language recommendation
    """
    try:
        analyzer = _get_analyzer()
        ae_df = analyzer.experience_vs_expected()
        lift_df = analyzer.risk_factor_lift()
        overall_ae = analyzer.overall_ae_ratio()
        report = calibrate_assumptions(ae_df, lift_df, overall_ae)
        return report.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate")
async def regenerate_portfolio(n_policies: int = 2000, seed: int = 42):
    """
    Regenerate the synthetic portfolio with new parameters.

    Useful for sensitivity testing or demo customization.
    """
    try:
        df = generate_portfolio(n=n_policies, seed=seed)
        save_portfolio(df, _PORTFOLIO_PATH)
        analyzer = ClaimsAnalyzer(df)
        summary = analyzer.portfolio_summary()
        return {
            "message": f"Portfolio regenerated: {len(df):,} policies",
            "loss_ratio": summary.loss_ratio,
            "claim_rate": summary.total_claims / summary.total_policies,
            "overall_ae_ratio": analyzer.overall_ae_ratio(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
