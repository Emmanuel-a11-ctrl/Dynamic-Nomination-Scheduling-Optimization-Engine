# ============================================================
# DYNAMIC NOMINATION & SCHEDULING OPTIMIZATION ENGINE
# Complete CNG Downstream Commercial Module with Interactive Dashboard
# Version: 2.0
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import math
import random
import json
import io
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

# OR-Tools for MILP (if available)
OR_TOOLS_AVAILABLE = False
try:
    from ortools.linear_solver import pywraplp
    OR_TOOLS_AVAILABLE = True
except ImportError:
    pass

# ============================================================
# UNIT CONVERSION CONSTANTS
# ============================================================
KG_TO_MMBTU = 0.053
MMBTU_TO_KG = 1 / KG_TO_MMBTU

def kg_to_mmbtu(kg: float) -> float:
    return kg * KG_TO_MMBTU

def mmbtu_to_kg(mmbtu: float) -> float:
    return mmbtu * MMBTU_TO_KG

# ============================================================
# DATA CLASSES
# ============================================================
@dataclass
class Customer:
    id: str
    name: str
    segment: str
    lat: float
    lon: float
    hub_assignment: str
    flexibility: str
    demurrage_history: int = 0
    price_per_mmbtu: float = 0.0 # New field for customer-specific price

@dataclass
class Nomination:
    customer_id: str
    date: datetime
    volume_mmbtu: float
    pressure_bar: int
    preferred_window_start: datetime
    preferred_window_end: datetime
    flexibility: str
    hub_assignment: str
    submitted_at: datetime = field(default_factory=datetime.now)

@dataclass
class Trailer:
    id: str
    current_location: str
    status: str
    pressure_bar: int
    capacity_kg: float
    assigned_customer_id: Optional[str] = None
    expected_return_time: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class HubInventory:
    hub_name: str
    skids_full: int
    skids_empty: int
    avg_pressure_bar: float
    utilization_pct: float
    last_updated: datetime = field(default_factory=datetime.now)

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def travel_time_hrs(lat1, lon1, lat2, lon2, avg_speed_kmh=45):
    dist = haversine(lat1, lon1, lat2, lon2)
    traffic_factor = random.uniform(0.85, 1.25)
    return (dist / avg_speed_kmh) * traffic_factor

# ============================================================
# CONFIGURATION
# ============================================================
CONFIG = {
    "hubs": {
        "Karongi (Mother)": {"lat": -2.016, "lon": 29.350, "type": "mother"},
        "Kigali Nyanza (Auto)": {"lat": -1.970, "lon": 30.104, "type": "auto_hub"},
        "Muhanga (Cooking)": {"lat": -2.082, "lon": 29.753, "type": "cooking_hub"}
    },
    "fleet": {
        "total_skids": 85,
        "trailer_capacity_kg": 5000,
    },
    "pricing": {
        "base_price_per_mmbtu": 12.50,
        "route_flex_discount": 0.10,
        "rigid_surcharge": 0.15,
        "demurrage_rate_per_hour": 75.00,
        "demurrage_grace_hours": 4,
        "operating_cost_per_km": 2.00,
    },
    "travel": {"avg_speed_kmh": 45},
    "units": {"preferred": "MMBTU"}
}

# ============================================================
# SAMPLE DATA GENERATION
# ============================================================
def generate_sample_customers(num_customers: int = 10) -> List[Customer]:
    random.seed(42)
    np.random.seed(42)
    customers = []
    segments = ["Auto Fleet", "Cooking Franchise", "Industrial Boiler"]
    hub_map = {
        "Auto Fleet": "Kigali Nyanza (Auto)",
        "Cooking Franchise": "Muhanga (Cooking)",
        "Industrial Boiler": "Kigali Nyanza (Auto)"
    }
    locations = [
        (-1.95, 30.10), (-2.08, 29.75), (-2.30, 29.60), (-1.68, 29.35), (-2.60, 29.80),
        (-1.85, 30.20), (-2.40, 29.50), (-1.75, 30.05), (-2.15, 29.90), (-2.25, 29.70)
    ]
    for i in range(num_customers):
        seg = random.choice(segments)
        lat, lon = locations[i % len(locations)]
        lat += random.uniform(-0.05, 0.05)
        lon += random.uniform(-0.05, 0.05)
        hub = hub_map.get(seg, "Muhanga (Cooking)")
        flex = random.choice(["Flex", "Rigid"])
        demurrage = random.randint(0, 3)

        # Generate a price for the customer, varying around the base price
        base_price = CONFIG["pricing"]["base_price_per_mmbtu"]
        customer_price = round(random.uniform(base_price * 0.9, base_price * 1.1), 2)

        customers.append(Customer(
            id=f"CUST-{i+1:03d}",
            name=f"{seg} {i+1}",
            segment=seg,
            lat=lat, lon=lon,
            hub_assignment=hub,
            flexibility=flex,
            demurrage_history=demurrage,
            price_per_mmbtu=customer_price # Assign the generated price
        ))
    return customers

