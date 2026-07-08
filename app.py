
# app.py - Complete CNG Commercial Prototype (All 4 Modules)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import random

# ----------------------------
# 1. PAGE CONFIGURATION
# ----------------------------
st.set_page_config(page_title="CNG Rwanda - Full Commercial Suite", page_icon="⛽", layout="wide")

# ----------------------------
# 2. INITIALIZE SESSION STATE (Persistent Data)
# ----------------------------
if 'trailers' not in st.session_state:
    # Simulate 4 Trailers (Jumbos)
    st.session_state.trailers = pd.DataFrame({
        'trailer_id': ['T-001', 'T-002', 'T-003', 'T-004'],
        'status': ['Moving', 'Loading', 'Unloading', 'Idle'],
        'current_lat': [-1.94, -1.98, -1.90, -1.95],
        'current_lon': [30.06, 30.10, 30.02, 30.08],
        'destination': ['Kigali Industries', 'Remera Auto Stn', 'Muhanga Textiles', 'Mother Station'],
        'eta_minutes': [45, 15, 30, 0],
        'pressure_psi': [3200, 3100, 2800, 3500],
        'load_kg': [1200, 800, 900, 0]
    })

if 'nomination_log' not in st.session_state:
    st.session_state.nomination_log = pd.DataFrame(columns=[
        'timestamp', 'customer', 'type', 'volume_kg', 'status', 'mdq_limit'
    ])

if 'delivery_log' not in st.session_state:
    # This will be fed by the Dispatch module
    st.session_state.delivery_log = pd.DataFrame(columns=[
        'date', 'customer_id', 'delivered_kg'
    ])

# ----------------------------
# 3. DATA LOADING (Customers & Static Settings)
# ----------------------------
@st.cache_data
def load_static_data():
    customers = pd.DataFrame({
        'customer_id': ['C001', 'C002', 'C003', 'C004', 'C005', 'C006', 'C007', 'C008', 'C009', 'C010'],
        'name': ['Kigali Industries', 'Gasorwa Mfg', 'Muhanga Textiles', 'Remera Auto Stn',
                 'Kimironko Hub', 'Nyabugogo Bus', 'Heaven Restaurant', 'Serena Kitchen',
                 'Gisenyi Fish Farm', 'Local Food Proc'],
        'segment': ['Industrial', 'Industrial', 'Industrial', 'Auto', 'Auto', 'Auto',
                    'Cooking', 'Cooking', 'Industrial', 'Cooking'],
        'base_price': [1.85, 1.90, 1.75, 2.50, 2.45, 2.55, 2.20, 2.30, 1.95, 2.15],
        'take_or_pay': [0.80, 0.80, 0.85, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0],
        'mdq_kg': [2000, 1800, 2200, 800, 750, 900, 500, 450, 1600, 400],
        'lat': [-1.94, -1.99, -2.02, -1.96, -1.92, -1.95, -1.93, -1.91, -2.10, -1.89],
        'lon': [30.06, 30.12, 29.98, 30.08, 30.14, 30.05, 30.09, 30.11, 29.95, 30.15]
    })
    return customers

customers_df = load_static_data()
mother_station = {'lat': -1.9441, 'lon': 30.0619}

# ----------------------------
# 4. CORE FUNCTIONS FOR EACH MODULE
# ----------------------------

def validate_nomination(customer_id, volume):
    """Checks MDQ limit for customer."""
    customer = customers_df[customers_df['customer_id'] == customer_id]
    if customer.empty:
        return False, "Customer not found."
    mdq = customer.iloc[0]['mdq_kg']
    if volume > mdq:
        return False, f"Volume {volume}kg exceeds Maximum Daily Quantity (MDQ) of {mdq}kg."
    return True, "Nomination Accepted."

