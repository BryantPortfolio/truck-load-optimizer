import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from datetime import date, timedelta
from pathlib import Path
from pandas.errors import ParserError

# -------------------------
# Constants (easy to tweak)
# -------------------------
AVG_MPH = 50                    # consistent with your existing AvailableHours*50 logic
DAILY_MAX_HOURS = 11            # 11-hour drive-time rule
MPG = 6
FUEL_PRICE = 4.0

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


# ------------------------------
# Sample Load Data
# ------------------------------
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


# ------------------------------
# City Coordinates
# ------------------------------
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
# Haversine Distance Function
# ------------------------------
def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 3958.8 * c


def _coords_to_lat_lon(coords):
    if not coords or not isinstance(coords, (list, tuple)) or len(coords) != 2:
        return None, None
    return coords[0], coords[1]


def _calc_fuel_cost(miles):
    if miles is None or pd.isna(miles):
        return None
    return (float(miles) / MPG) * float(FUEL_PRICE)


def _calc_hours_required(miles):
    if miles is None or pd.isna(miles):
        return None
    return float(miles) / float(AVG_MPH)


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
            net_profit = float(best["Payout"]) - fuel_cost if fuel_cost is not None else None

            assignments.append({
                "DriverID": int(driver["DriverID"]),
                "AssignedLoadID": int(best["LoadID"]),
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "LoadMiles": float(best["Miles"]),
                "Payout": float(best["Payout"]),
                "ToTargetMiles": round(float(best["DistanceToTarget"]), 1),
                # Keep coords for Streamlit map (optional)
                "PickupCoords": pickup_coords,
                "DropoffCoords": dropoff_coords,
                # Power BI-friendly numeric coords
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
                "Payout": 0.0,
                "ToTargetMiles": None,
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
    """Single entry point for GitHub Actions / scripts."""
    return match_loads_by_destination(drivers, loads, city_coords)


# ------------------------------
# NEW: Multi-load daily history using 11-hour rule
# ------------------------------
def build_daily_assignment_history(assigned_date: date) -> pd.DataFrame:
    """
    Per-load history for one assigned_date where each driver can take multiple loads per day
    up to DAILY_MAX_HOURS. If a load doesn't fit within remaining hours today, assume
    it completes next day (your rule).
    """
    history_rows = []
    available_loads = loads.copy()

    for _, driver in drivers.iterrows():
        remaining_hours_today = float(DAILY_MAX_HOURS)
        day_offset = 0
        seq = 1

        # Driver-level cap across planning horizon using AvailableHours
        driver_total_remaining_hours = float(driver["AvailableHours"])

        while driver_total_remaining_hours > 0 and not available_loads.empty:
            tmp = available_loads.copy()
            tmp["HoursRequired"] = tmp["Miles"].apply(_calc_hours_required)

            eligible = tmp[tmp["HoursRequired"] <= driver_total_remaining_hours].copy()
            if eligible.empty:
                break

            # Prefer max payout/hour (efficiency), then payout
            eligible["PayoutPerHour"] = eligible["Payout"] / eligible["HoursRequired"]
            best = eligible.sort_values(
                by=["PayoutPerHour", "Payout"],
                ascending=[False, False]
            ).iloc[0]

            hours_req = float(best["HoursRequired"])
            miles = float(best["Miles"])
            payout = float(best["Payout"])

            trip_start = assigned_date + timedelta(days=day_offset)

            # Your completion assumption
            if hours_req <= remaining_hours_today:
                trip_end = trip_start
                remaining_hours_today -= hours_req
            else:
                trip_end = trip_start + timedelta(days=1)
                spill = hours_req - remaining_hours_today
                day_offset += 1
                remaining_hours_today = max(float(DAILY_MAX_HOURS) - spill, 0.0)

            driver_total_remaining_hours -= hours_req

            pickup_coords = city_coords.get(best["Origin"].strip())
            dropoff_coords = city_coords.get(best["Destination"].strip())
            pu_lat, pu_lon = _coords_to_lat_lon(pickup_coords)
            do_lat, do_lon = _coords_to_lat_lon(dropoff_coords)

            fuel_cost = _calc_fuel_cost(miles)
            net_profit = payout - fuel_cost if fuel_cost is not None else None

            history_rows.append({
                "AssignedDate": assigned_date.isoformat(),
                "TripStartDate": trip_start.isoformat(),
                "TripEndDate": trip_end.isoformat(),
                "DriverID": int(driver["DriverID"]),
                "LoadID": int(best["LoadID"]),
                "LoadSequence": int(seq),
                "Origin": best["Origin"],
                "Destination": best["Destination"],
                "Miles": round(miles, 2),
                "HoursRequired": round(hours_req, 2),
                "Payout": round(payout, 2),
                "FuelCost": round(fuel_cost, 2) if fuel_cost is not None else None,
                "NetProfit": round(net_profit, 2) if net_profit is not None else None,
                "PickupLat": pu_lat,
                "PickupLon": pu_lon,
                "DropoffLat": do_lat,
                "DropoffLon": do_lon
            })

            # Remove used load
            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
            seq += 1

            # If they used all hours today, go to next day
            if remaining_hours_today <= 0:
                day_offset += 1
                remaining_hours_today = float(DAILY_MAX_HOURS)

    return pd.DataFrame(history_rows)


def _safe_read_assignment_history() -> pd.DataFrame:
    """
    Read assignment_history.csv if valid; otherwise return empty DF.
    Prevents GitHub Actions from crashing on malformed CSV.
    """
    if not ASSIGNMENT_HISTORY_PATH.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(ASSIGNMENT_HISTORY_PATH)
        # If someone accidentally created a 1-column file, treat as invalid
        if df.shape[1] <= 1:
            return pd.DataFrame()
        return df
    except (ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def update_assignment_history_csv(assigned_date: date) -> pd.DataFrame:
    """
    Append today's daily assignment history to assignment_history.csv.
    Avoid duplicates for the same (AssignedDate, DriverID, LoadID, LoadSequence).
    If the existing file is malformed, it will be rebuilt.
    """
    new_df = build_daily_assignment_history(assigned_date)

    if new_df.empty:
        # Still ensure a file exists for Power BI if you want
        if not ASSIGNMENT_HISTORY_PATH.exists():
            new_df.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
        return new_df

    existing = _safe_read_assignment_history()

    if existing.empty:
        combined = new_df
    else:
        combined = pd.concat([existing, new_df], ignore_index=True)

        combined = combined.drop_duplicates(
            subset=["AssignedDate", "DriverID", "LoadID", "LoadSequence"],
            keep="first"
        )

    combined.to_csv(ASSIGNMENT_HISTORY_PATH, index=False)
    return combined
