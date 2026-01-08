import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from datetime import date, timedelta, datetime, time 
from pathlib import Path
import random

# -------------------------
# Constants
# -------------------------
AVG_MPH = 50
DAILY_MAX_HOURS = 11
MPG = 6
FUEL_PRICE = 4.0

ASSIGNMENT_HISTORY_PATH = Path("assignment_history.csv")

# How many loads exist per day in the simulated market
DAILY_LOAD_POOL_SIZE = 40

# How strongly we favor loads that end closer to the driver TargetCity
TARGET_BIAS_WEIGHT = 0.15  # higher = more "must move toward target"

# Penalize repeating same destination for same driver (adds variety)
DEST_REPEAT_PENALTY = 0.35  # higher = less repetition

# -------------------------
# Base Driver Setup
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

# -------------------------
# Expanded City Coordinates (many states)
# -------------------------
city_coords = {
    # Midwest
    "Chicago, IL": [41.8781, -87.6298],
    "St. Louis, MO": [38.6270, -90.1994],
    "Indianapolis, IN": [39.7684, -86.1581],
    "Columbus, OH": [39.9612, -82.9988],
    "Detroit, MI": [42.3314, -83.0458],
    "Minneapolis, MN": [44.9778, -93.2650],
    "Kansas City, MO": [39.0997, -94.5786],

    # South
    "Atlanta, GA": [33.7490, -84.3880],
    "Nashville, TN": [36.1627, -86.7816],
    "Memphis, TN": [35.1495, -90.0490],
    "Dallas, TX": [32.7767, -96.7970],
    "Houston, TX": [29.7604, -95.3698],
    "San Antonio, TX": [29.4241, -98.4936],
    "New Orleans, LA": [29.9511, -90.0715],
    "Birmingham, AL": [33.5186, -86.8104],
    "Charlotte, NC": [35.2271, -80.8431],
    "Raleigh, NC": [35.7796, -78.6382],
    "Jacksonville, FL": [30.3322, -81.6557],
    "Orlando, FL": [28.5383, -81.3792],
    "Tampa, FL": [27.9506, -82.4572],

    # Mid-Atlantic / Northeast
    "Suffolk, VA": [36.7282, -76.5836],
    "Richmond, VA": [37.5407, -77.4360],
    "Washington, DC": [38.9072, -77.0369],
    "Baltimore, MD": [39.2904, -76.6122],
    "Philadelphia, PA": [39.9526, -75.1652],
    "New York, NY": [40.7128, -74.0060],
    "Boston, MA": [42.3601, -71.0589],

    # West / Southwest
    "Denver, CO": [39.7392, -104.9903],
    "Phoenix, AZ": [33.4484, -112.0740],
    "Las Vegas, NV": [36.1699, -115.1398],
    "Los Angeles, CA": [34.0522, -118.2437],
    "San Francisco, CA": [37.7749, -122.4194],
    "Seattle, WA": [47.6062, -122.3321],
    "Portland, OR": [45.5152, -122.6784],
    "Salt Lake City, UT": [40.7608, -111.8910],
}

ALL_CITIES = list(city_coords.keys())

# -------------------------
# Utility Functions
# -------------------------
def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 3958.8 * c

def _calc_hours_required(miles):
    if miles is None or pd.isna(miles):
        return None
    return miles / AVG_MPH

def _calc_fuel_cost(miles):
    if miles is None or pd.isna(miles):
        return None
    return (miles / MPG) * FUEL_PRICE

def _coords_to_lat_lon(coords):
    if not coords or not isinstance(coords, (list, tuple)) or len(coords) != 2:
        return None, None
    return coords[0], coords[1]

def _safe_read_history():
    """
    Read assignment_history.csv if it exists and is valid; otherwise return empty DF with correct columns.
    Also ensures DropoffLon exists even if older history files didn't have it.
    """
    cols = [
        "AssignedDate", "TripStartDate", "TripEndDate",
        "DriverID", "LoadID", "LoadSequence",
        "Origin", "Destination",
        "Miles", "HoursRequired", "Payout", "FuelCost", "NetProfit",
        "TargetCity",
        "PickupLat", "PickupLon", "DropoffLat", "DropoffLon"
    ]

    if not ASSIGNMENT_HISTORY_PATH.exists():
        return pd.DataFrame(columns=cols)

    try:
        df = pd.read_csv(ASSIGNMENT_HISTORY_PATH)

        if df.empty:
            return pd.DataFrame(columns=cols)

        # Normalize schema (add missing columns)
        for c in cols:
            if c not in df.columns:
                df[c] = None

        return df[cols]

    except Exception:
        # If file is broken/malformed, don't blow up your pipeline
        return pd.DataFrame(columns=cols)