def run_dispatch_optimization(scenario='normal'):
    """Simulates the Brain: Assigns trailers and calculates metrics."""
    trailers = st.session_state.trailers.copy()
    # Simulate cost and utilization logic
    if scenario == 'breakdown':
        # T-001 breaks down, delayed ETA
        trailers.loc[trailers['trailer_id'] == 'T-001', 'eta_minutes'] += 60
        trailers.loc[trailers['trailer_id'] == 'T-001', 'status'] = 'Delayed'

    # Calculate Fleet Metrics
    total_trailers = len(trailers)
    active = len(trailers[trailers['status'].isin(['Moving', 'Unloading'])])
    utilization = (active / total_trailers) * 100 if total_trailers > 0 else 0
    total_load = trailers['load_kg'].sum()

    # Simulate a dispatched route (for map)
    dispatched_orders = []
    for _, row in trailers.iterrows():
        if row['destination'] != 'Mother Station':
            dispatched_orders.append({
                'trailer': row['trailer_id'],
                'to': row['destination'],
                'eta': row['eta_minutes'],
                'load': row['load_kg']
            })

    return trailers, utilization, total_load, dispatched_orders

def generate_live_alerts():
    """Simulates predictive alerts for the Monitor tab."""
    alerts = []
    trailers = st.session_state.trailers

    # Alert 1: Low inventory at a random customer
    rand_cust = customers_df.sample(1).iloc[0]
    alerts.append({
        'type': '⚠️ Inventory Warning',
        'message': f"{rand_cust['name']} has less than 2 hours of buffer stock.",
        'severity': 'High'
    })

    # Alert 2: Trailer ETA deviation
    delayed = trailers[trailers['eta_minutes'] > 50]
    if not delayed.empty:
        for _, row in delayed.iterrows():
            alerts.append({
                'type': '⏰ ETA Alert',
                'message': f"Trailer {row['trailer_id']} is behind schedule by 20 mins.",
                'severity': 'Medium'
            })

    # Alert 3: Pressure drop
    low_pressure = trailers[trailers['pressure_psi'] < 2900]
    if not low_pressure.empty:
        for _, row in low_pressure.iterrows():
            alerts.append({
                'type': '🔧 Equipment Alert',
                'message': f"Pressure drop detected on {row['trailer_id']} ({row['pressure_psi']} psi).",
                'severity': 'Critical'
            })

    if not alerts:
        alerts.append({'type': '✅ All Clear', 'message': 'No active alerts.', 'severity': 'Info'})

    return alerts[:5] # Limit to 5

def calculate_settlement(start_date, end_date):
    """Enhanced Settlement Engine using the delivery log."""
    # Merge customer data with delivery log
    if st.session_state.delivery_log.empty:
        # Fallback to simulated data if no deliveries yet
        sim_deliveries = []
        for _, cust in customers_df.iterrows():
            sim_deliveries.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'customer_id': cust['customer_id'],
                'delivered_kg': np.random.uniform(100, 1500)
            })
        del_df = pd.DataFrame(sim_deliveries)
    else:
        del_df = st.session_state.delivery_log

    # Filter by date
    del_df['date'] = pd.to_datetime(del_df['date'])
    mask = (del_df['date'] >= pd.to_datetime(start_date)) & (del_df['date'] <= pd.to_datetime(end_date))
    filtered_del = del_df[mask]

    agg_del = filtered_del.groupby('customer_id')['delivered_kg'].sum().reset_index()
    merged = pd.merge(customers_df, agg_del, on='customer_id', how='left').fillna(0)

    # Simulate Nominations for settlement (assume nominal = delivered * 1.1 for industrial, else equal)
    results = []
    for _, row in merged.iterrows():
        delivered = row['delivered_kg']
        # If no delivery, set to 0
        if delivered == 0:
            continue

        price = row['base_price']
        top_pct = row['take_or_pay']

        # Simulate nomination (for demo, industrial under-lifts)
        if row['segment'] == 'Industrial':
            nominated = delivered * 1.25  # They nominated 25% more than they took
        else:
            nominated = delivered * 1.02

        min_obligation = nominated * top_pct
        billable_volume = max(delivered, min_obligation)
        shortfall = max(0, min_obligation - delivered)
        penalty_rate = 0.40
        penalty_amount = shortfall * price * penalty_rate
        base_revenue = delivered * price
        total_charge = base_revenue + penalty_amount
        logistics_cost = delivered * 0.65
        gross_margin = total_charge - logistics_cost

        results.append({
            'customer_id': row['customer_id'],
            'name': row['name'],
            'segment': row['segment'],
            'price': price,
            'nominated_kg': round(nominated, 2),
            'delivered_kg': round(delivered, 2),
            'min_obligation': round(min_obligation, 2),
            'shortfall_kg': round(shortfall, 2),
            'penalty_amount': round(penalty_amount, 2),
            'base_revenue': round(base_revenue, 2),
            'total_revenue': round(total_charge, 2),
            'logistics_cost': round(logistics_cost, 2),
            'gross_margin': round(gross_margin, 2),
            'margin_pct': round((gross_margin / total_charge) * 100, 2) if total_charge > 0 else 0
        })

    return pd.DataFrame(results)