def generate_nominations(customers: List[Customer], date: datetime) -> List[Nomination]:
    nominations = []
    for cust in customers:
        if cust.segment == "Auto Fleet":
            vol_mmbtu = random.uniform(2.0, 8.0)
            pressure = 250
        elif cust.segment == "Industrial Boiler":
            vol_mmbtu = random.uniform(5.0, 20.0)
            pressure = random.choice([100, 250])
        else:
            vol_mmbtu = random.uniform(0.5, 4.0)
            pressure = 20
        start_hour = random.randint(6, 20)
        end_hour = start_hour + random.randint(2, 6)
        window_start = datetime.combine(date, datetime.min.time()) + timedelta(hours=start_hour)
        window_end = datetime.combine(date, datetime.min.time()) + timedelta(hours=end_hour)
        nominations.append(Nomination(
            customer_id=cust.id,
            date=date,
            volume_mmbtu=vol_mmbtu,
            pressure_bar=pressure,
            preferred_window_start=window_start,
            preferred_window_end=window_end,
            flexibility=cust.flexibility,
            hub_assignment=cust.hub_assignment
        ))
    return nominations

def generate_trailers(num_trailers: int = 8) -> List[Trailer]:
    hubs = ["Karongi (Mother)", "Kigali Nyanza (Auto)", "Muhanga (Cooking)"]
    trailers = []
    for i in range(num_trailers):
        status = random.choice(["Idle", "Idle", "Idle", "Returning"])
        location = random.choice(hubs)
        trailers.append(Trailer(
            id=f"TRL-{i+1:03d}",
            current_location=location,
            status=status,
            pressure_bar=250 if random.random() > 0.2 else 150,
            capacity_kg=CONFIG["fleet"]["trailer_capacity_kg"],
            assigned_customer_id=None,
            expected_return_time=datetime.now() + timedelta(hours=random.randint(1, 6)) if status == "Returning" else None
        ))
    return trailers

def get_hub_inventory():
    return [
        HubInventory("Karongi (Mother)", 43, 5, 250, 78),
        HubInventory("Kigali Nyanza (Auto)", 12, 8, 245, 65),
        HubInventory("Muhanga (Cooking)", 30, 2, 250, 42)
    ]