# -------------------------
# LOAD POOL GENERATION (adds realism + new states)
# -------------------------
def generate_daily_load_pool(assigned_date: date, n_loads: int, rng: random.Random) -> pd.DataFrame:
    """
    Generates a daily pool of loads across many states, based on random city pairs.
    Miles computed via haversine * a realism factor; payout derived from miles with noise.
    """
    rows = []
    realism_factor = 1.18  # road miles > straight line

    for i in range(n_loads):
        origin = rng.choice(ALL_CITIES)
        dest = rng.choice(ALL_CITIES)
        while dest == origin:
            dest = rng.choice(ALL_CITIES)

        miles = haversine(city_coords[origin], city_coords[dest]) * realism_factor
        miles = max(60, min(miles, 2200))

        rpm = rng.uniform(1.6, 2.6)
        payout = miles * rpm + rng.uniform(50, 350)

        rows.append({
            "LoadID": int(assigned_date.strftime("%Y%m%d")) * 1000 + i,
            "Origin": origin,
            "Destination": dest,
            "Miles": round(miles, 0),
            "Payout": round(payout, 0)
        })

    return pd.DataFrame(rows)

# -------------------------
# LATEST SNAPSHOT (1 load per driver)
# -------------------------
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

            pickup_coords = city_coords_dict.get(str(best["Origin"]).strip())
            dropoff_coords = city_coords_dict.get(str(best["Destination"]).strip())
            pu_lat, pu_lon = _coords_to_lat_lon(pickup_coords)
            do_lat, do_lon = _coords_to_lat_lon(dropoff_coords)

            fuel_cost = _calc_fuel_cost(best["Miles"])
            net_profit = best["Payout"] - fuel_cost if fuel_cost is not None else None

            # ✅ Add back PickupCoords/DropoffCoords for Power BI stability
            pickup_coords_str = f"{pu_lat},{pu_lon}" if pu_lat is not None and pu_lon is not None else None
            dropoff_coords_str = f"{do_lat},{do_lon}" if do_lat is not None and do_lon is not None else None

            assignments.append({
                "DriverID": int(driver["DriverID"]),
                "AssignedLoadID": int(best["LoadID"]),
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "LoadMiles": float(best["Miles"]),
                "Payout": float(best["Payout"]),
                "ToTargetMiles": round(float(best["DistanceToTarget"]), 1),
                "TargetCity": target_city,

                # ✅ both formats
                "PickupCoords": pickup_coords_str,
                "DropoffCoords": dropoff_coords_str,
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon,

                "FuelCost": round(fuel_cost, 2) if fuel_cost is not None else None,
                "NetProfit": round(net_profit, 2) if net_profit is not None else None
            })

            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
        else:
            assignments.append({
                "DriverID": int(driver["DriverID"]),
                "AssignedLoadID": None,
                "Origin": None,
                "Destination": None,
                "LoadMiles": None,
                "Payout": 0,
                "ToTargetMiles": None,
                "TargetCity": target_city,

                # ✅ both formats
                "PickupCoords": None,
                "DropoffCoords": None,
                "PickupLat": None,
                "PickupLon": None,
                "DropoffLat": None,
                "DropoffLon": None,

                "FuelCost": None,
                "NetProfit": None
            })

    return pd.DataFrame(assignments)

def build_latest_assignments_df():
    """
    Generates a daily load pool (realistic) then assigns 1 load per driver for the snapshot.
    """
    rng = random.Random(int(date.today().strftime("%Y%m%d")))
    daily_pool = generate_daily_load_pool(date.today(), DAILY_LOAD_POOL_SIZE, rng)
    return match_loads_by_destination(drivers, daily_pool, city_coords)

