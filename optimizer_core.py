import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from datetime import date, timedelta
from pathlib import Path

# -------------------------
# Constants (easy to tweak)
# -------------------------
AVG_MPH = 50
DAILY_MAX_HOURS = 11
MPG = 6
FUEL_PRICE = 4.0

# How strongly to prefer loads that move closer to TargetCity
TARGET_DISTANCE_WEIGHT = 0.35  # higher = more "family time" bias

# Variety control: prevent a driver from repeating the same route too often
ROUTE_COOLDOWN_DAYS = 30

ASSIGNMENT_HISTORY_PATH = Path("assignment_history.csv")


# -------------------------
# Data Setup
# -------------------------
drivers = pd.DataFrame({
    "DriverID": [1, 2, 3, 4, 5, 6],
    "CurrentCity": [
        "Chicago, IL", "Atlanta, GA", "St. Louis, MO",
        "Dallas, TX", "Nashville, TN", "Houston, TX"
    ],
    "TargetCity": [
        "Dallas, TX", "Orlando, FL", "Houston, TX",
        "Atlanta, GA", "Memphis, TN", "Chicago, IL"
    ],
    "AvailableHours": [40, 38, 45, 36, 42, 39]
})

# Kept for "latest snapshot" compatibility (your original 11 loads)
loads = pd.DataFrame({
    "LoadID": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
    "Origin": [
        "Chicago, IL", "Nashville, TN", "Atlanta, GA", "St. Louis, MO",
        "Dallas, TX", "Houston, TX", "Memphis, TN", "Orlando, FL",
        "Chicago, IL", "Atlanta, GA", "Suffolk, VA"
    ],
    "Destination": [
        "Memphis, TN", "Dallas, TX", "Orlando, FL", "Houston, TX",
        "Atlanta, GA", "St. Louis, MO", "Chicago, IL", "Nashville, TN",
        "Houston, TX", "Memphis, TN", "Charlotte, NC"
    ],
    "Payout": [1000, 1800, 1500, 2000, 1100, 1700, 1600, 1400, 2100, 1250, 1950],
    "Miles": [500, 800, 600, 950, 550, 870, 780, 690, 990, 560, 880]
})

city_coords = {
    "Chicago, IL": [41.8781, -87.6298],
    "Memphis, TN": [35.1495, -90.0490],
    "Nashville, TN": [36.1627, -86.7816],
    "Dallas, TX": [32.7767, -96.7970],
    "Atlanta, GA": [33.7490, -84.3880],
    "Orlando, FL": [28.5383, -81.3792],
    "St. Louis, MO": [38.6270, -90.1994],
    "Houston, TX": [29.7604, -95.3698],
    "Suffolk, VA": [36.7282, -76.5836],
    "Charlotte, NC": [35.2271, -80.8431]
}

ALL_CITIES = list(city_coords.keys())


# ------------------------------
# Helpers
# ------------------------------
def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2)**2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 3958.8 * c

def _coords_to_lat_lon(coords):
    if not coords or not isinstance(coords, (list, tuple)) or len(coords) != 2:
        return None, None
    return coords[0], coords[1]

def _calc_fuel_cost(miles):
    if miles is None or pd.isna(miles):
        return None
    return (float(miles) / MPG) * FUEL_PRICE

def _calc_hours_required(miles):
    if miles is None or pd.isna(miles):
        return None
    return float(miles) / AVG_MPH

def _distance_city_to_city(city_a, city_b):
    ca = city_coords.get(city_a)
    cb = city_coords.get(city_b)
    if not ca or not cb:
        return None
    return haversine(ca, cb)

def _safe_city(city):
    return city if city in city_coords else None

def _route_key(origin, destination):
    return f"{origin}__{destination}"


# ------------------------------
# Latest snapshot (1-load-per-driver)
# ------------------------------
def match_loads_by_destination(drivers_df, loads_df, city_coords_dict):
    assignments = []
    available_loads = loads_df.copy()

    for _, driver in drivers_df.iterrows():
        max_miles = driver["AvailableHours"] * AVG_MPH
        target_city = driver["TargetCity"]
        target_coords = city_coords_dict.get(target_city)

        eligible = available_loads[available_loads["Miles"] <= max_miles].copy()

        if not eligible.empty and target_coords:
            eligible["DistanceToTarget"] = eligible["Destination"].map(
                lambda d: haversine(city_coords_dict.get(d, (0, 0)), target_coords)
            )
            best = eligible.sort_values(
                by=["Payout", "DistanceToTarget"],
                ascending=[False, True]
            ).iloc[0]

            pickup_coords = city_coords_dict.get(best["Origin"].strip())
            dropoff_coords = city_coords_dict.get(best["Destination"].strip())
            pu_lat, pu_lon = _coords_to_lat_lon(pickup_coords)
            do_lat, do_lon = _coords_to_lat_lon(dropoff_coords)

            fuel_cost = _calc_fuel_cost(best["Miles"])
            net_profit = best["Payout"] - fuel_cost if fuel_cost is not None else None

            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": best["LoadID"],
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "LoadMiles": best["Miles"],
                "Payout": best["Payout"],
                "ToTargetMiles": round(best["DistanceToTarget"], 1),
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon,
                "FuelCost": fuel_cost,
                "NetProfit": net_profit
            })

            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
        else:
            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": None,
                "Origin": None,
                "Destination": None,
                "LoadMiles": None,
                "Payout": 0,
                "ToTargetMiles": None,
                "PickupLat": None,
                "PickupLon": None,
                "DropoffLat": None,
                "DropoffLon": None,
                "FuelCost": None,
                "NetProfit": None
            })

    return pd.DataFrame(assignments)