# ----------------------------
# 5. STREAMLIT UI - NAVIGATION
# ----------------------------
st.sidebar.title("⛽ CNG Commercial Suite")
st.sidebar.markdown("---")
module = st.sidebar.radio(
    "Navigate to Module",
    ["📝 Nomination Engine", "🧠 Dispatch Optimizer", "📡 Real-Time Monitor", "💰 Settlement & BI"]
)

# Global KPI in Sidebar (Commercial Overview)
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Live Commercial Pulse")
total_trailers = len(st.session_state.trailers)
active_trailers = len(st.session_state.trailers[st.session_state.trailers['status'].isin(['Moving', 'Unloading'])])
st.sidebar.metric("🚛 Active Trailers", f"{active_trailers}/{total_trailers}")
st.sidebar.metric("📦 Total Load (kg)", f"{st.session_state.trailers['load_kg'].sum():,.0f}")

# ----------------------------
# MODULE 1: NOMINATION ENGINE
# ----------------------------
if module == "📝 Nomination Engine":
    st.title("📝 Customer Nomination & Demand Management")
    st.caption("Multi-Channel Input: Fixed, Dynamic, and Emergency Top-ups with real-time MDQ validation.")

    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("➕ Submit New Nomination")
        with st.form("nomination_form"):
            cust = st.selectbox("Select Customer", options=customers_df['name'])
            cust_id = customers_df[customers_df['name'] == cust].iloc[0]['customer_id']
            mdq = customers_df[customers_df['name'] == cust].iloc[0]['mdq_kg']
            st.caption(f"MDQ Limit: **{mdq} kg**")

            nom_type = st.radio("Nomination Regime", ["Fixed (Daily)", "Dynamic (Intra-day)", "Emergency Top-up"])
            volume = st.number_input("Volume (kg)", min_value=0.0, max_value=float(mdq), value=float(mdq * 0.7))
            submit = st.form_submit_button("Submit Nomination")

            if submit:
                valid, msg = validate_nomination(cust_id, volume)
                status = "✅ Confirmed" if valid else "❌ Rejected"
                new_entry = pd.DataFrame([{
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'customer': cust,
                    'type': nom_type,
                    'volume_kg': volume,
                    'status': status,
                    'mdq_limit': mdq
                }])
                st.session_state.nomination_log = pd.concat([st.session_state.nomination_log, new_entry], ignore_index=True)
                if valid:
                    st.success(f"✅ Nomination Confirmed! {volume}kg scheduled for {cust}.")
                    # Automatically create a delivery entry (simulate scheduling)
                    new_del = pd.DataFrame([{
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'customer_id': cust_id,
                        'delivered_kg': volume * 0.95  # Slight delivery loss
                    }])
                    st.session_state.delivery_log = pd.concat([st.session_state.delivery_log, new_del], ignore_index=True)
                else:
                    st.error(f"❌ Rejected: {msg}")

    with col2:
        st.subheader("📜 Nomination History")
        if not st.session_state.nomination_log.empty:
            st.dataframe(st.session_state.nomination_log.sort_values('timestamp', ascending=False), use_container_width=True)
        else:
            st.info("No nominations submitted yet. Use the form to start.")

        st.subheader("📊 Demand Pattern")
        if not st.session_state.nomination_log.empty:
            fig = px.bar(st.session_state.nomination_log, x='customer', y='volume_kg', color='type',
                         title="Nomination Volumes by Customer")
            st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# MODULE 2: DISPATCH OPTIMIZER
