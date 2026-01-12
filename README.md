# 🚛 Truck Load Optimizer - Logistics Analytics Portfolio Project

An interactive dashboard that assigns loads to truck drivers based on location, time, and profit goals - while keeping them on track to reach their desired destination by Friday at 6 PM as often as possible.

---

## 🔍 Overview

The Truck Load Optimizer is an end-to-end logistics analytics portfolio project designed to simulate real-world frieght operations and decision-makng. 
- Match truck drivers with the most profitable loads
- Ensure loads are within their available driving hours
- Prioritize loads that move them closer to where they want to end the week to ensure the driver can spend time home for the weekend
- Visualize assigned routes on an interactive map

The project began as a Python + Streamlit prototype for load assignment logic and evolved into a fully automated Power BI analytics solution, reflecting how operational analytics are built and consumed in enterprise environments.

The solution models multi-load driver assignments, delivery timelines, on-time performance, and route-level profitability across multi-year historical data, with daily automated updates.

---

## Project Goals

- Simulate realistic load assignment decisions under operational constraints
- Measure end-to-end load cycle time and delivery performance
- Evaluate on-time delivery, efficiency, and profitability.
- Present insights through executive-ready Power BI dashboards
- Demonstrate progression from prototype to scalable analytics solution
  
## 🛠 Features

✅ Multi-load driver assignment logic respecting:

  - Daily driving hour limits (<11)
  - Avaliable driver hours
  - Load distance and payout
    
✅ Fuel cost & net profit calculation

✅ Destination proximity bias toward driver target cities

✅ Realistic mileage calculations using Haversine distance

✅ Built with Streamlit (web dashboard) -> transferred to Power BI

  ## Time & Performance Modeling Features 
✅ Dispatch and delivery timestamps generated with realistic constraints

✅ End-to-End cycle time calculations in hours

✅ On-time delivery classfication based on SLA thresholds

✅ Daily and historical performance tracking

  ## Profitability Analysis
✅ Fuel cost modeling based on miles, MPG, and fuel price

✅ Net Profit calculation per load

✅ Route-level and destination-level profit analysis

✅ Top-performing destinations by volume and profit

---

## 📊 Technologies Used

- Python 3.x (Pandas, datetime, automation logic)
  
- Power BI (DAX, KPI modeling, interactive dashboards)
  
- Pandas, NumPy
  
- Folium & Haversine for geospatial logic
  
- Streamlit for the interactive web dashboard
  
- Streamlit-Folium for map embedding
  
- GitHub Actions (daily automation)
  
- GitHub (version control, portfolio hosting)
  
- Excel/CSV (data interchange)

---

## Transformation into a full interactive Dashboard

The Power BI dashboard provides:
- KPI cards for:
  + Average completion time
  + On-time delivery percentage
  + Total loads completed
  + Net profit
- Monthly performance trends
- Geographic route and destination analysis
- Top-10 destination performance breakdowns
- Interactive slicers for date-based analysis

ALL visuals are designed to support operational decision-making

## Automation & Data Pipeline

- Python generates daily laod assignments and historical records
- GitHub Actions automates daily execution and date refresh
- CSV outputs feed directly into Power BI
- Historical data accumulates automatically without duplication

# Repository Structure 
truck-load-optimizer/
│

├── optimizer_core.py        # Core optimization & simulation logic

├── scripts/

│   └── generate_latest_assignments.py

├── assignment_history.csv  # Historical load data (auto-generated)

├── latest_assignments.csv  # Daily snapshot

├── .github/workflows/

│   └── assign.yml          # Automation workflow

├── requirements.txt

└── README.md

## Notes

+ The data is simulated but designed to mirror real logistics constraints

## Screenshots

Screenshots from a Power BI dashboard built using automated Python-generated logistics data.

<img width="665" height="377" alt="Truck Load Optimizer (Full Dash)" src="https://github.com/user-attachments/assets/885767a7-85f3-48c7-9374-41bf4afcf99b" />

<img width="592" height="52" alt="Truck Load Optimizer (KPIs)" src="https://github.com/user-attachments/assets/dfd18128-bd25-45c5-a17e-cf14cd9151f6" />

<img width="368" height="137" alt="Truck Load Optimizer (Monthly View)" src="https://github.com/user-attachments/assets/e0a562e5-9b51-4006-aeca-512a9b05a695" />

## Contact 
Daijah Bryant
Data Analyst
LinkedIn -> https://www.linkedin.com/in/daijah-d/
