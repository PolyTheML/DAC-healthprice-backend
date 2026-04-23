"""
Phnom Penh Drift Simulator — Auto Telemetry Generator

Usage:
    python scripts/auto_telemetry_generator.py
    python scripts/auto_telemetry_generator.py --policy-id AUTO-XXXXXX
    python scripts/auto_telemetry_generator.py --base-url https://dac-healthprice-api.onrender.com

Phase 1 (0-30s): Normal driving  
Phase 2 (30s+):  High-risk "Phnom Penh Drift" behavior
"""
from __future__ import annotations
import argparse
import asyncio
import random
from datetime import datetime, timezone

import httpx


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_policy(client: httpx.AsyncClient, base_url: str) -> str:
    """Create a dummy auto policy and return its policy_id."""
    payload = {
        "vehicle_type": random.choice(["sedan", "suv", "motorcycle", "truck"]),
        "year_of_manufacture": random.randint(2010, 2023),
        "region": "phnom_penh",
        "driver_age": random.randint(25, 55),
        "accident_history": False,
        "coverage": "full",
        "tier": "standard",
        "family_size": 1,
    }
    resp = await client.post(f"{base_url}/api/v1/auto/quote", json=payload)
    resp.raise_for_status()
    data = resp.json()
    policy_id = data["policy_id"]
    print(f"✅ Created policy {policy_id}")
    print(f"   GLM anchor      = {data['glm_anchor']:,.0f} VND")
    print(f"   Initial premium = {data['current_premium']:,.0f} VND")
    return policy_id


async def simulate(base_url: str, policy_id: str | None = None):
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        if policy_id is None:
            policy_id = await create_policy(client, base_url)

        print(f"\n🚗 Starting telemetry simulation for {policy_id}")
        print("-" * 60)

        phase = "normal"
        start = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start

            if elapsed > 30 and phase == "normal":
                phase = "drift"
                print("\n⚠️  PHASE CHANGE → Phnom Penh Drift (high-risk behaviour)\n")

            # Event generation
            if phase == "normal":
                speed = max(0, random.gauss(40, 12))
                harsh = random.random() < 0.05
                lanes = random.randint(0, 1)
            else:
                speed = max(0, random.gauss(85, 18))
                harsh = random.random() < 0.45
                lanes = random.randint(2, 5)

            event = {
                "policy_id": policy_id,
                "gps_lat": 11.5564 + random.gauss(0, 0.008),
                "gps_lon": 104.9282 + random.gauss(0, 0.008),
                "speed_kmh": round(speed, 1),
                "harsh_braking": harsh,
                "lane_shifts": lanes,
                "timestamp": _now_iso(),
            }

            try:
                resp = await client.post(
                    f"{base_url}/api/v1/auto/telematics-event", json=event
                )
                data = resp.json()
                print(
                    f"[{phase:6}] speed={event['speed_kmh']:5.1f} km/h  "
                    f"braking={'YES' if harsh else 'no ':>3}  lanes={lanes}  "
                    f"premium={data.get('new_premium', 0):>12,.0f} VND  "
                    f"deviation={data.get('deviation', 0):.3f}"
                )
            except httpx.HTTPStatusError as e:
                print(f"HTTP error {e.response.status_code}: {e.response.text}")
            except Exception as e:
                print(f"❌ Network error: {e}")

            await asyncio.sleep(2)


def main():
    parser = argparse.ArgumentParser(
        description="Auto telemetry simulator for continuous underwriting demo"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="FastAPI base URL",
    )
    parser.add_argument(
        "--policy-id",
        default=None,
        help="Existing policy ID (if omitted, a new one is created)",
    )
    args = parser.parse_args()
    asyncio.run(simulate(args.base_url, args.policy_id))


if __name__ == "__main__":
    main()