# ============================================================
# OPTIMIZATION ENGINE (MILP + Greedy)
# ============================================================
class NominationOptimizationEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.hubs = config["hubs"]
        self.trailer_capacity_kg = config["fleet"]["trailer_capacity_kg"]
        self.base_price_mmbtu = config["pricing"]["base_price_per_mmbtu"]
        self.demurrage_rate = config["pricing"]["demurrage_rate_per_hour"]
        self.grace_hours = config["pricing"]["demurrage_grace_hours"]
        self.op_cost_per_km = config["pricing"]["operating_cost_per_km"]
        self.avg_speed = config["travel"]["avg_speed_kmh"]

    def optimize(self, nominations: List[Nomination], customers: List[Customer],
                 trailers: List[Trailer], hub_inv: List[HubInventory]) -> Dict:
        nom_df = self._nominations_to_df(nominations, customers)
        trailer_df = self._trailers_to_df(trailers)
        hub_df = self._hubs_to_df()
        if OR_TOOLS_AVAILABLE:
            try:
                return self._run_milp(nom_df, trailer_df, hub_df)
            except Exception:
                return self._run_greedy(nom_df, trailer_df, hub_df)
        else:
            return self._run_greedy(nom_df, trailer_df, hub_df)

    def _nominations_to_df(self, nominations, customers):
        cust_map = {c.id: c for c in customers}
        data = []
        for n in nominations:
            c = cust_map[n.customer_id]
            # Use the customer's specific price_per_mmbtu
            customer_base_price = c.price_per_mmbtu
            # Apply flexibility discount/surcharge to the customer's base price
            if n.flexibility == "Flex":
                price = customer_base_price * (1 - self.config["pricing"]["route_flex_discount"])
            else: # Rigid
                price = customer_base_price * (1 + self.config["pricing"]["rigid_surcharge"])

            data.append({
                'customer_id': n.customer_id,
                'name': c.name,
                'segment': c.segment,
                'hub_assignment': c.hub_assignment,
                'lat': c.lat, 'lon': c.lon,
                'volume_mmbtu': n.volume_mmbtu,
                'volume_kg': n.volume_mmbtu * MMBTU_TO_KG,
                'pressure_bar': n.pressure_bar,
                'window_start': n.preferred_window_start,
                'window_end': n.preferred_window_end,
                'flexibility': n.flexibility,
                'demurrage_history': c.demurrage_history,
                'revenue': n.volume_mmbtu * price, # Calculate revenue with specific price
                'customer_price_per_mmbtu': c.price_per_mmbtu # Add for reference
            })
        return pd.DataFrame(data)

    def _trailers_to_df(self, trailers):
        data = [{
            'id': t.id,
            'location': t.current_location,
            'status': t.status,
            'pressure': t.pressure_bar,
            'capacity_kg': t.capacity_kg,
            'assigned_customer': t.assigned_customer_id,
            'return_time': t.expected_return_time
        } for t in trailers]
        return pd.DataFrame(data)

    def _hubs_to_df(self):
        hubs = self.config["hubs"]
        data = [{'name': name, 'lat': info['lat'], 'lon': info['lon'], 'type': info['type']}
                for name, info in hubs.items()]
        return pd.DataFrame(data)

    def _run_milp(self, nom_df, trailer_df, hub_df):
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return self._run_greedy(nom_df, trailer_df, hub_df)
        num_customers = len(nom_df)
        num_trailers = len(trailer_df)
        x = {}
        for i in range(num_trailers):
            for j in range(num_customers):
                x[i, j] = solver.IntVar(0, 1, f'x_{i}_{j}')
        for j in range(num_customers):
            solver.Add(solver.Sum([x[i, j] for i in range(num_trailers)]) == 1)
        for i in range(num_trailers):
            solver.Add(solver.Sum([x[i, j] for j in range(num_customers)]) <= 2)
        objective = solver.Objective()
        for i in range(num_trailers):
            for j in range(num_customers):
                objective.SetCoefficient(x[i, j], nom_df.iloc[j]['revenue'])
        objective.SetMaximization()
        status = solver.Solve()
        if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            return self._run_greedy(nom_df, trailer_df, hub_df)
        routes = []
        total_rev = 0
        total_empty_km = 0
        total_volume_mmbtu_delivered = 0 # Changed name for clarity
        assigned = set()
        for i in range(num_trailers):
            served_noms_indices = [] # Indices of nominations served by this trailer
            for j in range(num_customers):
                if x[i, j].solution_value() > 0.5:
                    served_noms_indices.append(j)
            if served_noms_indices:
                custs_served_by_trailer = nom_df.iloc[served_noms_indices]
                route_names = custs_served_by_trailer['name'].tolist()
                route_str = " → ".join(route_names)
                empty_km = 0
                if len(served_noms_indices) == 2:
                    c1 = custs_served_by_trailer.iloc[0]; c2 = custs_served_by_trailer.iloc[1]
                    empty_km = haversine(c1['lat'], c1['lon'], c2['lat'], c2['lon'])
                    route_str += f" (Cascade: {empty_km:.1f}km)"
                else:
                    # Assuming single customer route, calculate distance to/from hub
                    hub = custs_served_by_trailer.iloc[0]['hub_assignment']
                    hub_info = self.hubs[hub]
                    empty_km = haversine(custs_served_by_trailer.iloc[0]['lat'], custs_served_by_trailer.iloc[0]['lon'],
                                        hub_info['lat'], hub_info['lon']) * 0.5 # Half of round trip
                total_empty_km += empty_km
                total_rev += custs_served_by_trailer['revenue'].sum()
                total_volume_mmbtu_delivered += custs_served_by_trailer['volume_mmbtu'].sum() # Sum volumes
                assigned.update(custs_served_by_trailer['customer_id'].tolist())
                routes.append({
                    "trailer": trailer_df.iloc[i]['id'],
                    "route": route_str,
                    "status": "✅ Scheduled",
                    "customers": custs_served_by_trailer['customer_id'].tolist()
                })

        demurrage = nom_df['demurrage_history'].sum() * self.demurrage_rate * 0.5
        empty_cost = total_empty_km * self.op_cost_per_km
        net_margin = total_rev - empty_cost - demurrage
        return {
            "status": "Success (MILP)",
            "total_trips": len(routes),
            "total_volume_mmbtu_delivered": total_volume_mmbtu_delivered, # Changed key
            "total_revenue_usd": total_rev,
            "total_empty_km": total_empty_km,
            "empty_cost_usd": empty_cost,
            "demurrage_penalty_usd": demurrage,
            "net_margin_usd": net_margin,
            "routes": routes,
            "fulfillment_rate": (len(assigned) / num_customers) * 100,
            "is_optimal": status == pywraplp.Solver.OPTIMAL
        }

    def _run_greedy(self, nom_df, trailer_df, hub_df):
        sorted_noms = nom_df.sort_values('window_start')
        routes = []
        total_rev = 0
        total_empty_km = 0
        total_volume_mmbtu_delivered = 0 # Changed name for clarity
        assigned = set()
        available = trailer_df[trailer_df['status'].isin(['Idle', 'Returning'])].copy()
        if len(available) == 0:
            available = trailer_df.copy()
        available = available.sample(frac=1).reset_index(drop=True)

        for idx, row in sorted_noms.iterrows():
            if row['customer_id'] in assigned or len(available) == 0:
                continue

            trailer = available.iloc[0]
            available = available.iloc[1:].reset_index(drop=True)

            assigned.add(row['customer_id'])
            route_customers = [row] # A list of dictionaries/series for customers in this route
            empty_km = 0

            # Attempt to find a second customer for cascade delivery
            for idx2, row2 in sorted_noms.iterrows():
                if row2['customer_id'] in assigned:
                    continue
                # Only consider flexible customers for cascading to simplify greedy logic
                if row2['flexibility'] == "Flex" and row2['hub_assignment'] == row['hub_assignment']:
                    dist = haversine(row['lat'], row['lon'], row2['lat'], row2['lon'])
                    if dist < 25: # Arbitrary distance threshold for cascading
                        assigned.add(row2['customer_id'])
                        route_customers.append(row2)
                        empty_km += dist
                        break # Found a cascade, move to next trailer

            route_names = [c['name'] for c in route_customers]
            route_str = " → ".join(route_names)

            current_route_volume_mmbtu = sum(c['volume_mmbtu'] for c in route_customers)
            current_route_revenue = sum(c['revenue'] for c in route_customers)

            if len(route_customers) > 1:
                route_str += f" (Cascade: {empty_km:.1f}km)"
            else:
                # If only one customer, calculate empty travel to/from hub
                hub = row['hub_assignment']
                hub_info = self.hubs[hub]
                empty_km += haversine(row['lat'], row['lon'], hub_info['lat'], hub_info['lon']) * 0.5

            total_empty_km += empty_km
            total_rev += current_route_revenue
            total_volume_mmbtu_delivered += current_route_volume_mmbtu # Sum volumes

            routes.append({
                "trailer": trailer['id'],
                "route": route_str,
                "status": "✅ Scheduled",
                "customers": [c['customer_id'] for c in route_customers]
            })

        demurrage = nom_df['demurrage_history'].sum() * self.demurrage_rate * 0.5
        empty_cost = total_empty_km * self.op_cost_per_km
        net_margin = total_rev - empty_cost - demurrage

        return {
            "status": "Success (Greedy)",
            "total_trips": len(routes),
            "total_volume_mmbtu_delivered": total_volume_mmbtu_delivered, # Changed key
            "total_revenue_usd": total_rev,
            "total_empty_km": total_empty_km,
            "empty_cost_usd": empty_cost,
            "demurrage_penalty_usd": demurrage,
            "net_margin_usd": net_margin,
            "routes": routes,
            "fulfillment_rate": (len(assigned) / len(nom_df)) * 100,
            "is_optimal": False
        }

