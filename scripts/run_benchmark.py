"""
DAC HealthPrice — Competitor Pricing Benchmark
===============================================
Runs all benchmark personas through the DAC API, then compares results
against manually collected competitor quotes in competitor_quotes.csv.

Benchmark scope (5 core personas × 3 competitors):
  Personas : P01 (25F), P04 (35M), P06 (40F), P08 (45M), P12 (55M)
  Competitors: Pacific Cross, Cigna Global, Manulife Cambodia

NOTE on pre-existing conditions:
  Competitors only price conditions at underwriting, not at quote stage.
  All competitor quotes should be collected as base rates (age + gender +
  smoker only). DAC quotes for the same personas will include condition
  loading — so variance reflects DAC's more granular risk segmentation,
  not a pricing error.

Usage:
    python scripts/run_benchmark.py                        # API + comparison (if CSV has data)
    python scripts/run_benchmark.py --api-only             # Skip competitor comparison
    python scripts/run_benchmark.py --report-only          # Only re-run comparison (no API calls)
    python scripts/run_benchmark.py --base-url http://...  # Override API base URL

Output files (written to scripts/benchmark_output/):
    dac_quotes.json       — Raw API responses for all personas
    dac_quotes.csv        — Flat summary of DAC results
    comparison.csv        — DAC vs competitor side-by-side with variance %
    report.txt            — Human-readable summary report

Auth:
    Set PARTNER_API_KEY env var to use partner auth (recommended).
    Otherwise a session token is requested automatically using BENCHMARK_EMAIL
    (default: benchmark@dac-health.com). Sessions allow 10 quotes each;
    multiple sessions are created automatically for larger persona sets.
"""

import os, sys, json, csv, time, argparse
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests not installed — run: pip install requests")

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
OUTPUT_DIR   = SCRIPT_DIR / "benchmark_output"
PERSONAS_FILE = SCRIPT_DIR / "benchmark_personas.json"
COMPETITOR_FILE = SCRIPT_DIR / "competitor_quotes.csv"

DEFAULT_BASE_URL  = "https://dac-healthprice-api.onrender.com"
BENCHMARK_EMAIL   = os.getenv("BENCHMARK_EMAIL", "benchmark@dac-health.com")
PARTNER_API_KEY   = os.getenv("PARTNER_API_KEY", "")
SESSION_QUOTA     = 10   # quotes per session (must match backend SESSION_QUOTE_LIMIT)
REQUEST_TIMEOUT   = 50   # seconds


