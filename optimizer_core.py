import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from datetime import date, timedelta
from pathlib import Path

# -------------------------
# Config
# -------------------------
AVG_SPEED_MPH = 50
MAX_DAILY_DRIVE_HOURS = 11
HISTORY_PATH = Path("assignment_history.csv")

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

# -----------------------
# Helpers
# -----------------------
def haversine(coord1, coord2):
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    rlat1, rlon1, rlat2, rlon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 3958.8 * c

def miles_to_hours(miles: float) -> float:
    if miles is None or pd.isna(miles):
        return None
    return round(float(miles) / AVG_SPEED_MPH, 2)

def coords_lat_lon(city: str):
    c = city_coords.get(city)
    if not c:
        return (None, None)
    return (c[0], c[1])

# -----------------------
# Single-load-per-driver (today snapshot)
# -----------------------
def match_loads_by_destination(drivers_df, loads_df, city_coords_dict):
    assignments = []
    available_loads = loads_df.copy()

    for _, driver in drivers_df.iterrows():
        max_miles = driver["AvailableHours"] * AVG_SPEED_MPH
        target_coords = city_coords_dict.get(driver["TargetCity"])

        eligible = available_loads[available_loads["Miles"] <= max_miles].copy()

        if not eligible.empty and target_coords:
            eligible["DistanceToTarget"] = eligible["Destination"].map(
                lambda d: haversine(city_coords_dict.get(d, (0, 0)), target_coords)
            )
            best = eligible.sort_values(
                by=["Payout", "DistanceToTarget"], ascending=[False, True]
            ).iloc[0]

            pick_lat, pick_lon = coords_lat_lon(best["Origin"].strip())
            drop_lat, drop_lon = coords_lat_lon(best["Destination"].strip())

            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": int(best["LoadID"]),
                "OriginCity": best["Origin"],
                "DestinationCity": best["Destination"],
                "LoadMiles": float(best["Miles"]),
                "DriveHours": miles_to_hours(best["Miles"]),
                "Payout": float(best["Payout"]),
                "ToTargetMiles": round(float(best["DistanceToTarget"]), 1),
                "PickupLat": pick_lat,
                "PickupLon": pick_lon,
                "DropoffLat": drop_lat,
                "DropoffLon": drop_lon,
            })

            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
        else:
            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": None,
                "OriginCity": None,
                "DestinationCity": None,
                "LoadMiles": None,
                "DriveHours": None,
                "Payout": 0.0,
                "ToTargetMiles": None,
                "PickupLat": None,
                "PickupLon": None,
                "DropoffLat": None,
                "DropoffLon": None,
            })

    df = pd.DataFrame(assignments)

    mpg = 6
    fuel_price = 4
    df["FuelCost"] = (df["LoadMiles"] / mpg) * fuel_price
    df["NetProfit"] = df["Payout"] - df["FuelCost"]
    return df

def build_latest_assignments_df():
    return match_loads_by_destination(drivers, loads, city_coords)

# -----------------------
# Multi-load-per-driver per day (History)
# -----------------------
def build_daily_assignment_history(
    assigned_date: date,
    completion_lag_days: int = 1
) -> pd.DataFrame:
    """
    Creates many assignments per driver for a single day while enforcing 11-hour daily drive limit.
    Strategy: for each driver, repeatedly pick the best eligible load until hours are used up.
    """

    records = []
    remaining = loads.copy()

    for _, driver in drivers.iterrows():
        hours_used = 0.0

        while True:
            # Filter loads that still fit in the remaining hours
            remaining["DriveHours"] = remaining["Miles"].apply(miles_to_hours)
            eligible = remaining[(remaining["DriveHours"].notna()) &
                                ((hours_used + remaining["DriveHours"]) <= MAX_DAILY_DRIVE_HOURS)].copy()

            if eligible.empty:
                break

            target_coords = city_coords.get(driver["TargetCity"])
            if target_coords:
                eligible["DistanceToTarget"] = eligible["Destination"].map(
                    lambda d: haversine(city_coords.get(d, (0, 0)), target_coords)
                )
            else:
                eligible["DistanceToTarget"] = 999999

            # Choose the best load (high payout, closer to target)
            best = eligible.sort_values(
                by=["Payout", "DistanceToTarget"],
                ascending=[False, True]
            ).iloc[0]

            pick_lat, pick_lon = coords_lat_lon(best["Origin"].strip())
            drop_lat, drop_lon = coords_lat_lon(best["Destination"].strip())

            drive_hours = float(best["DriveHours"])
            hours_used += drive_hours

            payout = float(best["Payout"])
            miles = float(best["Miles"])
            mpg = 6
            fuel_price = 4
            fuel_cost = (miles / mpg) * fuel_price
            net_profit = payout - fuel_cost

            records.append({
                "AssignedDate": assigned_date.isoformat(),
                "CompletedDate": (assigned_date + timedelta(days=completion_lag_days)).isoformat(),
                "DriverID": int(driver["DriverID"]),
                "LoadID": int(best["LoadID"]),
                "OriginCity": best["Origin"],
                "DestinationCity": best["Destination"],
                "Miles": miles,
                "DriveHours": drive_hours,
                "Payout": payout,
                "FuelCost": fuel_cost,
                "NetProfit": net_profit,
                "PickupLat": pick_lat,
                "PickupLon": pick_lon,
                "DropoffLat": drop_lat,
                "DropoffLon": drop_lon,
                "DailyHoursUsed": round(hours_used, 2),
                "DailyHoursRemaining": round(MAX_DAILY_DRIVE_HOURS - hours_used, 2),
            })

            # Remove assigned load
            remaining = remaining[remaining["LoadID"] != best["LoadID"]]

    return pd.DataFrame(records)

def update_assignment_history_csv(assigned_date: date):
    """
    Appends a new day's history to assignment_history.csv, avoiding duplicates for the same day.
    """
    new_df = build_daily_assignment_history(assigned_date=assigned_date)

    if HISTORY_PATH.exists():
        old = pd.read_csv(HISTORY_PATH)
        # avoid duplicating same day's loads if rerun
        old = old[old["AssignedDate"] != assigned_date.isoformat()]
        combined = pd.concat([old, new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(HISTORY_PATH, index=False)
    return combined