# ----------------------------
elif module == "🧠 Dispatch Optimizer":
    st.title("🧠 Intelligent Dispatch & Optimization Engine")
    st.caption("Multi-Objective Optimization: Cost Minimization | Asset Utilization | Service Level Maximization.")

    # Scenario Simulator
    scenario = st.radio("Scenario Mode", ["Normal Operations", "🚨 Breakdown Contingency (T-001)"], horizontal=True)

    if st.button("🔄 Run Optimization"):
        if scenario == "🚨 Breakdown Contingency (T-001)":
            trailers, utilization, total_load, orders = run_dispatch_optimization(scenario='breakdown')
            st.warning("⚠️ Contingency Plan Activated: T-001 re-routed. ETA extended by 60 mins.")
        else:
            trailers, utilization, total_load, orders = run_dispatch_optimization(scenario='normal')
            st.success("✅ Optimization Complete: All schedules optimized.")

        # Update session state
        st.session_state.trailers = trailers

        # Display Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("📈 Fleet Utilization", f"{utilization:.1f}%", delta="+5% from baseline")
        col2.metric("⏱️ Avg ETA (mins)", f"{trailers['eta_minutes'].mean():.0f}", delta="-10 mins")
        col3.metric("📦 Total Dispatched (kg)", f"{total_load:,.0f}")

        # Display Map
        st.subheader("🗺️ Dispatch Route Map")
        fig = go.Figure()

        # Mother Station
        fig.add_trace(go.Scattermapbox(
            lat=[mother_station['lat']], lon=[mother_station['lon']],
            mode='markers+text', marker=dict(size=15, color='red'), text=["Mother Station"],
            textposition="top right"
        ))

        # Trailers
        fig.add_trace(go.Scattermapbox(
            lat=trailers['current_lat'], lon=trailers['current_lon'],
            mode='markers+text', marker=dict(size=12, color='blue'), text=trailers['trailer_id'],
            textposition="top center"
        ))

        # Destinations
        dest_lats, dest_lons = [], []
        for dest in trailers['destination']:
            if dest != "Mother Station":
                cust_row = customers_df[customers_df['name'] == dest]
                if not cust_row.empty:
                    dest_lats.append(cust_row.iloc[0]['lat'])
                    dest_lons.append(cust_row.iloc[0]['lon'])
        fig.add_trace(go.Scattermapbox(
            lat=dest_lats, lon=dest_lons,
            mode='markers', marker=dict(size=10, color='green'), text=["Customers"]
        ))

        fig.update_layout(
            mapbox=dict(style="open-street-map", center=dict(lat=-1.97, lon=30.08), zoom=10),
            height=500, margin=dict(l=0, r=0, t=0, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Dispatch Schedule Table
        st.subheader("📋 Optimized Dispatch Schedule")
        st.dataframe(trailers[['trailer_id', 'status', 'destination', 'eta_minutes', 'load_kg', 'pressure_psi']], use_container_width=True)

# ----------------------------
# MODULE 3: REAL-TIME MONITOR
# ----------------------------
elif module == "📡 Real-Time Monitor":
    st.title("📡 Real-Time Monitoring & Digital Twin")
    st.caption("End-to-end visibility: Tracker locations, Pressure/Temperature telemetry, and Predictive Alerts.")

    # Simulate time progression for realistic movement
    if st.button("⏩ Advance Time (+15 mins)"):
        # Update trailer positions randomly
        for idx in st.session_state.trailers.index:
            if st.session_state.trailers.loc[idx, 'status'] == 'Moving':
                st.session_state.trailers.loc[idx, 'current_lat'] += random.uniform(-0.005, 0.005)
                st.session_state.trailers.loc[idx, 'current_lon'] += random.uniform(-0.005, 0.005)
                st.session_state.trailers.loc[idx, 'eta_minutes'] = max(5, st.session_state.trailers.loc[idx, 'eta_minutes'] - 15)
                st.session_state.trailers.loc[idx, 'pressure_psi'] -= random.uniform(0, 50)

    # Alerts
    st.subheader("🚨 Predictive Alerts")
    alerts = generate_live_alerts()
    for alert in alerts:
        if alert['severity'] == 'Critical':
            st.error(f"{alert['type']}: {alert['message']}")
        elif alert['severity'] == 'High':
            st.warning(f"{alert['type']}: {alert['message']}")
        else:
            st.info(f"{alert['type']}: {alert['message']}")

    # Digital Twin Cards
    col1, col2, col3, col4 = st.columns(4)
    trailers = st.session_state.trailers
    for idx, (_, row) in enumerate(trailers.iterrows()):
        with [col1, col2, col3, col4][idx % 4]:
            st.metric(f"🚛 {row['trailer_id']}", f"{row['status']}")
            st.caption(f"📍 Dest: {row['destination']} | ETA: {row['eta_minutes']}m")
            st.caption(f"⚙️ {row['pressure_psi']} psi | Load: {row['load_kg']}kg")

    # Live Map
    st.subheader("🗺️ Live Fleet Tracker")
    fig = go.Figure()

    # Add all trailers with color coding by status
    color_map = {'Moving': 'green', 'Loading': 'orange', 'Unloading': 'red', 'Idle': 'gray', 'Delayed': 'purple'}
    for status, color in color_map.items():
        subset = trailers[trailers['status'] == status]
        if not subset.empty:
            fig.add_trace(go.Scattermapbox(
                lat=subset['current_lat'], lon=subset['current_lon'],
                mode='markers+text', marker=dict(size=14, color=color),
                text=subset['trailer_id'] + " - " + subset['status'],
                name=status
            ))

    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=-1.97, lon=30.08), zoom=11),
        height=400, margin=dict(l=0, r=0, t=0, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# MODULE 4: SETTLEMENT & BI (VALUE CAPTURE)
# ----------------------------
else:
    st.title("💰 Commercial Settlement & Business Intelligence")
    st.caption("The Value Capture: Automated invoicing, KPI scorecards, and behavioral analytics.")

    # Date Filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Period From", value=datetime.now().date() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Period To", value=datetime.now().date())

    # Segment Filter
    segments = st.multiselect("Filter by Segment", options=customers_df['segment'].unique(), default=customers_df['segment'].unique())

    # Calculate Settlement
    settlement_df = calculate_settlement(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    filtered_settlement = settlement_df[settlement_df['segment'].isin(segments)]

    if filtered_settlement.empty:
        st.warning("No delivery data found for this period. Submit nominations in Tab 1 to generate data.")
    else:
        # Top KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💰 Total Revenue", f"${filtered_settlement['total_revenue'].sum():,.0f}")
        k2.metric("📈 Gross Margin", f"${filtered_settlement['gross_margin'].sum():,.0f}")
        k3.metric("⚠️ Penalties Captured", f"${filtered_settlement['penalty_amount'].sum():,.0f}")
        k4.metric("📦 Total Delivered (kg)", f"{filtered_settlement['delivered_kg'].sum():,.0f}")

        # Charts
        c1, c2 = st.columns(2)
        with c1:
            seg_rev = filtered_settlement.groupby('segment')['total_revenue'].sum().reset_index()
            fig = px.pie(seg_rev, values='total_revenue', names='segment', hole=0.4, title="Revenue by Segment")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            top5 = filtered_settlement.nlargest(5, 'total_revenue')
            fig = px.bar(top5, x='name', y='total_revenue', color='segment', text_auto='.2s', title="Top 5 Customers")
            st.plotly_chart(fig, use_container_width=True)

        # Detailed Ledger
        st.subheader("📋 Commercial Settlement Ledger")
        display_cols = ['name', 'segment', 'nominated_kg', 'delivered_kg', 'shortfall_kg',
                        'penalty_amount', 'base_revenue', 'total_revenue', 'gross_margin', 'margin_pct']
        display_df = filtered_settlement[display_cols].copy()
        display_df.columns = ['Customer', 'Segment', 'Nominated', 'Delivered', 'Shortfall',
                              'Penalty', 'Base Rev', 'Total Charge', 'Gross Margin', 'Margin %']
        st.dataframe(display_df.style.format({
            'Nominated': '{:,.0f}', 'Delivered': '{:,.0f}', 'Shortfall': '{:,.0f}',
            'Penalty': '${:,.2f}', 'Base Rev': '${:,.2f}', 'Total Charge': '${:,.2f}',
            'Gross Margin': '${:,.2f}', 'Margin %': '{:.1f}%'
        }).background_gradient(subset=['Total Charge'], cmap='Blues'), use_container_width=True)

        # Export
        csv = filtered_settlement.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="cng_settlement_report.csv">⬇️ Download Full Settlement CSV</a>'
        st.markdown(href, unsafe_allow_html=True)
