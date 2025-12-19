import streamlit as st
import folium
from streamlit_folium import st_folium
from optimizer_core import build_latest_assignments_df

st.title("Truck Load Optimizer")

# Assign loads (from core logic)
assignments = build_latest_assignments_df()

# Display assignment table
st.subheader("Driver Assignments")
st.dataframe(assignments)

# ------------------------------
# Folium Map with Colored Routes
# ------------------------------
st.subheader("Route Map by Driver")

route_colors = [
    "blue", "green", "red", "orange", "purple",
    "darkred", "cadetblue", "pink", "darkgreen", "black", "lightblue"
]

assigned = assignments.dropna(subset=["PickupCoords", "DropoffCoords"]).reset_index(drop=True)

m = folium.Map(location=[39.8283, -98.5795], zoom_start=4)

for i, row in assigned.iterrows():
    color = route_colors[i % len(route_colors)]
    driver_id = row["DriverID"]

    folium.Marker(
        location=row["PickupCoords"],
        tooltip=f"Driver {driver_id} Pickup",
        icon=folium.Icon(color=color, icon="truck", prefix="fa")
    ).add_to(m)

    folium.Marker(
        location=row["DropoffCoords"],
        tooltip=f"Driver {driver_id} Drop-off",
        icon=folium.Icon(color=color, icon="flag", prefix="fa")
    ).add_to(m)

    folium.PolyLine(
        locations=[row["PickupCoords"], row["DropoffCoords"]],
        color=color,
        tooltip=f"Driver {driver_id} Route",
        weight=4
    ).add_to(m)

st_folium(m, width=725)