def get_session_token(base_url: str) -> str:
    resp = requests.post(
        f"{base_url}/api/v2/session",
        json={"email": BENCHMARK_EMAIL},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    token = resp.json()["token"]
    print(f"  Session token obtained ({SESSION_QUOTA} quotes available)")
    return token


def price_persona(base_url: str, persona: dict, token: str | None, partner_key: str | None) -> dict:
    headers = {"Content-Type": "application/json"}
    if partner_key:
        headers["X-Partner-Key"] = partner_key
    elif token:
        headers["X-Session-Token"] = token

    payload = {k: v for k, v in persona.items() if k not in ("id", "label")}

    resp = requests.post(
        f"{base_url}/api/v2/price",
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 422:
        return {"error": "validation", "detail": resp.json()}
    if resp.status_code == 200:
        return resp.json()
    return {"error": resp.status_code, "detail": resp.text[:300]}


def run_api_benchmark(base_url: str, personas: list) -> list:
    print(f"\n── Running {len(personas)} personas against DAC API ──")
    print(f"   Base URL: {base_url}")

    results = []
    token = None
    token_uses = 0

    for i, persona in enumerate(personas):
        # Refresh session token when quota exhausted or not yet created
        if not PARTNER_API_KEY and (token is None or token_uses >= SESSION_QUOTA):
            print(f"\n  Requesting new session (quota consumed after {token_uses} quotes)...")
            token = get_session_token(base_url)
            token_uses = 0

        print(f"  [{i+1:02d}/{len(personas)}] {persona['id']} — {persona['label']}", end=" ", flush=True)
        t0 = time.monotonic()
        res = price_persona(base_url, persona, token, PARTNER_API_KEY or None)
        elapsed = round((time.monotonic() - t0) * 1000)

        if not PARTNER_API_KEY:
            token_uses += 1

        entry = {
            "persona_id": persona["id"],
            "label": persona["label"],
            "tier": persona["ipd_tier"],
            "response_ms": elapsed,
            "result": res,
        }
        results.append(entry)

        if "error" in res:
            print(f"  ERROR: {res.get('detail', res['error'])}")
        elif res.get("underwriting", {}).get("status") == "decline":
            print(f"  DECLINED (underwriting) — {elapsed}ms")
        else:
            total = res.get("total_annual_premium")
            model = res.get("model_source", "?")
            print(f"  ${total:,.0f}/yr  [{model}]  {elapsed}ms")

        time.sleep(0.3)   # be polite to the API

    return results


def save_dac_quotes(results: list):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Raw JSON
    with open(OUTPUT_DIR / "dac_quotes.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Flat CSV summary
    rows = []
    for entry in results:
        res = entry["result"]
        if "error" in res:
            rows.append({
                "persona_id": entry["persona_id"],
                "label": entry["label"],
                "tier": entry["tier"],
                "dac_annual_premium": None,
                "dac_monthly_premium": None,
                "model_source": None,
                "model_accuracy_pct": None,
                "model_version": None,
                "underwriting_status": "error",
                "response_ms": entry["response_ms"],
            })
        else:
            rows.append({
                "persona_id": entry["persona_id"],
                "label": entry["label"],
                "tier": entry["tier"],
                "dac_annual_premium": res.get("total_annual_premium"),
                "dac_monthly_premium": res.get("total_monthly_premium"),
                "model_source": res.get("model_source"),
                "model_accuracy_pct": res.get("model_accuracy_pct"),
                "model_version": res.get("model_version"),
                "underwriting_status": res.get("underwriting", {}).get("status"),
                "response_ms": entry["response_ms"],
            })

    if rows:
        with open(OUTPUT_DIR / "dac_quotes.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    print(f"\n  Saved: {OUTPUT_DIR / 'dac_quotes.json'}")
    print(f"  Saved: {OUTPUT_DIR / 'dac_quotes.csv'}")
    return rows


def load_dac_quotes_from_csv() -> list:
    path = OUTPUT_DIR / "dac_quotes.csv"
    if not path.exists():
        sys.exit(f"No saved DAC quotes found at {path}. Run without --report-only first.")
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def load_competitor_quotes() -> dict:
    """Returns {persona_id: [{competitor, tier, annual_premium_usd, ...}]}"""
    if not COMPETITOR_FILE.exists():
        print("  competitor_quotes.csv not found — skipping comparison.")
        return {}

    data = {}
    with open(COMPETITOR_FILE, newline="") as f:
        for row in csv.DictReader(f):
            pid = row["persona_id"].strip()
            annual = row.get("annual_premium_usd", "").strip()
            if not annual:
                continue    # skip empty rows (not yet filled in)
            try:
                row["annual_premium_usd"] = float(annual)
            except ValueError:
                continue
            data.setdefault(pid, []).append(row)

    filled = sum(len(v) for v in data.values())
    print(f"  Loaded {filled} competitor quotes for {len(data)} personas")
    return data


def run_comparison(dac_rows: list, competitor_data: dict):
    if not competitor_data:
        print("\n── No competitor data available — fill in competitor_quotes.csv and re-run ──")
        return [], {}

    print("\n── Building comparison ──")

    # Index DAC results by persona_id
    dac_index = {r["persona_id"]: r for r in dac_rows}

    comparison_rows = []
    variances_by_competitor = {}

    for pid, comp_quotes in competitor_data.items():
        dac = dac_index.get(pid)
        if not dac or not dac.get("dac_annual_premium"):
            continue
        dac_premium = float(dac["dac_annual_premium"])

        for cq in comp_quotes:
            comp_name = cq["competitor"].strip()
            comp_premium = float(cq["annual_premium_usd"])
            variance_pct = round((dac_premium - comp_premium) / comp_premium * 100, 2)

            comparison_rows.append({
                "persona_id": pid,
                "label": dac["label"],
                "tier": dac["tier"],
                "competitor": comp_name,
                "dac_annual": dac_premium,
                "competitor_annual": comp_premium,
                "variance_pct": variance_pct,
                "abs_variance_pct": abs(variance_pct),
                "model_source": dac.get("model_source"),
            })

            variances_by_competitor.setdefault(comp_name, []).append(variance_pct)

    if comparison_rows:
        with open(OUTPUT_DIR / "comparison.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=comparison_rows[0].keys())
            writer.writeheader()
            writer.writerows(comparison_rows)
        print(f"  Saved: {OUTPUT_DIR / 'comparison.csv'}")

    return comparison_rows, variances_by_competitor


def build_report(dac_rows: list, comparison_rows: list, variances_by_competitor: dict):
    lines = []
    lines.append("=" * 60)
    lines.append("  DAC HEALTHPRICE — COMPETITOR BENCHMARK REPORT")
    lines.append(f"  Generated: {date.today().isoformat()}")
    lines.append("=" * 60)

    # ── DAC API performance
    valid_rows = [r for r in dac_rows if r.get("dac_annual_premium")]
    declined = [r for r in dac_rows if r.get("underwriting_status") == "decline"]
    errors   = [r for r in dac_rows if r.get("underwriting_status") == "error"]
    response_times = [int(r["response_ms"]) for r in dac_rows if r.get("response_ms")]

    lines.append("\n── DAC API PERFORMANCE ──")
    lines.append(f"  Personas tested  : {len(dac_rows)}")
    lines.append(f"  Successful quotes: {len(valid_rows)}")
    lines.append(f"  Declined (UW)    : {len(declined)}")
    lines.append(f"  Errors           : {len(errors)}")
    if response_times:
        lines.append(f"  Latency p50      : {sorted(response_times)[len(response_times)//2]}ms")
        lines.append(f"  Latency p95      : {sorted(response_times)[int(len(response_times)*0.95)]}ms")
        lines.append(f"  Latency max      : {max(response_times)}ms")

    ml_count = sum(1 for r in dac_rows if r.get("model_source") == "ml")
    lines.append(f"  ML-sourced quotes: {ml_count}/{len(dac_rows)}")

    # ── Premium range by tier
    lines.append("\n── DAC PREMIUMS BY TIER ──")
    by_tier = {}
    for r in valid_rows:
        t = r["tier"]
        by_tier.setdefault(t, []).append(float(r["dac_annual_premium"]))
    for tier in ["Bronze", "Silver", "Gold", "Platinum"]:
        if tier in by_tier:
            premiums = by_tier[tier]
            lines.append(f"  {tier:<10}  ${min(premiums):>7,.0f} – ${max(premiums):>7,.0f}/yr  (n={len(premiums)})")

    # ── Competitor comparison
    if comparison_rows:
        lines.append("\n── VARIANCE VS COMPETITORS ──")
        lines.append(f"  {'Competitor':<12}  {'n':>4}  {'Mean var%':>10}  {'Abs mean%':>10}  {'Within ±10%':>12}")
        lines.append("  " + "-" * 56)
        all_variances = []
        for comp, variances in sorted(variances_by_competitor.items()):
            mean_var = round(sum(variances) / len(variances), 1)
            abs_mean = round(sum(abs(v) for v in variances) / len(variances), 1)
            within_10 = sum(1 for v in variances if abs(v) <= 10)
            lines.append(f"  {comp:<12}  {len(variances):>4}  {mean_var:>+10.1f}%  {abs_mean:>9.1f}%  {within_10}/{len(variances):>10}")
            all_variances.extend(variances)

        if all_variances:
            lines.append("  " + "-" * 56)
            overall_abs = round(sum(abs(v) for v in all_variances) / len(all_variances), 1)
            overall_mean = round(sum(all_variances) / len(all_variances), 1)
            within_6  = sum(1 for v in all_variances if abs(v) <= 6)
            within_10 = sum(1 for v in all_variances if abs(v) <= 10)
            lines.append(f"  {'OVERALL':<12}  {len(all_variances):>4}  {overall_mean:>+10.1f}%  {overall_abs:>9.1f}%  {within_10}/{len(all_variances):>10}")
            lines.append(f"\n  Within ±6%  : {within_6}/{len(all_variances)} ({round(within_6/len(all_variances)*100)}%)")
            lines.append(f"  Within ±10% : {within_10}/{len(all_variances)} ({round(within_10/len(all_variances)*100)}%)")

            # Headline claim
            lines.append("\n── HEADLINE CLAIM ──")
            if overall_abs <= 6:
                lines.append(f"  ✅ DAC pricing within ±{overall_abs}% of market leaders (target: ±6%)")
            elif overall_abs <= 10:
                lines.append(f"  ⚠  DAC pricing within ±{overall_abs}% of market (target: ±6% — close)")
            else:
                lines.append(f"  ✗  DAC pricing diverges ±{overall_abs}% from market (review multipliers)")

        # ── Biggest outliers
        if comparison_rows:
            outliers = sorted(comparison_rows, key=lambda r: r["abs_variance_pct"], reverse=True)[:5]
            lines.append("\n── TOP 5 OUTLIERS ──")
            for r in outliers:
                sign = "+" if r["variance_pct"] > 0 else ""
                lines.append(f"  {r['persona_id']}  {r['tier']:<10}  vs {r['competitor']:<10}  {sign}{r['variance_pct']}%  (DAC ${r['dac_annual']:,.0f}  vs  ${r['competitor_annual']:,.0f})")
    else:
        lines.append("\n── NO COMPETITOR DATA ──")
        lines.append("  Fill in competitor_quotes.csv with quotes from Bupa, AXA, Allianz, etc.")
        lines.append("  Then re-run: python scripts/run_benchmark.py --report-only")

    lines.append("\n" + "=" * 60)

    report = "\n".join(lines)
    with open(OUTPUT_DIR / "report.txt", "w") as f:
        f.write(report)

    print(report)
    print(f"\n  Saved: {OUTPUT_DIR / 'report.txt'}")


def main():
    parser = argparse.ArgumentParser(description="DAC HealthPrice competitor benchmark")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-only",    action="store_true", help="Run API calls only, skip comparison")
    parser.add_argument("--report-only", action="store_true", help="Skip API calls, re-run comparison from saved CSV")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)

    with open(PERSONAS_FILE) as f:
        personas = json.load(f)

    if args.report_only:
        print("── Report-only mode: loading saved DAC quotes ──")
        dac_rows = load_dac_quotes_from_csv()
    else:
        api_results = run_api_benchmark(args.base_url, personas)
        dac_rows = save_dac_quotes(api_results)

    if args.api_only:
        build_report(dac_rows, [], {})
        return

    competitor_data = load_competitor_quotes()
    comparison_rows, variances_by_competitor = run_comparison(dac_rows, competitor_data)
    build_report(dac_rows, comparison_rows, variances_by_competitor)


if __name__ == "__main__":
    main()
