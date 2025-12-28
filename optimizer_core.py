import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from datetime import date, timedelta
from pathlib import Path

# -------------------------
# Constants (easy to tweak)
# -------------------------
AVG_MPH = 50                     # used to convert miles -> hours
DAILY_MAX_HOURS = 11             # 11-hour rule
MPG = 6
FUEL_PRICE = 4.0

# Backfill defaults
BACKFILL_DAYS = 365 * 2          # 2 years
LOADS_PER_DAY = 30               # synthetic load pool size per day
SEED = 42

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

# Base “seed” loads (used for latest snapshot + as inspiration)
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


# ------------------------------
# Utilities
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


def _safe_read_history(path: Path) -> pd.DataFrame:
    """
    Reads assignment_history.csv safely.
    If the file doesn't exist, is empty, or is malformed, returns an empty DF
    with expected columns.
    """
    cols = [
        "AssignedDate", "TripStartDate", "TripEndDate",
        "DriverID", "DriverTargetCity",
        "LoadID", "LoadSequence",
        "Origin", "Destination",
        "Miles", "HoursRequired",
        "Payout", "FuelCost", "NetProfit",
        "PickupLat", "PickupLon", "DropoffLat", "DropoffLon"
    ]

    if not path.exists():
        return pd.DataFrame(columns=cols)

    try:
        df = pd.read_csv(path)
        # If it's blank or has 1 weird column, normalize
        if df.empty or len(df.columns) < 5:
            return pd.DataFrame(columns=cols)
        # Ensure all required columns exist
        for c in cols:
            if c not in df.columns:
                df[c] = None
        return df[cols]
    except Exception:
        # Malformed CSV (like your ParserError). Treat as empty.
        return pd.DataFrame(columns=cols)


def _route_key(row) -> str:
    return f"{row['Origin']}__{row['Destination']}"


# ------------------------------
# Latest snapshot (1 load per driver)
# ------------------------------
def match_loads_by_destination(drivers_df, loads_df, city_coords_dict):
    assignments = []
    available_loads = loads_df.copy()

    for _, driver in drivers_df.iterrows():
        max_miles = driver["AvailableHours"] * AVG_MPH
        target_coords = city_coords_dict.get(driver["TargetCity"])

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
# Synthetic load generation for history (variety)
# ------------------------------
def generate_synthetic_loads(for_date: date, n: int = LOADS_PER_DAY, seed: int = SEED) -> pd.DataFrame:
    """
    Generates a realistic set of loads for a given day with variety.
    Miles are based on haversine distance with noise.
    Payout correlates with miles with noise.
    """
    rng = np.random.default_rng(int(seed) + int(for_date.toordinal()))
    cities = list(city_coords.keys())

    rows = []
    load_id_base = int(for_date.strftime("%y%m%d")) * 1000  # stable-ish unique per date
    i = 0

    while len(rows) < n:
        origin = rng.choice(cities)
        dest = rng.choice(cities)
        if dest == origin:
            continue

        o_coord = city_coords[origin]
        d_coord = city_coords[dest]
        base_miles = haversine(o_coord, d_coord)

        # keep miles within a reasonable operational range
        # noise factor + min cap
        miles = max(120, base_miles * rng.uniform(0.85, 1.15))
        miles = float(round(miles))

        # payout: ~ $1.6 to $2.6 per mile + noise
        rate = rng.uniform(1.6, 2.6)
        payout = miles * rate + rng.normal(0, 75)
        payout = float(round(max(400, payout), 0))

        rows.append({
            "LoadID": load_id_base + i,
            "Origin": origin,
            "Destination": dest,
            "Miles": miles,
            "Payout": payout
        })
        i += 1

    return pd.DataFrame(rows)


