# ============================================================
# DYNAMIC NOMINATION & SCHEDULING OPTIMIZATION ENGINE
# Complete CNG Downstream Commercial Module
# Version: 3.0 - Customer-Specific Pricing
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
# DATA CLASSES (UPDATED with customer-specific price)
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
    price_per_mmbtu: float  # <-- NEW: customer-specific gas price
    demurrage_history: int = 0

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
        "default_price_per_mmbtu": 12.50,  # fallback if customer doesn't have one
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
# SAMPLE DATA GENERATION (UPDATED with prices)
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
        # Assign customer-specific price based on segment
        if seg == "Auto Fleet":
            price = round(random.uniform(12.0, 15.0), 2)
        elif seg == "Industrial Boiler":
            price = round(random.uniform(10.0, 13.0), 2)
        else:  # Cooking Franchise
            price = round(random.uniform(14.0, 18.0), 2)
        customers.append(Customer(
            id=f"CUST-{i+1:03d}",
            name=f"{seg} {i+1}",
            segment=seg,
            lat=lat, lon=lon,
            hub_assignment=hub,
            flexibility=flex,
            price_per_mmbtu=price,
            demurrage_history=demurrage
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
# OPTIMIZATION ENGINE (UPDATED with customer-specific pricing)
# ============================================================
class NominationOptimizationEngine:
    def __init__(self, config: Dict):
        self.config = config
        self.hubs = config["hubs"]
        self.trailer_capacity_kg = config["fleet"]["trailer_capacity_kg"]
        self.demurrage_rate = config["pricing"]["demurrage_rate_per_hour"]
        self.grace_hours = config["pricing"]["demurrage_grace_hours"]
        self.op_cost_per_km = config["pricing"]["operating_cost_per_km"]
        self.avg_speed = config["travel"]["avg_speed_kmh"]
        self.default_price = config["pricing"]["default_price_per_mmbtu"]
        self.flex_discount = config["pricing"]["route_flex_discount"]
        self.rigid_surcharge = config["pricing"]["rigid_surcharge"]

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
            # Effective price = customer price * (1 - discount) if Flex, else * (1 + surcharge)
            if n.flexibility == "Flex":
                effective_price = c.price_per_mmbtu * (1 - self.flex_discount)
            else:
                effective_price = c.price_per_mmbtu * (1 + self.rigid_surcharge)
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
                'price_per_mmbtu': c.price_per_mmbtu,
                'effective_price': effective_price,
                'demurrage_history': c.demurrage_history,
                'revenue': n.volume_mmbtu * effective_price
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
        assigned = set()
        for i in range(num_trailers):
            served = []
            for j in range(num_customers):
                if x[i, j].solution_value() > 0.5:
                    served.append(j)
            if served:
                custs = nom_df.iloc[served]
                route_names = custs['name'].tolist()
                route_str = " → ".join(route_names)
                empty_km = 0
                if len(served) == 2:
                    c1 = custs.iloc[0]; c2 = custs.iloc[1]
                    empty_km = haversine(c1['lat'], c1['lon'], c2['lat'], c2['lon'])
                    route_str += f" (Cascade: {empty_km:.1f}km)"
                else:
                    hub = custs.iloc[0]['hub_assignment']
                    hub_info = self.hubs[hub]
                    empty_km = haversine(custs.iloc[0]['lat'], custs.iloc[0]['lon'],
                                        hub_info['lat'], hub_info['lon']) * 0.5
                total_empty_km += empty_km
                total_rev += custs['revenue'].sum()
                assigned.update(custs['customer_id'].tolist())
                routes.append({
                    "trailer": trailer_df.iloc[i]['id'],
                    "route": route_str,
                    "status": "✅ Scheduled",
                    "customers": custs['customer_id'].tolist()
                })
        demurrage = nom_df['demurrage_history'].sum() * self.demurrage_rate * 0.5
        empty_cost = total_empty_km * self.op_cost_per_km
        net_margin = total_rev - empty_cost - demurrage
        return {
            "status": "Success (MILP)",
            "total_trips": len(routes),
            "total_revenue_mmbtu": total_rev / (nom_df['effective_price'].mean() if len(nom_df) > 0 else self.default_price),
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
            route_customers = [row]
            empty_km = 0
            for idx2, row2 in sorted_noms.iterrows():
                if row2['customer_id'] in assigned:
                    continue
                if row2['flexibility'] == "Flex" and row2['hub_assignment'] == row['hub_assignment']:
                    dist = haversine(row['lat'], row['lon'], row2['lat'], row2['lon'])
                    if dist < 25:
                        assigned.add(row2['customer_id'])
                        route_customers.append(row2)
                        empty_km += dist
                        break
            route_names = [c['name'] for c in route_customers]
            route_str = " → ".join(route_names)
            if len(route_customers) > 1:
                route_str += f" (Cascade: {empty_km:.1f}km)"
            else:
                hub = row['hub_assignment']
                hub_info = self.hubs[hub]
                empty_km += haversine(row['lat'], row['lon'], hub_info['lat'], hub_info['lon']) * 0.5
            total_empty_km += empty_km
            total_rev += sum(c['revenue'] for c in route_customers)
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
            "total_revenue_mmbtu": total_rev / (nom_df['effective_price'].mean() if len(nom_df) > 0 else self.default_price),
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
# INVOICING MODULE (UPDATED with customer-specific price)
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
# STREAMLIT DASHBOARD (UPDATED to show customer prices)
# ============================================================
def main_dashboard():
    st.set_page_config(page_title="CNG Nomination Engine", page_icon="⛽", layout="wide")
    st.title("⛽ Dynamic Nomination & Scheduling Engine")
    st.markdown("### Commercial Optimization for CNG Virtual Pipeline")
    st.markdown("---")

    st.sidebar.header("⚙️ Controls")
    num_customers = st.sidebar.slider("Number of Customers", 5, 25, 10, 1)
    num_trailers = st.sidebar.slider("Number of Trailers", 3, 15, 8, 1)
    date = st.sidebar.date_input("Nomination Date", datetime.now().date() + timedelta(days=1))
    opt_mode = st.sidebar.selectbox("Optimization Mode", ["Balanced", "Profit Maximization", "Time Minimization"])
    run_button = st.sidebar.button("Run Optimization", type="primary")

    if 'customers' not in st.session_state:
        st.session_state.customers = generate_sample_customers(num_customers)
        st.session_state.nominations = generate_nominations(st.session_state.customers, date)
        st.session_state.trailers = generate_trailers(num_trailers)
        st.session_state.engine = NominationOptimizationEngine(CONFIG)
        st.session_state.result = None
        st.session_state.invoices = None
        st.session_state.actual_deliveries = None

    if st.sidebar.button("Reset Data"):
        st.session_state.customers = generate_sample_customers(num_customers)
        st.session_state.nominations = generate_nominations(st.session_state.customers, date)
        st.session_state.trailers = generate_trailers(num_trailers)
        st.session_state.result = None
        st.session_state.invoices = None
        st.session_state.actual_deliveries = None
        st.rerun()

    if run_button:
        with st.spinner("Optimizing..."):
            st.session_state.result = st.session_state.engine.optimize(
                st.session_state.nominations,
                st.session_state.customers,
                st.session_state.trailers,
                get_hub_inventory()
            )
            actual = {}
            for n in st.session_state.nominations:
                variation = np.random.uniform(0.85, 1.15)
                actual[n.customer_id] = n.volume_mmbtu * variation
            st.session_state.actual_deliveries = actual
            invoices = []
            for n in st.session_state.nominations:
                cust = next(c for c in st.session_state.customers if c.id == n.customer_id)
                demurrage_hours = random.randint(0, 6)
                inv = InvoiceGenerator.generate_invoice(
                    n.customer_id,
                    n.volume_mmbtu,
                    actual[n.customer_id],
                    cust.price_per_mmbtu,
                    demurrage_hours
                )
                invoices.append(inv)
            st.session_state.invoices = invoices
        st.success("Optimization complete!")

    if st.session_state.result is not None:
        res = st.session_state.result
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Trips", res['total_trips'])
        col2.metric("Revenue", f"${res['total_revenue_usd']:,.0f}")
        col3.metric("Empty KM", f"{res['total_empty_km']:.1f} km")
        col4.metric("Net Margin", f"${res['net_margin_usd']:,.0f}")
        col5.metric("Fulfillment", f"{res['fulfillment_rate']:.1f}%")

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
        cust_df = pd.DataFrame([{'name': c.name, 'lat': c.lat, 'lon': c.lon, 'segment': c.segment} for c in st.session_state.customers])
        for seg, group in cust_df.groupby('segment'):
            fig.add_trace(go.Scattermapbox(
                lat=group['lat'], lon=group['lon'],
                mode='markers',
                marker=dict(size=10, color='orange'),
                text=group['name'], name=f"Customers ({seg})",
                hovertext=group['name']
            ))
        route_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
        for i, route in enumerate(res['routes']):
            nodes = route['customers']
            if not nodes:
                continue
            cust_map = {c.id: (c.lat, c.lon) for c in st.session_state.customers}
            hub_map = {name: (info['lat'], info['lon']) for name, info in hubs.items()}
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

        st.subheader("📋 Optimized Routes")
        routes_df = pd.DataFrame(res['routes'])
        routes_df['customers'] = routes_df['customers'].apply(lambda x: ', '.join(x))
        st.dataframe(routes_df, use_container_width=True)

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
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': '#0a2f6c'}}
            ))
            st.plotly_chart(fig_gauge, use_container_width=True)

        # Customer price table
        st.subheader("💰 Customer Pricing")
        price_df = pd.DataFrame([{
            'Customer': c.name,
            'Segment': c.segment,
            'Price ($/MMBTU)': c.price_per_mmbtu,
            'Flexibility': c.flexibility
        } for c in st.session_state.customers])
        st.dataframe(price_df, use_container_width=True)

        if st.session_state.invoices:
            st.subheader("🧾 Invoices")
            inv_df = pd.DataFrame(st.session_state.invoices)
            st.dataframe(inv_df[['invoice_id', 'customer_id', 'planned_mmbtu', 'actual_mmbtu',
                                 'price_per_mmbtu', 'base_amount', 'demurrage_charge',
                                 'under_nomination_penalty', 'total_amount']],
                         use_container_width=True)
            csv = inv_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Invoice CSV", data=csv, file_name="invoices.csv", mime="text/csv")

            fig_inv = go.Figure()
            fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['total_amount'], name='Total Amount'))
            fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['demurrage_charge'], name='Demurrage'))
            fig_inv.add_trace(go.Bar(x=inv_df['customer_id'], y=inv_df['under_nomination_penalty'], name='Under-nom Penalty'))
            fig_inv.update_layout(barmode='group', height=400)
            st.plotly_chart(fig_inv, use_container_width=True)

    else:
        st.info("Click 'Run Optimization' in the sidebar to see results.")

    st.caption("🔒 CONFIDENTIAL - CNG Commercial Department | Dynamic Nomination Engine v3.0")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    try:
        main_dashboard()
    except:
        # Fallback to demo if not in streamlit
        def run_demo():
            print("Demo mode - run with streamlit for interactive dashboard.")
            customers = generate_sample_customers(10)
            nominations = generate_nominations(customers, datetime.now().date() + timedelta(days=1))
            trailers = generate_trailers(8)
            engine = NominationOptimizationEngine(CONFIG)
            result = engine.optimize(nominations, customers, trailers, get_hub_inventory())
            print(f"Optimization complete: {result['status']}")
            print(f"Total revenue: ${result['total_revenue_usd']:.2f}")
            print(f"Net margin: ${result['net_margin_usd']:.2f}")
            print("
Customer prices:")
            for c in customers:
                print(f"  {c.name}: ${c.price_per_mmbtu:.2f}/MMBTU")
        run_demo()