# ============================================================
# INVOICING MODULE
# ============================================================
class InvoiceGenerator:
    @staticmethod
    def generate_invoice(customer_id: str, planned_mmbtu: float, actual_mmbtu: float,
                         price_per_mmbtu: float, demurrage_hours: float = 0) -> Dict:
        base_amount = actual_mmbtu * price_per_mmbtu
        demurrage_charge = max(0, demurrage_hours - CONFIG["pricing"]["demurrage_grace_hours"]) * CONFIG["pricing"]["demurrage_rate_per_hour"]
        under_penalty = 0
        if actual_mmbtu < 0.9 * planned_mmbtu:
            under_penalty = (planned_mmbtu - actual_mmbtu) * price_per_mmbtu * 0.05
        total = base_amount + demurrage_charge + under_penalty
        return {
            'customer_id': customer_id,
            'planned_mmbtu': planned_mmbtu,
            'actual_mmbtu': actual_mmbtu,
            'price_per_mmbtu': price_per_mmbtu,
            'base_amount': base_amount,
            'demurrage_charge': demurrage_charge,
            'under_nomination_penalty': under_penalty,
            'total_amount': total,
            'due_date': datetime.now() + timedelta(days=30),
            'invoice_id': f"INV-{customer_id}-{datetime.now().strftime('%Y%m%d')}"
        }