# ------------------------------
# History: multi-load/day using 11-hour rule + TargetCity logic + anti-repeat
# ------------------------------
def build_daily_assignment_history(assigned_date: date,
                                  loads_df: pd.DataFrame,
                                  drivers_df: pd.DataFrame,
                                  existing_history: pd.DataFrame) -> pd.DataFrame:
    """
    For one assigned_date, each driver can take multiple loads per day up to 11 hours.
    If hours spill beyond remaining hours for the day, TripEndDate becomes next day.
    Variety: avoid repeating the same origin/destination for the same driver
            if it appeared in the last ~60 days.
    TargetCity logic: prefer loads whose Destination moves driver closer to TargetCity
            (soft preference, not a hard constraint).
    """
    history_rows = []
    available_loads = loads_df.copy()

    # build recent-route memory per driver (last 60 days)
    cutoff = assigned_date - timedelta(days=60)
    recent = existing_history.copy()
    if not recent.empty:
        recent["AssignedDate"] = pd.to_datetime(recent["AssignedDate"], errors="coerce")
        recent = recent[recent["AssignedDate"] >= pd.Timestamp(cutoff)]
    recent_routes = {}
    for d in drivers_df["DriverID"].tolist():
        if recent.empty:
            recent_routes[int(d)] = set()
        else:
            r = recent[recent["DriverID"] == int(d)].copy()
            recent_routes[int(d)] = set((r["Origin"].astype(str) + "__" + r["Destination"].astype(str)).tolist())

    # precompute target coords
    target_coords_by_driver = {
        int(row["DriverID"]): city_coords.get(row["TargetCity"])
        for _, row in drivers_df.iterrows()
    }

    # add HoursRequired + payout/hour to available_loads
    available_loads = available_loads.copy()
    available_loads["HoursRequired"] = available_loads["Miles"].apply(_calc_hours_required)
    available_loads["PayoutPerHour"] = available_loads["Payout"] / available_loads["HoursRequired"]

    for _, driver in drivers_df.iterrows():
        driver_id = int(driver["DriverID"])
        target_city = str(driver["TargetCity"])
        target_coord = target_coords_by_driver.get(driver_id)

        remaining_hours_today = float(DAILY_MAX_HOURS)
        day_offset = 0
        seq = 1

        # cap planning horizon by driver AvailableHours (week-ish capacity)
        driver_total_remaining_hours = float(driver["AvailableHours"])

        while driver_total_remaining_hours > 0 and not available_loads.empty:
            # eligible must fit into remaining overall hours
            eligible = available_loads[available_loads["HoursRequired"] <= driver_total_remaining_hours].copy()
            if eligible.empty:
                break

            # anti-repeat: remove routes the driver has done recently
            eligible["RouteKey"] = eligible.apply(_route_key, axis=1)
            eligible = eligible[~eligible["RouteKey"].isin(recent_routes[driver_id])].copy()

            # if anti-repeat filtered everything, allow repeats (but still pick best)
            if eligible.empty:
                eligible = available_loads[available_loads["HoursRequired"] <= driver_total_remaining_hours].copy()
                eligible["RouteKey"] = eligible.apply(_route_key, axis=1)

            # TargetCity preference (soft): smaller distance-to-target is better
            if target_coord:
                eligible["ToTargetMiles"] = eligible["Destination"].map(
                    lambda d: haversine(city_coords.get(d, (0, 0)), target_coord)
                )
            else:
                eligible["ToTargetMiles"] = np.nan

            # Score: prioritize payout/hour, then payout; break ties by closer-to-target
            # We convert ToTargetMiles into a small penalty so high profit still wins.
            eligible["Score"] = (
                eligible["PayoutPerHour"] * 1000
                + eligible["Payout"]
                - eligible["ToTargetMiles"].fillna(0) * 0.25
            )

            best = eligible.sort_values(by=["Score"], ascending=[False]).iloc[0]

            hours_req = float(best["HoursRequired"])
            miles = float(best["Miles"])
            payout = float(best["Payout"])

            start_date = assigned_date + timedelta(days=day_offset)
            if hours_req <= remaining_hours_today:
                end_date = start_date
                remaining_hours_today -= hours_req
            else:
                end_date = start_date + timedelta(days=1)
                spill = hours_req - remaining_hours_today
                day_offset += 1
                remaining_hours_today = max(DAILY_MAX_HOURS - spill, 0)

            driver_total_remaining_hours -= hours_req

            pickup_coords = city_coords.get(str(best["Origin"]).strip())
            dropoff_coords = city_coords.get(str(best["Destination"]).strip())
            pu_lat, pu_lon = _coords_to_lat_lon(pickup_coords)
            do_lat, do_lon = _coords_to_lat_lon(dropoff_coords)

            fuel_cost = _calc_fuel_cost(miles)
            net_profit = payout - fuel_cost if fuel_cost is not None else None

            history_rows.append({
                "AssignedDate": assigned_date.isoformat(),
                "TripStartDate": start_date.isoformat(),
                "TripEndDate": end_date.isoformat(),
                "DriverID": driver_id,
                "DriverTargetCity": target_city,
                "LoadID": int(best["LoadID"]),
                "LoadSequence": seq,
                "Origin": str(best["Origin"]),
                "Destination": str(best["Destination"]),
                "Miles": round(miles, 0),
                "HoursRequired": round(hours_req, 2),
                "Payout": round(payout, 0),
                "FuelCost": round(fuel_cost, 2) if fuel_cost is not None else None,
                "NetProfit": round(net_profit, 2) if net_profit is not None else None,
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon
            })

            # record route to prevent reusing for this driver soon
            recent_routes[driver_id].add(f"{best['Origin']}__{best['Destination']}")

            # remove load from pool
            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]].copy()

            seq += 1

            if remaining_hours_today <= 0:
                day_offset += 1
                remaining_hours_today = float(DAILY_MAX_HOURS)

    return pd.DataFrame(history_rows)