# -------------------------
# HISTORY (multi-load per driver per day using 11-hour rule)
# -------------------------
def build_daily_assignment_history(assigned_date: date, rng_seed: int | None = None) -> pd.DataFrame:
    """
    Multi-load per driver per assigned_date, respecting 11-hour daily rule.
    Completion date:
      - same day if hours fit within remaining 11 hours
      - next day if it spills over
    Includes TargetCity logic and variety (penalize same destination repeats).
    """
    rng = random.Random(rng_seed if rng_seed is not None else int(assigned_date.strftime("%Y%m%d")))
    daily_pool = generate_daily_load_pool(assigned_date, DAILY_LOAD_POOL_SIZE, rng)

    history = _safe_read_history()

    recent = history.copy()
    if not recent.empty:
        recent["AssignedDate"] = pd.to_datetime(recent["AssignedDate"], errors="coerce")
        cutoff = pd.Timestamp(assigned_date) - pd.Timedelta(days=60)
        recent = recent[recent["AssignedDate"] >= cutoff]

    driver_recent_dests = {}
    for d in drivers["DriverID"].tolist():
        if recent.empty:
            driver_recent_dests[int(d)] = set()
        else:
            ddf = recent[recent["DriverID"] == int(d)]
            driver_recent_dests[int(d)] = set(ddf["Destination"].dropna().tolist())

    rows = []
    available_loads = daily_pool.copy()

    for _, driver in drivers.iterrows():
        driver_id = int(driver["DriverID"])
        target_city = driver["TargetCity"]
        target_coords = city_coords.get(target_city)

        remaining_today = float(DAILY_MAX_HOURS)
        day_offset = 0
        seq = 1

        driver_total_remaining = float(driver["AvailableHours"])

        while driver_total_remaining > 0 and not available_loads.empty:
            tmp = available_loads.copy()
            tmp["HoursRequired"] = tmp["Miles"].apply(_calc_hours_required)

            tmp = tmp[tmp["HoursRequired"] <= driver_total_remaining]
            if tmp.empty:
                break

            tmp["PayoutPerHour"] = tmp["Payout"] / tmp["HoursRequired"]

            if target_coords:
                tmp["DistToTarget"] = tmp["Destination"].map(
                    lambda c: haversine(city_coords.get(c, (0, 0)), target_coords)
                )
            else:
                tmp["DistToTarget"] = 0

            tmp["RepeatPenalty"] = tmp["Destination"].apply(
                lambda d: 1 if d in driver_recent_dests.get(driver_id, set()) else 0
            )

            tmp["Score"] = (
                tmp["PayoutPerHour"]
                - TARGET_BIAS_WEIGHT * (tmp["DistToTarget"] / 1000.0)
                - DEST_REPEAT_PENALTY * tmp["RepeatPenalty"]
            )

            best = tmp.sort_values(by=["Score", "Payout"], ascending=[False, False]).iloc[0]

            hours_req = float(best["HoursRequired"])
            miles = float(best["Miles"])
            payout = float(best["Payout"])

            start_date = assigned_date + timedelta(days=day_offset)
            if hours_req <= remaining_today:
                end_date = start_date
                remaining_today -= hours_req
            else:
                end_date = start_date + timedelta(days=1)
                spill = hours_req - remaining_today
                day_offset += 1
                remaining_today = max(DAILY_MAX_HOURS - spill, 0)

            driver_total_remaining -= hours_req

            pu_coords = city_coords.get(str(best["Origin"]).strip())
            do_coords = city_coords.get(str(best["Destination"]).strip())
            pu_lat, pu_lon = _coords_to_lat_lon(pu_coords)
            do_lat, do_lon = _coords_to_lat_lon(do_coords)

            fuel = _calc_fuel_cost(miles)
            net = payout - fuel if fuel is not None else None

            rows.append({
                "AssignedDate": assigned_date.isoformat(),
                "TripStartDate": start_date.isoformat(),
                "TripEndDate": end_date.isoformat(),
                "DriverID": driver_id,
                "LoadID": int(best["LoadID"]),
                "LoadSequence": seq,
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "Miles": round(miles, 0),
                "HoursRequired": round(hours_req, 2),
                "Payout": round(payout, 0),
                "FuelCost": round(fuel, 2) if fuel is not None else None,
                "NetProfit": round(net, 2) if net is not None else None,
                "TargetCity": target_city,
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon
            })

            driver_recent_dests.setdefault(driver_id, set()).add(best["Destination"])
            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
            seq += 1

            if remaining_today <= 0:
                day_offset += 1
                remaining_today = float(DAILY_MAX_HOURS)

    return pd.DataFrame(rows)

def update_assignment_history_csv(assigned_date: date) -> pd.DataFrame:
    """
    Append one day into assignment_history.csv with de-dupe.
    Creates the file if missing. Safe even if the existing file is malformed.
    """
    new_df = build_daily_assignment_history(assigned_date)

    if new_df.empty:
        return new_df

    existing = _safe_read_history()
    combined = pd.concat([existing, new_df], ignore_index=True)

    combined = combined.drop_duplicates(
        subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
        keep="first"
    )

    combined.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return combined