# ============================================================
# STREAMLIT DASHBOARD (MAIN)
# ============================================================
def main_dashboard():
    st.set_page_config(page_title="CNG Nomination Engine", page_icon="⛽", layout="wide")
    st.title("⛽ Dynamic Nomination & Scheduling Engine")
    st.markdown("### Commercial Optimization for CNG Virtual Pipeline")
    st.markdown("---")

    # Sidebar controls
    st.sidebar.header("⚙️ Controls")
    num_customers = st.sidebar.slider("Number of Customers", 5, 25, 10, 1)
    num_trailers = st.sidebar.slider("Number of Trailers", 3, 15, 8, 1)
    date = st.sidebar.date_input("Nomination Date", datetime.now().date() + timedelta(days=1))
    opt_mode = st.sidebar.selectbox("Optimization Mode", ["Balanced", "Profit Maximization", "Time Minimization"])
    run_button = st.sidebar.button("Run Optimization", type="primary")

    # Initialize session state
    if 'customers' not in st.session_state:
        st.session_state.customers = generate_sample_customers(num_customers)
        st.session_state.nominations = generate_nominations(st.session_state.customers, date)
        st.session_state.trailers = generate_trailers(num_trailers)
        st.session_state.engine = NominationOptimizationEngine(CONFIG)
        st.session_state.result = None
        st.session_state.invoices = None
        st.session_state.actual_deliveries = None

    # Regenerate if sliders change
    if st.sidebar.button("Reset Data"):
        st.session_state.customers = generate_sample_customers(num_customers)
        st.session_state.nominations = generate_nominations(st.session_state.customers, date)
        st.session_state.trailers = generate_trailers(num_trailers)
        st.session_state.result = None
        st.session_state.invoices = None
        st.session_state.actual_deliveries = None
        st.rerun()

    # Run optimization
    if run_button:
        with st.spinner("Optimizing..."):
            st.session_state.result = st.session_state.engine.optimize(
                st.session_state.nominations,
                st.session_state.customers,
                st.session_state.trailers,
                get_hub_inventory()
            )
            # Simulate actual deliveries
            actual = {}
            for n in st.session_state.nominations:
                variation = np.random.uniform(0.85, 1.15)
                actual[n.customer_id] = n.volume_mmbtu * variation
            st.session_state.actual_deliveries = actual
            # Generate invoices
            invoices = []
            cust_map = {c.id: c for c in st.session_state.customers} # Map to get customer details
            for n in st.session_state.nominations:
                demurrage_hours = random.randint(0, 6)
                customer = cust_map[n.customer_id] # Get the specific customer object
                inv = InvoiceGenerator.generate_invoice(
                    n.customer_id,
                    n.volume_mmbtu,
                    actual[n.customer_id],
                    customer.price_per_mmbtu, # Use customer's specific price
                    demurrage_hours
                )
                invoices.append(inv)
            st.session_state.invoices = invoices
        st.success("Optimization complete!")

    # Define a function to simulate historical data for a customer
    def _generate_customer_history_df(customer: Customer) -> pd.DataFrame:
        dates = [datetime.now() - timedelta(days=i) for i in range(30, 0, -1)]
        history_data = []
        for d in dates:
            planned_vol = customer.price_per_mmbtu * random.uniform(5, 20) # Varies by customer price for simulation
            actual_vol = planned_vol * random.uniform(0.8, 1.2)
            demurrage = random.randint(0, 2) # Simulate 0-2 hours of demurrage
            price = customer.price_per_mmbtu
            rev = actual_vol * price
            penalty = 0
            if actual_vol < 0.9 * planned_vol:
                penalty = (planned_vol - actual_vol) * price * 0.05

            history_data.append({
                'date': d,
                'planned_mmbtu': planned_vol,
                'actual_mmbtu': actual_vol,
                'revenue_usd': rev,
                'demurrage_charge_usd': max(0, demurrage - CONFIG["pricing"]["demurrage_grace_hours"]) * CONFIG["pricing"]["demurrage_rate_per_hour"],
                'under_nomination_penalty_usd': penalty
            })
        df = pd.DataFrame(history_data)
        df['date'] = pd.to_datetime(df['date'])
        return df

    # Helper function for KPI comparison
    def _compare_kpis(base_result: Dict, simulated_result: Dict) -> pd.DataFrame:
        kpis_to_compare = [
            ("Net Margin", "net_margin_usd", "$", 0),
            ("Total Revenue", "total_revenue_usd", "$", 0),
            ("Total Volume Delivered", "total_volume_mmbtu_delivered", " MMBTU", 1),
            ("Total Trips", "total_trips", "", 0),
            ("Fulfillment Rate", "fulfillment_rate", "%", 1)
        ]
        comparison_data = []
        for kpi_name, key, unit, decimals in kpis_to_compare:
            base_val = base_result.get(key, 0)
            sim_val = simulated_result.get(key, 0)
            percentage_change = ((sim_val - base_val) / base_val * 100) if base_val != 0 else float('inf')

            comparison_data.append({
                "KPI": kpi_name,
                "Base Value": f"{base_val:,.{decimals}f}{unit}",
                "Simulated Value": f"{sim_val:,.{decimals}f}{unit}",
                "% Change": f"{percentage_change:,.1f}%"
            })
        return pd.DataFrame(comparison_data)


    # Display results if available
    if st.session_state.result is not None:
        res = st.session_state.result
        # KPIs
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Trips", res['total_trips'])
        col2.metric("Revenue", f"${res['total_revenue_usd']:,.0f}")
        col3.metric("Empty KM", f"{res['total_empty_km']:.1f} km")
        col4.metric("Net Margin", f"${res['net_margin_usd']:,.0f}")
        col5.metric("Fulfillment", f"{res['fulfillment_rate']:.1f}%")

        tabs = st.tabs(["Optimization Results", "Commercial Insights", "Invoices", "Predictive Analytics"])

        with tabs[0]: # Optimization Results
            # Map
            st.subheader("🗺️ Geospatial View with Optimized Routes")
            import plotly.graph_objects as go
            fig = go.Figure()
            hubs = CONFIG["hubs"]
            colors = {"mother":"red","auto_hub":"blue","cooking_hub":"green"}
            sizes = {"mother":25,"auto_hub":30,"cooking_hub":30}
            for name, info in hubs.items():
                fig.add_trace(go.Scattermapbox(
                    lat=[info['lat']], lon=[info['lon']],
                    mode='markers+text',
                    marker=dict(size=sizes[info['type']], color=colors[info['type']]),
                    text=[name], textposition="top center", name=name, showlegend=False
                ))
            # Customers
            cust_df = pd.DataFrame([{'name': c.name, 'lat': c.lat, 'lon': c.lon, 'segment': c.segment} for c in st.session_state.customers])
            for seg, group in cust_df.groupby('segment'):
                fig.add_trace(go.Scattermapbox(
                    lat=group['lat'], lon=group['lon'],
                    mode='markers',
                    marker=dict(size=10, color='orange'),
                    text=group['name'], name=f"Customers ({seg})",
                    hovertext=group['name']
                ))
            # Routes
            route_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377b2', '#7f7f7f']
            for i, route in enumerate(res['routes']):
                nodes = route['customers']
                if not nodes:
                    continue
                # Get coordinates for nodes: hub + customers
                cust_map = {c.id: (c.lat, c.lon) for c in st.session_state.customers}
                hub_map = {name: (info['lat'], info['lon']) for name, info in hubs.items()}
                # Build lat/lon sequence: start from customer's hub, then customer(s)
                first_cust_id = nodes[0]
                first_cust = next(c for c in st.session_state.customers if c.id == first_cust_id)
                hub_name = first_cust.hub_assignment
                lats = [hub_map[hub_name][0]]
                lons = [hub_map[hub_name][1]]
                for cid in nodes:
                    c = next(c for c in st.session_state.customers if c.id == cid)
                    lats.append(c.lat)
                    lons.append(c.lon)
                fig.add_trace(go.Scattermapbox(
                    lat=lats, lon=lons,
                    mode='lines+markers',
                    line=dict(width=2, color=route_colors[i % len(route_colors)]),
                    marker=dict(size=8, color=route_colors[i % len(route_colors)]),
                    name=f"Route {i+1}",
                    hovertext=route['route']
                ))
            fig.update_layout(
                mapbox=dict(style="open-street-map", center=dict(lat=-2.0, lon=29.7), zoom=8.5),
                height=500,
                margin=dict(l=0, r=0, t=30, b=0)
            )
            st.plotly_chart(fig, use_container_width=True)

            # Routes table
            st.subheader("📋 Optimized Routes")
            routes_df = pd.DataFrame(res['routes'])
            routes_df['customers'] = routes_df['customers'].apply(lambda x: ', '.join(x))
            st.dataframe(routes_df, use_container_width=True)

            # P&L breakdown
            st.subheader("📊 Profit & Loss Breakdown")
            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                pie_data = {
                    'Revenue': res['total_revenue_usd'],
                    'Empty KM Cost': res['empty_cost_usd'],
                    'Demurrage Penalty': res['demurrage_penalty_usd']
                }
                fig_pie = go.Figure(go.Pie(labels=list(pie_data.keys()), values=list(pie_data.values()), hole=0.4))
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_ch2:
                efficiency = max(0, 100 - (res['total_empty_km'] / (res['total_empty_km'] + 100) * 100))
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=efficiency,
                    title={'text': "Route Efficiency (%)"},
                    gauge={'axis': {'range': [0, 100]}, 'bar': {'color': '#0a2f6c'}} # Changed bar color
                ))
                st.plotly_chart(fig_gauge, use_container_width=True)

        with tabs[1]: # Commercial Insights
            st.subheader("📈 Customer-Specific Performance History")
            customer_ids = [c.id for c in st.session_state.customers]
            selected_customer_id = st.selectbox("Select Customer", customer_ids, key="customer_insights_selector")

            if selected_customer_id:
                current_customer = next(c for c in st.session_state.customers if c.id == selected_customer_id)
                st.write(f"##### Details for {current_customer.name} (Segment: {current_customer.segment})")
                st.write(f"* **Assigned Hub**: {current_customer.hub_assignment}")
                st.write(f"* **Flexibility**: {current_customer.flexibility}")
                st.write(f"* **Current Price/MMBTU**: ${current_customer.price_per_mmbtu:.2f}")

                customer_history_df = _generate_customer_history_df(current_customer)

                if not customer_history_df.empty:
                    # Summary KPIs
                    col_ci1, col_ci2, col_ci3, col_ci4 = st.columns(4)
                    col_ci1.metric("Avg Daily Nominated MMBTU", f"{customer_history_df['planned_mmbtu'].mean():.1f}")
                    col_ci2.metric("Avg Daily Delivered MMBTU", f"{customer_history_df['actual_mmbtu'].mean():.1f}")
                    col_ci3.metric("Total Historical Revenue", f"${customer_history_df['revenue_usd'].sum():,.0f}")
                    col_ci4.metric("Total Historical Penalties", f"${(customer_history_df['demurrage_charge_usd'] + customer_history_df['under_nomination_penalty_usd']).sum():,.0f}")

                    st.markdown("###### Daily Volume: Nominated vs. Actual")
                    fig_vol = go.Figure(data=[
                        go.Bar(name='Planned', x=customer_history_df['date'], y=customer_history_df['planned_mmbtu']),
                        go.Bar(name='Actual', x=customer_history_df['date'], y=customer_history_df['actual_mmbtu'])
                    ])
                    fig_vol.update_layout(barmode='group', height=300)
                    st.plotly_chart(fig_vol, use_container_width=True)

                    st.markdown("###### Daily Revenue and Penalties")
                    fig_rev_pen = go.Figure(data=[
                        go.Scatter(name='Revenue', x=customer_history_df['date'], y=customer_history_df['revenue_usd'], mode='lines+markers'),
                        go.Scatter(name='Demurrage', x=customer_history_df['date'], y=customer_history_df['demurrage_charge_usd'], mode='lines+markers'),
                        go.Scatter(name='Under-nom Penalty', x=customer_history_df['date'], y=customer_history_df['under_nomination_penalty_usd'], mode='lines+markers')
                    ])
                    fig_rev_pen.update_layout(height=300)
                    st.plotly_chart(fig_rev_pen, use_container_width=True)

                else:
                    st.info("No historical data available for this customer.")

        with tabs[2]: # Invoices
            # Invoices
            if st.session_state.invoices:
                st.subheader("🧾 Invoices")
                inv_df = pd.DataFrame(st.session_state.invoices)
                st.dataframe(inv_df[['invoice_id', 'customer_id', 'planned_mmbtu', 'actual_mmbtu',
                                     'price_per_mmbtu', 'base_amount', 'demurrage_charge', 'under_nomination_penalty', 'total_amount']],
                             use_container_width=True)
                # Download CSV
                csv = inv_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Invoice CSV", data=csv, file_name="invoices.csv", mime="text/csv")

                # Invoice summary chart
                st.subheader("📈 Invoice Summary")
                fig_inv = go.Figure()
                fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['total_amount'], name='Total Amount'))
                fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['demurrage_charge'], name='Demurrage'))
                fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['under_nomination_penalty'], name='Under-nom Penalty'))
                fig_inv.update_layout(barmode='group', height=400)
                st.plotly_chart(fig_inv, use_container_width=True)

        with tabs[3]: # Predictive Analytics (New Tab)
            st.subheader("🔮 Predictive Analytics: Scenario Modeling")
            st.markdown("Adjust the parameters below to simulate different market and operational scenarios and see their potential impact on key metrics.")

            # Scenario Input Widgets
            col_scenario1, col_scenario2 = st.columns(2)
            with col_scenario1:
                demand_shock_pct = st.slider("Simulate Demand Shock (%)", -20, 20, 0, 5, key="demand_shock")
                trailer_availability_change_pct = st.slider("Simulate Trailer Availability Change (%)", -20, 20, 0, 5, key="trailer_avail_change")
            with col_scenario2:
                new_customer_impact = st.slider("New Major Customer (MMBTU/day)", 0, 50, 0, 5, key="new_cust_impact")
                fuel_price_change_pct = st.slider("Simulate Fuel Price Change (%)", -15, 15, 0, 5, key="fuel_price_change")

            if st.button("Run Scenario Simulation", type="primary"):
                st.info("Running hypothetical simulation with selected parameters...")

                # --- Dynamic Scenario Calculation ---
                # 1. Create a deep copy of CONFIG and other relevant session state variables
                import copy
                simulated_config = copy.deepcopy(CONFIG)
                simulated_customers = copy.deepcopy(st.session_state.customers)
                simulated_nominations = copy.deepcopy(st.session_state.nominations)
                simulated_trailers = copy.deepcopy(st.session_state.trailers)
                simulated_date = date # Use the date from sidebar

                # 2. Adjust CONFIG based on fuel_price_change_pct
                simulated_config["pricing"]["operating_cost_per_km"] *= (1 + fuel_price_change_pct / 100)

                # 3. Adjust Trailers based on trailer_availability_change_pct
                current_num_trailers = len(simulated_trailers)
                new_num_trailers = int(current_num_trailers * (1 + trailer_availability_change_pct / 100))
                if new_num_trailers < 1: new_num_trailers = 1 # Ensure at least one trailer
                simulated_trailers = generate_trailers(new_num_trailers)

                # 4. Adjust Nominations based on demand_shock_pct
                for nom in simulated_nominations:
                    nom.volume_mmbtu *= (1 + demand_shock_pct / 100)
                    if nom.volume_mmbtu < 0: nom.volume_mmbtu = 0 # Ensure non-negative volume

                # 5. Add new customer and nominations if new_customer_impact > 0
                if new_customer_impact > 0:
                    new_cust_id = f"CUST-NEW-{datetime.now().strftime('%H%M%S')}"
                    # Create a hypothetical new customer
                    hypo_customer = Customer(
                        id=new_cust_id,
                        name="Hypothetical New Client",
                        segment="Industrial Boiler",
                        lat=-2.0, lon=29.8,
                        hub_assignment="Muhanga (Cooking)",
                        flexibility="Flex",
                        price_per_mmbtu=simulated_config["pricing"]["base_price_per_mmbtu"]
                    )
                    simulated_customers.append(hypo_customer)

                    # Create nominations for the new customer based on new_customer_impact
                    hypo_nomination = Nomination(
                        customer_id=new_cust_id,
                        date=simulated_date,
                        volume_mmbtu=new_customer_impact,
                        pressure_bar=250,
                        preferred_window_start=datetime.combine(simulated_date, datetime.min.time()) + timedelta(hours=9),
                        preferred_window_end=datetime.combine(simulated_date, datetime.min.time()) + timedelta(hours=17),
                        flexibility="Flex",
                        hub_assignment="Muhanga (Cooking)"
                    )
                    simulated_nominations.append(hypo_nomination)

                # 6. Re-run the optimization engine with simulated parameters
                simulated_engine = NominationOptimizationEngine(simulated_config)
                simulated_result = simulated_engine.optimize(
                    simulated_nominations,
                    simulated_customers,
                    simulated_trailers,
                    get_hub_inventory() # Assuming hub inventory is not part of simulation parameters for simplicity
                )

                # Display scenario results
                st.markdown("#### Scenario Results")
                st.markdown("##### KPI Comparison")
                kpi_comparison_df = _compare_kpis(st.session_state.result, simulated_result)
                st.dataframe(kpi_comparison_df, use_container_width=True)

                # Download CSV button for scenario results
                csv_simulation = kpi_comparison_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Scenario Results CSV",
                    data=csv_simulation,
                    file_name="scenario_kpi_comparison.csv",
                    mime="text/csv",
                )

                st.success("Scenario simulation complete!")

            else:
                st.info("Click 'Run Scenario Simulation' to see results for the chosen parameters.")

    else:
        st.info("Click 'Run Optimization' in the sidebar to see results.")

    st.caption("🔒 CONFIDENTIAL - CNG Commercial Department | Dynamic Nomination Engine v2.0")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    # Check if running in Streamlit
    try:
        # If streamlit is running, this will be the entry point
        main_dashboard()
    except:
        # Otherwise run the demo (for Colab without streamlit)
        print("Streamlit not detected. Running demo...")
        # Import and run the demo function from earlier version
        # (We'll embed it here for completeness)
        def run_demo():
            print("Demo mode - run the script with streamlit for interactive dashboard.")
            # Quick demo output
            customers = generate_sample_customers(10)
            nominations = generate_nominations(customers, datetime.now().date() + timedelta(days=1))
            trailers = generate_trailers(8)
            engine = NominationOptimizationEngine(CONFIG)
            result = engine.optimize(nominations, customers, trailers, get_hub_inventory())
            print(f"Optimization complete: {result['status']}")
            print(f"Total revenue: ${result['total_revenue_usd']:.2f}")
            print(f"Net margin: ${result['net_margin_usd']:.2f}")
        run_demo()