def update_assignment_history_csv(assigned_date: date,
                                  loads_per_day: int = LOADS_PER_DAY,
                                  seed: int = SEED) -> pd.DataFrame:
    """
    Appends one day's assignments into assignment_history.csv, creating it if needed.
    """
    existing = _safe_read_history(ASSIGNMENT_HISTORY_PATH)

    daily_loads = generate_synthetic_loads(for_date=assigned_date, n=loads_per_day, seed=seed)
    new_df = build_daily_assignment_history(
        assigned_date=assigned_date,
        loads_df=daily_loads,
        drivers_df=drivers,
        existing_history=existing
    )

    if new_df.empty:
        return existing

    combined = pd.concat([existing, new_df], ignore_index=True)

    combined = combined.drop_duplicates(
        subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
        keep="first"
    )

    combined.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return combined


def backfill_assignment_history(end_date: date = None,
                                days: int = BACKFILL_DAYS,
                                seed: int = SEED,
                                loads_per_day: int = LOADS_PER_DAY) -> pd.DataFrame:
    """
    Backfills assignment_history.csv for `days` ending at `end_date` (default today).
    Ensures variety via synthetic loads + anti-repeat logic.
    """
    if end_date is None:
        end_date = date.today()

    start_date = end_date - timedelta(days=days - 1)

    history = _safe_read_history(ASSIGNMENT_HISTORY_PATH)

    d = start_date
    while d <= end_date:
        # Each day updates with new synthetic loads; anti-repeat uses prior rows
        daily_loads = generate_synthetic_loads(for_date=d, n=loads_per_day, seed=seed)
        new_df = build_daily_assignment_history(
            assigned_date=d,
            loads_df=daily_loads,
            drivers_df=drivers,
            existing_history=history
        )
        if not new_df.empty:
            history = pd.concat([history, new_df], ignore_index=True)
            history = history.drop_duplicates(
                subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
                keep="first"
            )
        d += timedelta(days=1)

    history.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return history
