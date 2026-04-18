"""
real_route_telematics_generator.py  (v2)

Generates a thesis-grade Phnom Penh telematics dataset:
  - 30 Phnom Penh O-D pairs across all districts
  - 3 traffic snapshots per route (peak / midday / offpeak)
  - Routes cached to case-study/routes_cache.json (90 API calls, once)
  - 3 driver archetypes (commuter / delivery_rider / long_haul)
  - 1,500 baseline trips; optional drift cohorts for EXP-002/003/004

Two outputs:
  case-study/phnom_penh_pings.csv         — ping-level (~900K rows, route visualisation)
  case-study/phnom_penh_trip_features.csv — trip-level (~1,500 rows, PSI experiments)

Methodology constants (documented in thesis Ch3):
  Hard braking  : |acceleration| > 3.0 m/s²   (NHTSA threshold)
  Harsh jerk    : |jerk|         > 2.0 m/s³
  Idle          : speed          < 5.0 km/h

Setup:
  1. pip install googlemaps polyline python-dotenv
  2. GOOGLE_MAPS_API_KEY=<key> in .env (or export)
  3. python real_route_telematics_generator.py
     python real_route_telematics_generator.py --trips-per-route 60 --with-drift

DAC Auto Insurance — EXP-001/002/003/004 Dataset
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

import googlemaps
import numpy as np
import polyline as polyline_codec
from dotenv import find_dotenv, load_dotenv

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

rng = np.random.default_rng(42)

# ─── Methodology constants (cite in Ch3) ─────────────────────────────────────
GPS_INTERVAL_M          = 7.0   # metres between GPS pings
HARD_BRAKE_THRESH_MS2   = 3.0   # |accel| > 3 m/s²  → hard braking event (NHTSA)
HARSH_JERK_THRESH_MS3   = 2.0   # |jerk|  > 2 m/s³  → harsh maneuver
IDLE_SPEED_KMH          = 5.0   # speed   < 5 km/h   → idle ping
SPEED_NOISE_STD         = 1.5   # base km/h Gaussian noise on each ping

# ─── Hour-of-day trip-departure weights (reflects Phnom Penh traffic density) ─
_HW = np.ones(24)
_HW[7:9]   = 3.5   # morning peak
_HW[17:19] = 3.5   # evening peak
_HW[11:13] = 1.8   # lunch
_HW[0:5]   = 0.05  # near-zero night
_HW       /= _HW.sum()


# ═════════════════════════════════════════════════════════════════════════════
# 1.  PHNOM PENH POIs  &  O-D PAIRS
# ═════════════════════════════════════════════════════════════════════════════

POIS: dict[str, tuple[float, float]] = {
    "independence_monument": (11.5609, 104.9282),
    "royal_palace":          (11.5641, 104.9302),
    "central_market":        (11.5709, 104.9175),
    "riverside_sisowath":    (11.5694, 104.9305),
    "naga_world":            (11.5647, 104.9294),
    "calmette_hospital":     (11.5649, 104.9272),
    "bkk1":                  (11.5537, 104.9219),
    "tuol_sleng":            (11.5491, 104.9174),
    "olympic_stadium":       (11.5536, 104.9228),
    "russian_market":        (11.5384, 104.9257),
    "phsar_deum_thkov":      (11.5354, 104.9132),
    "stung_meanchey":        (11.5102, 104.9148),
    "aeon_mall_1":           (11.5530, 104.9055),
    "sorya_mall":            (11.5724, 104.9165),
    "toul_kork":             (11.5800, 104.9050),
    "aeon_mall_2_senkok":    (11.5891, 104.8998),
    "sen_sok_district":      (11.5958, 104.8935),
    "chip_mong_271":         (11.6055, 104.9155),
    "chroy_changvar":        (11.5923, 104.9497),
    "pnh_airport":           (11.5469, 104.8442),
}

# 30 O-D pairs: ~10 short (1-3 km), ~12 medium (3-8 km), ~8 long (8-15 km)
ROUTES: list[dict] = [
    # ── Short  ────────────────────────────────────────────────────────────────
    {"name": "independence_to_royal_palace",     "o": "independence_monument", "d": "royal_palace"},
    {"name": "central_market_to_riverside",      "o": "central_market",        "d": "riverside_sisowath"},
    {"name": "bkk1_to_tuol_sleng",               "o": "bkk1",                  "d": "tuol_sleng"},
    {"name": "olympic_stadium_to_russian_market","o": "olympic_stadium",        "d": "russian_market"},
    {"name": "naga_world_to_royal_palace",        "o": "naga_world",            "d": "royal_palace"},
    {"name": "bkk1_to_olympic_stadium",           "o": "bkk1",                  "d": "olympic_stadium"},
    {"name": "sorya_mall_to_central_market",      "o": "sorya_mall",            "d": "central_market"},
    {"name": "calmette_to_independence",          "o": "calmette_hospital",     "d": "independence_monument"},
    {"name": "riverside_to_calmette",             "o": "riverside_sisowath",    "d": "calmette_hospital"},
    {"name": "russian_market_to_phsar_deum_thkov","o": "russian_market",        "d": "phsar_deum_thkov"},
    # ── Medium  ───────────────────────────────────────────────────────────────
    {"name": "independence_to_aeon_mall_1",       "o": "independence_monument", "d": "aeon_mall_1"},
    {"name": "independence_to_aeon_mall_2",       "o": "independence_monument", "d": "aeon_mall_2_senkok"},
    {"name": "central_market_to_toul_kork",       "o": "central_market",        "d": "toul_kork"},
    {"name": "olympic_stadium_to_chip_mong",      "o": "olympic_stadium",       "d": "chip_mong_271"},
    {"name": "riverside_to_stung_meanchey",       "o": "riverside_sisowath",    "d": "stung_meanchey"},
    {"name": "russian_market_to_sen_sok",         "o": "russian_market",        "d": "sen_sok_district"},
    {"name": "calmette_to_aeon_mall_2",           "o": "calmette_hospital",     "d": "aeon_mall_2_senkok"},
    {"name": "tuol_sleng_to_royal_palace",        "o": "tuol_sleng",            "d": "royal_palace"},
    {"name": "phsar_deum_thkov_to_central_market","o": "phsar_deum_thkov",      "d": "central_market"},
    {"name": "toul_kork_to_chroy_changvar",       "o": "toul_kork",             "d": "chroy_changvar"},
    {"name": "aeon_mall_1_to_calmette",           "o": "aeon_mall_1",           "d": "calmette_hospital"},
    {"name": "sen_sok_to_olympic_stadium",        "o": "sen_sok_district",      "d": "olympic_stadium"},
    # ── Long  ─────────────────────────────────────────────────────────────────
    {"name": "riverside_to_airport",              "o": "riverside_sisowath",    "d": "pnh_airport"},
    {"name": "central_market_to_stung_meanchey",  "o": "central_market",        "d": "stung_meanchey"},
    {"name": "chroy_changvar_to_russian_market",  "o": "chroy_changvar",        "d": "russian_market"},
    {"name": "airport_to_chip_mong",              "o": "pnh_airport",           "d": "chip_mong_271"},
    {"name": "stung_meanchey_to_aeon_mall_2",     "o": "stung_meanchey",        "d": "aeon_mall_2_senkok"},
    {"name": "royal_palace_to_airport",           "o": "royal_palace",          "d": "pnh_airport"},
    {"name": "chip_mong_to_stung_meanchey",       "o": "chip_mong_271",         "d": "stung_meanchey"},
    {"name": "central_market_to_airport",         "o": "central_market",        "d": "pnh_airport"},
]

# ─── Traffic snapshots: 3 per route → 90 API calls total ─────────────────────
# departure_time must be future; we use next Monday at these hours.
SNAPSHOTS: dict[str, dict] = {
    "peak":    {"hour": 7,  "minute": 30},   # morning rush
    "midday":  {"hour": 12, "minute": 0},    # lunch lull
    "offpeak": {"hour": 20, "minute": 30},   # post-evening rush
}

def _snapshot_key(hour: int) -> str:
    if (7 <= hour <= 9) or (17 <= hour <= 19):
        return "peak"
    elif 10 <= hour <= 16:
        return "midday"
    return "offpeak"

def _next_monday_at(hour: int, minute: int) -> datetime:
    """Return the next Monday (or today if it is Monday and time is future) at hour:minute."""
    now = datetime.now()
    days = (0 - now.weekday()) % 7  # 0 = Monday
    candidate = (now + timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=7)
    return candidate


# ═════════════════════════════════════════════════════════════════════════════
# 2.  DRIVER ARCHETYPES
# ═════════════════════════════════════════════════════════════════════════════

ARCHETYPES: dict[str, dict] = {
    "commuter": {
        "speed_scale":  0.85,   # cautious, trapped in traffic
        "speed_noise":  1.5,    # km/h std
        "idle_prob":    0.12,   # P(this ping is near-stopped)
        "weight":       0.50,
    },
    "delivery_rider": {
        "speed_scale":  1.10,   # weaves, uses shortcuts
        "speed_noise":  3.0,
        "idle_prob":    0.04,   # brief stops at drop-off points
        "weight":       0.30,
    },
    "long_haul": {
        "speed_scale":  1.20,   # national roads, less congestion
        "speed_noise":  2.0,
        "idle_prob":    0.01,
        "weight":       0.20,
    },
}

_ARCHETYPE_NAMES   = list(ARCHETYPES.keys())
_ARCHETYPE_WEIGHTS = np.array([ARCHETYPES[a]["weight"] for a in _ARCHETYPE_NAMES])
_ARCHETYPE_WEIGHTS /= _ARCHETYPE_WEIGHTS.sum()

# ─── Vibration zones ─────────────────────────────────────────────────────────
VIBRATION_ZONES: list[dict] = [
    {"name": "suburban_north",    "lat": (11.595, 11.645), "lon": (104.855, 104.915), "vib": (0.60, 0.92)},
    {"name": "suburban_south",    "lat": (11.500, 11.548), "lon": (104.870, 104.940), "vib": (0.42, 0.78)},
    {"name": "central_boulevard", "lat": (11.555, 11.585), "lon": (104.910, 104.940), "vib": (0.05, 0.25)},
    {"name": "riverside",         "lat": (11.555, 11.578), "lon": (104.928, 104.960), "vib": (0.10, 0.32)},
    {"name": "national_road",     "lat": (11.505, 11.645), "lon": (104.962, 104.988), "vib": (0.18, 0.44)},
]
_DEFAULT_VIB = (0.20, 0.50)


# ═════════════════════════════════════════════════════════════════════════════
# 3.  GEO HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin(math.radians(lat2 - lat1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(min(1.0, a)))


def interpolate_segment(p1, p2, interval_m):
    d = haversine_m(p1[0], p1[1], p2[0], p2[1])
    if d < interval_m:
        return [p1]
    n = max(1, int(d / interval_m))
    return [(p1[0] + (i / n) * (p2[0] - p1[0]),
             p1[1] + (i / n) * (p2[1] - p1[1])) for i in range(n)]


def zone_vibration(lat: float, lon: float) -> float:
    for z in VIBRATION_ZONES:
        if z["lat"][0] <= lat <= z["lat"][1] and z["lon"][0] <= lon <= z["lon"][1]:
            lo, hi = z["vib"]
            return float(np.clip(rng.uniform(lo, hi) + rng.normal(0, 0.015), 0.0, 1.0))
    lo, hi = _DEFAULT_VIB
    return float(np.clip(rng.uniform(lo, hi), 0.0, 1.0))


# ═════════════════════════════════════════════════════════════════════════════
# 4.  ROUTE FETCHING  &  CACHING
# ═════════════════════════════════════════════════════════════════════════════

def _fetch_steps(client: googlemaps.Client, origin: str, destination: str,
                 departure: datetime) -> list[dict]:
    result = client.directions(origin, destination, mode="driving",
                               departure_time=departure, traffic_model="best_guess")
    if not result:
        raise RuntimeError(f"No route: {origin} → {destination}")
    steps_out = []
    for leg in result[0]["legs"]:
        base_s    = leg["duration"]["value"]
        traffic_s = leg.get("duration_in_traffic", leg["duration"])["value"]
        scale     = (traffic_s / base_s) if base_s > 0 else 1.0
        for step in leg["steps"]:
            dist_m = step["distance"]["value"]
            step_s = step["duration"]["value"] * scale
            spd    = (dist_m / step_s * 3.6) if step_s > 0 else 5.0
            steps_out.append({
                "points":     polyline_codec.decode(step["polyline"]["points"]),
                "speed_kmh":  max(1.0, spd),
                "distance_m": dist_m,
            })
    return steps_out


def fetch_and_cache(client: googlemaps.Client, cache_path: Path,
                    routes: list[dict], snapshots: dict) -> dict:
    """
    Fetch 3 traffic snapshots for every route; save to cache_path as JSON.
    Returns the cache dict.  Skips routes already present in an existing cache.
    """
    cache: dict = {}
    if cache_path.exists():
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        log.info(f"Loaded existing cache ({len(cache)} entries) from {cache_path}")

    n_new = 0
    total = len(routes) * len(snapshots)
    done  = 0

    for route in routes:
        o_coord = "{},{}".format(*POIS[route["o"]])
        d_coord = "{},{}".format(*POIS[route["d"]])

        for snap_name, snap_time in snapshots.items():
            key = f"{route['name']}:{snap_name}"
            if key in cache:
                done += 1
                continue

            depart = _next_monday_at(snap_time["hour"], snap_time["minute"])
            try:
                steps = _fetch_steps(client, o_coord, d_coord, depart)
                # JSON-serialise: points are list-of-lists
                cache[key] = [
                    {"points": list(s["points"]), "speed_kmh": s["speed_kmh"],
                     "distance_m": s["distance_m"]}
                    for s in steps
                ]
                n_new += 1
                done += 1
                log.info(f"  [{done}/{total}] cached {key}  "
                         f"({sum(s['distance_m'] for s in steps)/1000:.2f} km, "
                         f"{len(steps)} steps)")
            except Exception as exc:
                log.warning(f"  SKIP {key}: {exc}")
                done += 1

            time.sleep(0.05)   # polite pause between API calls

    if n_new > 0:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        log.info(f"Saved {n_new} new entries to cache → {cache_path}")

    return cache


# ═════════════════════════════════════════════════════════════════════════════
# 5.  PING GENERATION
# ═════════════════════════════════════════════════════════════════════════════

def build_pings(steps: list[dict], trip_id: str, route_name: str,
                archetype_name: str, departure_time: datetime,
                interval_m: float, cohort: str = "baseline",
                drift_fraction: float = 0.0) -> list[dict]:
    """
    Generate high-frequency GPS pings for one trip.

    drift_fraction (0–1): amplifies aggressive-driving parameters for
    EXP-002 distortion cohorts.  0 = baseline behaviour.
    """
    arch = ARCHETYPES[archetype_name]
    # Drift amplification: scale speed up, reduce idle probability
    spd_scale   = arch["speed_scale"]  * (1.0 + 0.15 * drift_fraction)
    spd_noise   = arch["speed_noise"]  * (1.0 + 0.50 * drift_fraction)
    idle_p      = arch["idle_prob"]    * max(0.0, 1.0 - drift_fraction)

    flat: list[tuple[float, float, float]] = []

    for step in steps:
        pts      = step["points"]
        base_spd = step["speed_kmh"] * spd_scale

        for i in range(len(pts) - 1):
            for lat, lon in interpolate_segment(pts[i], pts[i + 1], interval_m):
                if rng.random() < idle_p:
                    spd = float(rng.uniform(0.5, 4.0))  # near-stopped
                else:
                    spd = float(max(0.5, base_spd + rng.normal(0, spd_noise)))
                flat.append((lat, lon, spd))

        spd = float(max(0.5, base_spd + rng.normal(0, spd_noise)))
        flat.append((pts[-1][0], pts[-1][1], spd))

    if not flat:
        return []

    pings: list[dict] = []
    ts         = departure_time
    prev_v     = flat[0][2] / 3.6
    prev_accel = 0.0

    for seq, (lat, lon, spd_kmh) in enumerate(flat):
        v_ms  = spd_kmh / 3.6
        dt    = (interval_m / v_ms) if v_ms > 0 else 5.0
        accel = (v_ms - prev_v) / dt  if dt > 0 else 0.0
        jerk  = (accel - prev_accel) / dt if dt > 0 else 0.0

        pings.append({
            "trip_id":             trip_id,
            "route_name":          route_name,
            "archetype":           archetype_name,
            "cohort":              cohort,
            "drift_fraction":      drift_fraction,
            "ping_seq":            seq,
            "timestamp":           ts.isoformat(timespec="milliseconds"),
            "GPS_Lat":             round(lat, 7),
            "GPS_Lon":             round(lon, 7),
            "speed_kmh":           round(spd_kmh, 3),
            "acceleration_m_s2":   round(accel, 5),
            "jerk_m_s3":           round(jerk, 5),
            "vibration_intensity": round(zone_vibration(lat, lon), 4),
            "dt_s":                round(dt, 4),
        })
        prev_v     = v_ms
        prev_accel = accel
        ts        += timedelta(seconds=dt)

    return pings


# ═════════════════════════════════════════════════════════════════════════════
# 6.  POPULATION GENERATOR
# ═════════════════════════════════════════════════════════════════════════════

def generate_population(
    cache:            dict,
    routes:           list[dict],
    trips_per_route:  int,
    cohort:           str          = "baseline",
    drift_fraction:   float        = 0.0,
    interval_m:       float        = GPS_INTERVAL_M,
    base_date:        datetime     = None,
) -> list[dict]:
    """
    Generate trips_per_route synthetic trips for every route.
    Each trip gets a random archetype (weighted) and departure hour.
    Returns flat list of all ping dicts.
    """
    if base_date is None:
        base_date = datetime(2026, 4, 21)   # Monday baseline

    all_pings: list[dict] = []
    trip_counter = 0

    for route in routes:
        for _ in range(trips_per_route):
            # Sample archetype and departure hour
            arch_name = str(rng.choice(_ARCHETYPE_NAMES, p=_ARCHETYPE_WEIGHTS))
            hour      = int(rng.choice(range(24), p=_HW))
            minute    = int(rng.integers(0, 60))
            snap_key  = f"{route['name']}:{_snapshot_key(hour)}"

            if snap_key not in cache:
                # fallback to any available snapshot for this route
                fallbacks = [k for k in cache if k.startswith(route["name"] + ":")]
                if not fallbacks:
                    continue
                snap_key = fallbacks[0]

            steps = cache[snap_key]
            trip_counter += 1
            trip_id      = f"{cohort[:3].upper()}{trip_counter:05d}"
            depart       = base_date.replace(hour=hour, minute=minute)

            pings = build_pings(
                steps        = steps,
                trip_id      = trip_id,
                route_name   = route["name"],
                archetype_name = arch_name,
                departure_time = depart,
                interval_m   = interval_m,
                cohort       = cohort,
                drift_fraction = drift_fraction,
            )
            all_pings.extend(pings)

    log.info(f"  Cohort '{cohort}' ({drift_fraction:.0%} drift): "
             f"{trip_counter} trips, {len(all_pings):,} pings")
    return all_pings


# ═════════════════════════════════════════════════════════════════════════════
# 7.  TRIP-LEVEL AGGREGATION  (PSI-ready)
# ═════════════════════════════════════════════════════════════════════════════

def aggregate_trip_features(all_pings: list[dict]) -> list[dict]:
    """
    Aggregate ping-level data to one row per trip.
    Columns match the feature set used in PSI calculations (thesis Ch4).
    """
    from collections import defaultdict
    trips: dict[str, list] = defaultdict(list)
    for p in all_pings:
        trips[p["trip_id"]].append(p)

    rows: list[dict] = []
    for tid, pings in trips.items():
        speeds  = [p["speed_kmh"]           for p in pings]
        accels  = [p["acceleration_m_s2"]    for p in pings]
        jerks   = [p["jerk_m_s3"]            for p in pings]
        vibs    = [p["vibration_intensity"]  for p in pings]
        dts     = [p["dt_s"]                 for p in pings]

        total_s = sum(dts)
        idle_s  = sum(dt for spd, dt in zip(speeds, dts) if spd < IDLE_SPEED_KMH)

        rows.append({
            "trip_id":              tid,
            "route_name":           pings[0]["route_name"],
            "archetype":            pings[0]["archetype"],
            "cohort":               pings[0]["cohort"],
            "drift_fraction":       pings[0]["drift_fraction"],
            "departure_hour":       int(pings[0]["timestamp"][11:13]),
            "is_peak_hour":         int(_snapshot_key(int(pings[0]["timestamp"][11:13])) == "peak"),
            "n_pings":              len(pings),
            "trip_duration_min":    round(total_s / 60, 2),
            "trip_distance_km":     round(len(pings) * GPS_INTERVAL_M / 1000, 3),
            # Speed features
            "speed_avg_kmh":        round(float(np.mean(speeds)), 3),
            "speed_p90_kmh":        round(float(np.percentile(speeds, 90)), 3),
            "speed_max_kmh":        round(float(np.max(speeds)), 3),
            # Braking / jerk events
            "hard_braking_events":  sum(1 for a in accels if abs(a) > HARD_BRAKE_THRESH_MS2),
            "harsh_jerk_events":    sum(1 for j in jerks  if abs(j) > HARSH_JERK_THRESH_MS3),
            "jerk_rms":             round(float(np.sqrt(np.mean(np.array(jerks) ** 2))), 5),
            # Idle
            "idle_pct":             round(idle_s / total_s if total_s > 0 else 0.0, 4),
            # Vibration
            "vibration_avg":        round(float(np.mean(vibs)), 4),
            "vibration_max":        round(float(np.max(vibs)), 4),
        })

    return rows


# ═════════════════════════════════════════════════════════════════════════════
# 8.  STREAMING SIMULATION
# ═════════════════════════════════════════════════════════════════════════════

def stream_pings(pings: list[dict], delay_s: float) -> Iterator[dict]:
    for ping in pings:
        if delay_s > 0:
            time.sleep(delay_s)
        yield ping


# ═════════════════════════════════════════════════════════════════════════════
# 9.  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(description="Phnom Penh Real-Route Telematics Generator v2")
    ROOT = Path(__file__).parent.parent.parent / "case-study"

    parser.add_argument("--cache",   default=str(ROOT / "routes_cache.json"))
    parser.add_argument("--pings",   default=str(ROOT / "phnom_penh_pings.csv"))
    parser.add_argument("--trips",   default=str(ROOT / "phnom_penh_trip_features.csv"))
    parser.add_argument("--trips-per-route", type=int, default=50,
                        help="Synthetic trips generated per route (default: 50 → 1,500 total)")
    parser.add_argument("--interval", type=float, default=GPS_INTERVAL_M,
                        metavar="METRES")
    parser.add_argument("--with-drift", action="store_true",
                        help="Also generate EXP-002 distortion cohorts (0.1–0.5)")
    parser.add_argument("--stream",  action="store_true",
                        help="Simulate 50ms ping-emission delay")
    args = parser.parse_args()

    # ── API key ───────────────────────────────────────────────────────────────
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: GOOGLE_MAPS_API_KEY not set.\n"
            "  Add it to a .env file or: export GOOGLE_MAPS_API_KEY=your_key"
        )

    cache_path = Path(args.cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Fetch & cache routes ─────────────────────────────────────────
    log.info("═" * 60)
    log.info("PHASE 1 — Fetch & cache routes")
    log.info(f"  {len(ROUTES)} routes × {len(SNAPSHOTS)} snapshots = "
             f"{len(ROUTES)*len(SNAPSHOTS)} API calls  (cached after first run)")
    client = googlemaps.Client(key=api_key)
    cache  = fetch_and_cache(client, cache_path, ROUTES, SNAPSHOTS)
    log.info(f"  Cache ready: {len(cache)} entries")

    # ── Phase 2: Generate population ─────────────────────────────────────────
    log.info("═" * 60)
    log.info("PHASE 2 — Generate trip population")
    n = args.trips_per_route
    all_pings: list[dict] = []

    # Baseline
    all_pings += generate_population(cache, ROUTES, n, cohort="baseline",
                                     drift_fraction=0.0, interval_m=args.interval)

    # EXP-002 distortion cohorts (optional)
    if args.with_drift:
        for frac in (0.1, 0.2, 0.3, 0.4, 0.5):
            label = f"distorted_{int(frac*100):02d}pct"
            cohort_n = max(10, n // 3)   # smaller cohort for comparison
            all_pings += generate_population(
                cache, ROUTES, cohort_n, cohort=label,
                drift_fraction=frac, interval_m=args.interval,
                base_date=datetime(2026, 5, 21),  # offset date for temporal clarity
            )

    # ── Phase 3: Stream simulation (optional) ─────────────────────────────────
    if args.stream:
        log.info(f"Streaming {len(all_pings):,} pings at 50ms/ping ...")
        all_pings = list(stream_pings(all_pings, delay_s=0.05))

    # ── Phase 4: Write pings CSV ──────────────────────────────────────────────
    log.info("═" * 60)
    log.info("PHASE 3 — Write outputs")

    ping_fields = [
        "trip_id", "route_name", "archetype", "cohort", "drift_fraction",
        "ping_seq", "timestamp", "GPS_Lat", "GPS_Lon",
        "speed_kmh", "acceleration_m_s2", "jerk_m_s3",
        "vibration_intensity", "dt_s",
    ]
    pings_path = Path(args.pings)
    pings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pings_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=ping_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_pings)
    log.info(f"  pings  → {pings_path}  ({len(all_pings):,} rows)")

    # ── Phase 5: Aggregate & write trip features ──────────────────────────────
    trip_rows  = aggregate_trip_features(all_pings)
    trips_path = Path(args.trips)
    trip_fields = list(trip_rows[0].keys()) if trip_rows else []
    with open(trips_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=trip_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(trip_rows)
    log.info(f"  trips  → {trips_path}  ({len(trip_rows):,} rows)")

    # ── Summary ───────────────────────────────────────────────────────────────
    baseline = [t for t in trip_rows if t["cohort"] == "baseline"]
    log.info("")
    log.info("═" * 60)
    log.info(f"  Routes       : {len(ROUTES)}")
    log.info(f"  Total trips  : {len(trip_rows):,}  (baseline: {len(baseline):,})")
    log.info(f"  Total pings  : {len(all_pings):,}")
    if baseline:
        avg_spd  = sum(t["speed_avg_kmh"]    for t in baseline) / len(baseline)
        avg_brk  = sum(t["hard_braking_events"] for t in baseline) / len(baseline)
        avg_idle = sum(t["idle_pct"]          for t in baseline) / len(baseline)
        log.info(f"  Avg speed    : {avg_spd:.1f} km/h")
        log.info(f"  Avg hard brk : {avg_brk:.1f} events/trip")
        log.info(f"  Avg idle pct : {avg_idle*100:.1f}%")
    log.info("═" * 60)


# ─── dotenv helper ────────────────────────────────────────────────────────────
def _load_env() -> str | None:
    env = find_dotenv()
    if not env:
        return None
    with open(env, "rb") as f:
        bom = f.read(2)
    enc = "utf-16" if bom in (b"\xff\xfe", b"\xfe\xff") else "utf-8"
    load_dotenv(env, encoding=enc)
    return None   # already loaded above; main() passes None to load_dotenv (no-op)


if __name__ == "__main__":
    main()
