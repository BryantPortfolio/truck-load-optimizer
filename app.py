import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from math import radians, sin, cos, sqrt, atan2


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
    a = sin(dlat / 2)**2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 3958.8 * c

# ------------------------------
# Load Assignment Logic
# ------------------------------
def match_loads_by_destination(drivers_df, loads_df, city_coords):
    assignments = []
    available_loads = loads_df.copy()

    for _, driver in drivers_df.iterrows():
        max_miles = driver['AvailableHours'] * 50
        target_coords = city_coords.get(driver['TargetCity'])

        eligible = available_loads[available_loads['Miles'] <= max_miles].copy()

        if not eligible.empty and target_coords:
            eligible['DistanceToTarget'] = eligible['Destination'].map(
                lambda d: haversine(city_coords.get(d, (0, 0)), target_coords)
            )
            best = eligible.sort_values(by=["Payout", "DistanceToTarget"], ascending=[False, True]).iloc[0]

            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": best["LoadID"],
                "LoadMiles": best["Miles"],
                "Payout": best["Payout"],
                "ToTargetMiles": round(best["DistanceToTarget"], 1),
                "PickupCoords": city_coords.get(best["Origin"].strip()),
                "DropoffCoords": city_coords.get(best["Destination"].strip())
            })

            available_loads = available_loads[available_loads["LoadID"] != best["LoadID"]]
        else:
            assignments.append({
                "DriverID": driver["DriverID"],
                "AssignedLoadID": None,
                "LoadMiles": None,
                "Payout": 0,
                "ToTargetMiles": None,
                "PickupCoords": None,
                "DropoffCoords": None
            })

    df = pd.DataFrame(assignments)
    mpg = 6
    fuel_price = 4
    df['FuelCost'] = (df['LoadMiles'] / mpg) * fuel_price
    df['NetProfit'] = df['Payout'] - df['FuelCost']
    return df

# ------------------------------
# Streamlit Dashboard
# ------------------------------
st.title("🚛 Truck Load Optimizer")

# Assign loads
assignments = match_loads_by_destination(drivers, loads, city_coords)

# Display assignment table
st.subheader("📋 Driver Assignments")
st.dataframe(assignments)

# ------------------------------
# Folium Map with Colored Routes
# ------------------------------
st.subheader("📍 Route Map by Driver")

route_colors = [
    "blue", "green", "red", "orange", "purple",
    "darkred", "cadetblue", "pink", "darkgreen", "black", "lightblue"
]

assigned = assignments.dropna(subset=["PickupCoords", "DropoffCoords"]).reset_index(drop=True)

m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

for i, row in assigned.iterrows():
    color = route_colors[i % len(route_colors)]
    driver_id = row['DriverID']

    folium.Marker(
        location=row['PickupCoords'],
        tooltip=f"Driver {driver_id} Pickup",
        icon=folium.Icon(color=color, icon="truck", prefix="fa")
    ).add_to(m)

    folium.Marker(
        location=row['DropoffCoords'],
        tooltip=f"Driver {driver_id} Drop-off",
        icon=folium.Icon(color=color, icon="flag", prefix="fa")
    ).add_to(m)

    folium.PolyLine(
        locations=[row['PickupCoords'], row['DropoffCoords']],
        color=color,
        tooltip=f"Driver {driver_id} Route",
        weight=4
    ).add_to(m)

st_data = st_folium(m, width=725)