# -------------------------
# One-time 2-year backfill
# -------------------------
def backfill_assignment_history_once(years: int = 2) -> pd.DataFrame:
    """
    Backfills history ONLY ONCE.
    Rule:
      - If assignment_history.csv already exists AND already contains data older than the desired start date,
        do nothing.
      - Otherwise, backfill missing days.
    """
    end = date.today()
    start = end - timedelta(days=365 * years)

    existing = _safe_read_history()

    if not existing.empty:
        existing_dates = pd.to_datetime(existing["AssignedDate"], errors="coerce").dropna()
        if not existing_dates.empty:
            min_existing = existing_dates.min().date()
            if min_existing <= start:
                return existing

    all_days = pd.date_range(start=start, end=end, freq="D")
    combined = existing.copy()

    existing_day_set = set()
    if not existing.empty:
        existing_day_set = set(existing["AssignedDate"].dropna().astype(str).tolist())

    for d in all_days:
        day_str = d.date().isoformat()
        if day_str in existing_day_set:
            continue

        day_df = build_daily_assignment_history(d.date(), rng_seed=int(d.strftime("%Y%m%d")))
        if day_df.empty:
            continue

        combined = pd.concat([combined, day_df], ignore_index=True)

    combined = combined.drop_duplicates(
        subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
        keep="first"
    )

    combined.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return combined
def _pick_dispatch_datetime(rng: random.Random, dispatch_day: date) -> datetime:
    """Dispatch time between 6:00 and 10:45 AM."""
    hour = rng.randint(6, 10)
    minute = rng.choice([0, 15, 30, 45])
    return datetime.combine(dispatch_day, time(hour, minute))

def _calc_dwell_hours(rng: random.Random, hours_required: float) -> float:
    """Simple realism: dwell/stops increase with trip duration."""
    if hours_required <= 4:
        return rng.uniform(0.1, 0.4)
    elif hours_required <= 8:
        return rng.uniform(0.25, 0.75)
    else:
        return rng.uniform(0.5, 1.5)
def add_dispatch_delivery_timestamps_to_history(force: bool = False) -> pd.DataFrame:
    """
    Adds DispatchDateTime and DeliveryDateTime to the existing assignment_history.csv.
    Uses simple realism and deterministic randomness based on DriverID/LoadID so it’s stable.
    If the columns already exist and force=False, it does nothing.
    """
    if not ASSIGNMENT_HISTORY_PATH.exists():
        raise FileNotFoundError("assignment_history.csv not found. Generate history first.")

    df = pd.read_csv(ASSIGNMENT_HISTORY_PATH)

    if (not force) and ("DispatchDateTime" in df.columns) and ("DeliveryDateTime" in df.columns):
        return df

    # Ensure required columns exist
    needed = {"AssignedDate", "TripStartDate", "TripEndDate", "DriverID", "LoadID", "HoursRequired"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"assignment_history.csv is missing required columns: {missing}")

    dispatch_list = []
    delivery_list = []

    for _, row in df.iterrows():
        # deterministic RNG per row
        seed = int(row["DriverID"]) * 1_000_003 + int(row["LoadID"])
        rng = random.Random(seed)

        start_date = pd.to_datetime(row["TripStartDate"]).date()
        end_date = pd.to_datetime(row["TripEndDate"]).date()
        hrs = float(row["HoursRequired"]) if pd.notna(row["HoursRequired"]) else 0.0

        # dispatch between 6:00–10:45
        dispatch_dt = _pick_dispatch_datetime(rng, start_date)
        dwell = _calc_dwell_hours(rng, hrs)

        if end_date == start_date:
            delivery_dt = dispatch_dt + timedelta(hours=hrs + dwell)
        else:
            # resume next day 6:00–8:45
            resume_hour = rng.randint(6, 8)
            resume_min = rng.choice([0, 15, 30, 45])
            resume_dt = datetime.combine(end_date, time(resume_hour, resume_min))
            delivery_dt = resume_dt + timedelta(hours=hrs + dwell)

        dispatch_list.append(dispatch_dt.isoformat(sep=" "))
        delivery_list.append(delivery_dt.isoformat(sep=" "))

    df["DispatchDateTime"] = dispatch_list
    df["DeliveryDateTime"] = delivery_list

    df.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return df