def build_latest_assignments_df():
    return match_loads_by_destination(drivers, loads, city_coords)


# ------------------------------
# Synthetic daily loads (for realistic history)
# ------------------------------
def generate_synthetic_loads_for_day(day: date, n_loads: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    Creates varied loads each day using city pairs + distance-based miles + payout noise.
    LoadID is unique per day (yyyymmddxxxx).
    """
    rows = []
    # bias some days to have popular destinations (trendable)
    hotspot_destinations = rng.choice(ALL_CITIES, size=min(3, len(ALL_CITIES)), replace=False)

    for i in range(n_loads):
        origin = rng.choice(ALL_CITIES)
        # 60% chance destination is a "hotspot", else random (trendable but not repetitive)
        if rng.random() < 0.60:
            destination = rng.choice(hotspot_destinations)
        else:
            destination = rng.choice(ALL_CITIES)

        # ensure not same city
        tries = 0
        while destination == origin and tries < 10:
            destination = rng.choice(ALL_CITIES)
            tries += 1

        dist = _distance_city_to_city(origin, destination)
        if dist is None:
            continue

        # miles ~ distance with noise
        miles = max(50, int(dist * rng.uniform(0.9, 1.15)))
        hours = miles / AVG_MPH

        # payout roughly correlated to miles, with randomness
        base_rate = rng.uniform(1.6, 2.8)  # $/mile-ish
        payout = int(miles * base_rate * rng.uniform(0.9, 1.2))

        load_id = int(f"{day.strftime('%Y%m%d')}{i:04d}")

        rows.append({
            "LoadID": load_id,
            "Origin": origin,
            "Destination": destination,
            "Miles": miles,
            "Payout": payout,
            "HoursRequired": round(hours, 2)
        })

    return pd.DataFrame(rows)


# ------------------------------
# Daily history: multiple loads per driver, 11-hour rule, TargetCity logic, variety rules
# ------------------------------
def build_daily_assignment_history(
    assigned_date: date,
    drivers_state: pd.DataFrame,
    day_loads: pd.DataFrame,
    route_recent: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns:
      - history_df for this assigned_date
      - updated drivers_state (CurrentCity updated to last completed destination)
    """
    history_rows = []
    available = day_loads.copy()

    # ensure required columns exist
    for col in ["HoursRequired"]:
        if col not in available.columns:
            available["HoursRequired"] = available["Miles"].apply(_calc_hours_required)

    updated_drivers = drivers_state.copy()

    for idx, driver in updated_drivers.iterrows():
        driver_id = int(driver["DriverID"])
        target_city = driver["TargetCity"]
        current_city = driver["CurrentCity"]

        remaining_hours_today = float(DAILY_MAX_HOURS)
        seq = 1

        # We'll keep assigning until they run out of day hours or no loads left
        while remaining_hours_today > 0 and not available.empty:
            # filter loads that can at least be started today (we allow spill to next day)
            eligible = available.copy()
            eligible = eligible[eligible["HoursRequired"] > 0]

            if eligible.empty:
                break

            # scoring:
            # - maximize payout per hour
            # - prefer loads whose DEST is closer to TargetCity (family time)
            eligible["PayoutPerHour"] = eligible["Payout"] / eligible["HoursRequired"]

            # distance-to-target
            eligible["DestToTarget"] = eligible["Destination"].apply(
                lambda d: _distance_city_to_city(d, target_city) if _safe_city(d) and _safe_city(target_city) else 999999
            )

            # variety rule: don't repeat same route for driver within cooldown
            def route_allowed(row):
                rk = _route_key(row["Origin"], row["Destination"])
                last_seen = route_recent.get((driver_id, rk))
                if last_seen is None:
                    return True
                return (assigned_date - last_seen).days >= ROUTE_COOLDOWN_DAYS

            eligible = eligible[eligible.apply(route_allowed, axis=1)]
            if eligible.empty:
                break

            # combined score: payout-per-hour minus normalized distance-to-target
            # normalize distance roughly to 0-1 scale using a soft divisor
            eligible["Score"] = eligible["PayoutPerHour"] - (TARGET_DISTANCE_WEIGHT * (eligible["DestToTarget"] / 1000.0))

            best = eligible.sort_values(by=["Score", "Payout"], ascending=[False, False]).iloc[0]

            miles = float(best["Miles"])
            hours_req = float(best["HoursRequired"])
            payout = float(best["Payout"])

            # completion rule you specified:
            # - if it fits within remaining hours today -> completes same day
            # - else completes next day
            trip_start = assigned_date
            trip_end = assigned_date if hours_req <= remaining_hours_today else (assigned_date + timedelta(days=1))

            # consume hours today
            remaining_hours_today = max(0.0, remaining_hours_today - hours_req)

            pickup_coords = city_coords.get(best["Origin"])
            dropoff_coords = city_coords.get(best["Destination"])
            pu_lat, pu_lon = _coords_to_lat_lon(pickup_coords)
            do_lat, do_lon = _coords_to_lat_lon(dropoff_coords)

            fuel_cost = _calc_fuel_cost(miles)
            net_profit = payout - fuel_cost if fuel_cost is not None else None

            history_rows.append({
                "AssignedDate": assigned_date.isoformat(),
                "TripStartDate": trip_start.isoformat(),
                "TripEndDate": trip_end.isoformat(),
                "DriverID": driver_id,
                "LoadID": int(best["LoadID"]),
                "LoadSequence": seq,
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "TargetCity": target_city,
                "Miles": miles,
                "HoursRequired": round(hours_req, 2),
                "Payout": payout,
                "FuelCost": round(fuel_cost, 2) if fuel_cost is not None else None,
                "NetProfit": round(net_profit, 2) if net_profit is not None else None,
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon
            })

            # mark route last used for this driver
            rk = _route_key(best["Origin"], best["Destination"])
            route_recent[(driver_id, rk)] = assigned_date

            # update driver's current city to last destination (for realism)
            current_city = best["Destination"]
            updated_drivers.loc[idx, "CurrentCity"] = current_city

            # remove load from pool
            available = available[available["LoadID"] != best["LoadID"]]
            seq += 1

    return pd.DataFrame(history_rows), updated_drivers


def update_assignment_history_csv(assigned_date: date, seed: int = 42) -> pd.DataFrame:
    """
    Appends ONE day of generated history to assignment_history.csv.
    Creates the file if missing.
    """
    rng = np.random.default_rng(seed + int(assigned_date.strftime("%Y%m%d")))
    day_loads = generate_synthetic_loads_for_day(assigned_date, n_loads=30, rng=rng)

    # build route memory from existing file (if present)
    route_recent = {}
    if ASSIGNMENT_HISTORY_PATH.exists():
        try:
            existing = pd.read_csv(ASSIGNMENT_HISTORY_PATH)
            # store last date each driver used each route
            existing["AssignedDate"] = pd.to_datetime(existing["AssignedDate"]).dt.date
            for _, r in existing.iterrows():
                route_recent[(int(r["DriverID"]), _route_key(r["Origin"], r["Destination"]))] = r["AssignedDate"]
        except Exception:
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()

    drivers_state = drivers.copy()
    new_df, _ = build_daily_assignment_history(assigned_date, drivers_state, day_loads, route_recent)

    if existing.empty:
        combined = new_df
    else:
        combined = pd.concat([existing, new_df], ignore_index=True)

        # de-dupe by (AssignedDate, DriverID, LoadID, LoadSequence)
        combined = combined.drop_duplicates(
            subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
            keep="first"
        )

    combined.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return combined


def backfill_assignment_history(
    end_date: date,
    years: int = 2,
    seed: int = 42
) -> pd.DataFrame:
    """
    Creates a realistic multi-year assignment_history.csv (overwrites file).
    - multiple loads per driver per day
    - 11-hour rule
    - TargetCity bias
    - variety: route cooldown per driver

    end_date: last date to include (inclusive)
    years: number of years to backfill
    """
    start_date = end_date - timedelta(days=365 * years)

    rng = np.random.default_rng(seed)
    route_recent = {}

    drivers_state = drivers.copy()
    all_days = []

    d = start_date
    while d <= end_date:
        # daily loads vary by weekday (more loads midweek)
        weekday = d.weekday()  # Mon=0..Sun=6
        base = 28 if weekday in (1, 2, 3) else 22
        n_loads = int(base + rng.integers(-4, 6))

        day_rng = np.random.default_rng(seed + int(d.strftime("%Y%m%d")))
        day_loads = generate_synthetic_loads_for_day(d, n_loads=n_loads, rng=day_rng)

        day_history, drivers_state = build_daily_assignment_history(
            assigned_date=d,
            drivers_state=drivers_state,
            day_loads=day_loads,
            route_recent=route_recent
        )
        if not day_history.empty:
            all_days.append(day_history)

        d += timedelta(days=1)

    history = pd.concat(all_days, ignore_index=True) if all_days else pd.DataFrame()
    history.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return history
