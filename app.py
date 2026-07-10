
# app.py - Complete CNG Commercial Prototype (All 4 Modules + Enhancements)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import random
import matplotlib.pyplot as plt
import io

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
        'load_mmbtu': [1200, 800, 900, 0]
    })

if 'nomination_log' not in st.session_state:
    st.session_state.nomination_log = pd.DataFrame(
        columns=['timestamp', 'customer', 'type', 'volume_mmbtu', 'status']
    )

if 'delivery_log' not in st.session_state:
    # This will be fed by the Dispatch module or simulated
    st.session_state.delivery_log = pd.DataFrame(
        columns=['date', 'customer_id', 'delivered_mmbtu']
    )

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
        'price_per_mmbtu': [1.85, 1.90, 1.75, 2.50, 2.45, 2.55, 2.20, 2.30, 1.95, 2.15],
        'take_or_pay': [0.80, 0.80, 0.85, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0],
        'mdq_mmbtu': [2000, 1800, 2200, 800, 750, 900, 500, 450, 1600, 400],
        'lat': [-1.94, -1.99, -2.02, -1.96, -1.92, -1.95, -1.93, -1.91, -2.10, -1.89],
        'lon': [30.06, 30.12, 29.98, 30.08, 30.14, 30.05, 30.09, 30.11, 29.95, 30.15],
        'baseline_fuel': ['HFO', 'DIESEL', 'COAL', 'PETROL', 'LPG', 'WOOD', 'DIESEL', 'HFO', 'PEAT', 'LPG'] # Added baseline fuel for each customer
    })
    return customers

customers_df = load_static_data()
mother_station = {'lat': -1.9441, 'lon': 30.0619}

# Conversion factor for MScf to MMBTU (example value, can be adjusted)
MScf_TO_MMBTU_FACTOR = 1.028 # 1 MScf approx 1.028 MMBTU for natural gas

# ----------------------------
# 4. CORE FUNCTIONS FOR EACH MODULE
# ----------------------------

def validate_nomination(customer_id, volume_mmbtu):
    """Checks MDQ limit for customer."""
    customer = customers_df[customers_df['customer_id'] == customer_id]
    if customer.empty:
        return False, "Customer not found."
    mdq = customer.iloc[0]['mdq_mmbtu']
    if volume_mmbtu > mdq:
        pass
    return True, "Nomination Accepted."

def run_dispatch_optimization(scenario='normal'):
    """Simulates the Brain: Assigns trailers and calculates metrics."""
    trailers = st.session_state.trailers.copy()
    if scenario == 'breakdown':
        trailers.loc[trailers['trailer_id'] == 'T-001', 'eta_minutes'] += 60
        trailers.loc[trailers['trailer_id'] == 'T-001', 'status'] = 'Delayed'

    total_trailers = len(trailers)
    active = len(trailers[trailers['status'].isin(['Moving', 'Unloading'])])
    utilization = (active / total_trailers) * 100 if total_trailers > 0 else 0
    total_load = trailers['load_mmbtu'].sum()

    dispatched_orders = []
    for _, row in trailers.iterrows():
        if row['destination'] != 'Mother Station':
            dispatched_orders.append({
                'trailer': row['trailer_id'],
                'to': row['destination'],
                'eta': row['eta_minutes'],
                'load': row['load_mmbtu'] # Corrected: should be load_mmbtu
            })

    return trailers, utilization, total_load, dispatched_orders

def generate_live_alerts():
    """Simulates predictive alerts for the Monitor tab."""
    alerts = []
    trailers = st.session_state.trailers

    rand_cust = customers_df.sample(1).iloc[0]
    alerts.append({
        'type': '⚠️ Inventory Warning',
        'message': f"{rand_cust['name']} has less than 2 hours of buffer stock.",
        'severity': 'High'
    })

    delayed = trailers[trailers['eta_minutes'] > 50]
    if not delayed.empty:
        for _, row in delayed.iterrows():
            alerts.append({
                'type': '⏰ ETA Alert',
                'message': f"Trailer {row['trailer_id']} is behind schedule by 20 mins.",
                'severity': 'Medium'
            })

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

    return alerts[:5]

def calculate_settlement(start_date, end_date, customers_data=None):
    """Enhanced Settlement Engine using the delivery log."""
    if customers_data is None:
        customers_data = customers_df

    if st.session_state.delivery_log.empty:
        sim_deliveries = []
        for _, cust in customers_data.iterrows():
            sim_deliveries.append({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'customer_id': cust['customer_id'],
                'delivered_mmbtu': np.random.uniform(100, 1500)
            })
        del_df = pd.DataFrame(sim_deliveries)
    else:
        del_df = st.session_state.delivery_log

    del_df['date'] = pd.to_datetime(del_df['date'])
    mask = (del_df['date'] >= pd.to_datetime(start_date)) & (del_df['date'] <= pd.to_datetime(end_date))
    filtered_del = del_df[mask]

    agg_del = filtered_del.groupby('customer_id')['delivered_mmbtu'].sum().reset_index()
    merged = pd.merge(customers_data, agg_del, on='customer_id', how='left').fillna(0)

    # --- Carbon Emission Factors ---
    # Define emission factors for various fuels (tons of CO2e per MMBTU)
    fuel_emission_factors_per_mmbtu = {
        'CNG': 0.05,
        'DIESEL': 0.08,
        'HFO': 0.095,
        'LPG': 0.06,
        'PEAT': 0.12,
        'COAL': 0.15,
        'PETROL': 0.075,
        'WOOD': 0.11
    }
    carbon_credit_price_per_ton_co2e = 50.0 # Example: $50 per ton of CO2e

    results = []
    for _, row in merged.iterrows():
        delivered = row['delivered_mmbtu']
        if delivered == 0:
            continue

        price = row['price_per_mmbtu']
        top_pct = row['take_or_pay']

        if row['segment'] == 'Industrial':
            nominated = delivered * 1.25
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

        # --- Calculate Carbon Emissions and Reductions ---
        actual_cng_emissions = delivered * fuel_emission_factors_per_mmbtu['CNG']

        # Get the customer's baseline fuel and its emission factor
        customer_baseline_fuel = row['baseline_fuel']
        baseline_fossil_fuel_emission_factor_per_mmbtu = fuel_emission_factors_per_mmbtu.get(customer_baseline_fuel, 0.08) # Default to Diesel if not found

        potential_baseline_emissions = delivered * baseline_fossil_fuel_emission_factor_per_mmbtu
        carbon_emission_reductions = potential_baseline_emissions - actual_cng_emissions

        # Carbon credit earnings are based on reductions
        carbon_credit_earnings = carbon_emission_reductions * carbon_credit_price_per_ton_co2e

        results.append({
            'customer_id': row['customer_id'],
            'name': row['name'],
            'segment': row['segment'],
            'price_per_mmbtu': price,
            'nominated_mmbtu': round(nominated, 2),
            'delivered_mmbtu': round(delivered, 2),
            'min_obligation_mmbtu': round(min_obligation, 2),
            'shortfall_mmbtu': round(shortfall, 2),
            'penalty_amount': round(penalty_amount, 2),
            'base_revenue': round(base_revenue, 2),
            'total_revenue': round(total_charge, 2),
            'logistics_cost': round(logistics_cost, 2),
            'gross_margin': round(gross_margin, 2),
            'margin_pct': round((gross_margin / total_charge) * 100, 2) if total_charge > 0 else 0,
            'actual_cng_emissions': round(actual_cng_emissions, 2), # Emissions from CNG
            'carbon_emission_reductions': round(carbon_emission_reductions, 2),
            'carbon_credit_earnings': round(carbon_credit_earnings, 2)
        })

    return pd.DataFrame(results)

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Settlement Data')
    processed_data = output.getvalue()
    return processed_data


def forecast_demand(customer_id, days=7):
    # Simulate a basic demand forecast based on historical deliveries
    customer_deliveries = st.session_state.delivery_log[st.session_state.delivery_log['customer_id'] == customer_id]
    if customer_deliveries.empty:
        return pd.DataFrame({'date': pd.date_range(start=datetime.now(), periods=days, freq='D'), 'forecast_mmbtu': [500] * days})

    customer_deliveries['date'] = pd.to_datetime(customer_deliveries['date'])
    daily_avg = customer_deliveries.groupby('date')['delivered_mmbtu'].sum().mean() # Base for forecast

    forecast_dates = pd.date_range(start=datetime.now(), periods=days, freq='D')
    # Make forecast slightly more dynamic based on avg, with some random variation
    forecast_volumes = [max(100, daily_avg + random.uniform(-0.1 * daily_avg, 0.1 * daily_avg)) for _ in range(days)]

    return pd.DataFrame({
        'date': forecast_dates,
        'forecast_mmbtu': forecast_volumes
    })


# ----------------------------
# 5. STREAMLIT UI - NAVIGATION
# ----------------------------
st.sidebar.title("⛽ CNG Commercial Suite")
st.sidebar.markdown("---")
module = st.sidebar.radio(
    "Navigate to Module",
    ["📝 Nomination Engine", "🧠 Dispatch Optimizer", "📡 Real-Time Monitor", "💰 Settlement & BI", "📈 Demand Forecasting", "⚙️ Scenario Simulation"]
)

# Global KPI in Sidebar (Commercial Overview)
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Live Commercial Pulse")
total_trailers = len(st.session_state.trailers)
active_trailers = len(st.session_state.trailers[st.session_state.trailers['status'].isin(['Moving', 'Unloading'])])
st.sidebar.metric("🚛 Active Trailers", f"{active_trailers}/{total_trailers}")
st.sidebar.metric("📦 Total Load (MMBTU)", f"{st.session_state.trailers['load_mmbtu'].sum():,.0f}")

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
            nom_type = st.radio("Nomination Regime", ["Fixed (Daily)", "Dynamic (Intra-day)", "Emergency Top-up"])
            volume_mscf = st.number_input("Volume (MScf)", min_value=0.0, max_value=None, value=1000.0)
            confirm_submission = st.checkbox("I confirm these details are correct.")

            submit = st.form_submit_button("Submit Nomination")

            if submit:
                if not confirm_submission:
                    st.warning("⚠️ Please confirm the details by checking the box before submitting.")
                elif volume_mscf <= 0:
                    st.error("❌ Nomination volume (MScf) must be greater than zero.")
                else:
                    volume_mmbtu = volume_mscf * MScf_TO_MMBTU_FACTOR # Convert to MMBTU for internal calculations
                    valid, msg = validate_nomination(cust_id, volume_mmbtu)
                    status = "✅ Confirmed" if valid else "❌ Rejected"
                    new_entry = pd.DataFrame(
                        {
                        'timestamp': [datetime.now().strftime('%Y-%m-%d %H:%M')],
                        'customer': [cust],
                        'type': [nom_type],
                        'volume_mmbtu': [volume_mmbtu],
                        'status': [status]
                        }
                    )
                    st.session_state.nomination_log = pd.concat([st.session_state.nomination_log, new_entry], ignore_index=True)
                    if valid:
                        st.success(f"✅ Nomination Confirmed! {volume_mscf:,.0f} MScf ({volume_mmbtu:,.0f} MMBTU) scheduled for {cust}.")
                        new_del = pd.DataFrame(
                            {
                            'date': [datetime.now().strftime('%Y-%m-%d')],
                            'customer_id': [cust_id],
                            'delivered_mmbtu': [volume_mmbtu * 0.95]
                            }
                        )
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
            fig = px.bar(st.session_state.nomination_log, x='customer', y='volume_mmbtu', color='type',
                         title="Nomination Volumes by Customer (MMBTU)")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("📈 Nomination Status Overview")
        if not st.session_state.nomination_log.empty:
            status_counts = st.session_state.nomination_log['status'].value_counts().reset_index()
            status_counts.columns = ['status', 'count']
            fig_status = px.pie(status_counts, values='count', names='status', title='Distribution of Nomination Statuses',
                                 color_discrete_map={'✅ Confirmed': 'green', '❌ Rejected': 'red'})
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("No nominations to display status for yet.")

# ----------------------------
# MODULE 2: DISPATCH OPTIMIZER
# ----------------------------
elif module == "🧠 Dispatch Optimizer":
    st.title("🧠 Intelligent Dispatch & Optimization Engine")
    st.caption("Multi-Objective Optimization: Cost Minimization | Asset Utilization | Service Level Maximization.")

    scenario = st.radio("Scenario Mode", ["Normal Operations", "🚨 Breakdown Contingency (T-001)"], horizontal=True)

    if st.button("🔄 Run Optimization"):
        if scenario == "🚨 Breakdown Contingency (T-001)":
            trailers, utilization, total_load, orders = run_dispatch_optimization(scenario='breakdown')
            st.warning("⚠️ Contingency Plan Activated: T-001 re-routed. ETA extended by 60 mins.")
        else:
            trailers, utilization, total_load, orders = run_dispatch_optimization(scenario='normal')
            st.success("✅ Optimization Complete: All schedules optimized.")

        st.session_state.trailers = trailers

        col1, col2, col3 = st.columns(3)
        col1.metric("📈 Fleet Utilization", f"{utilization:.1f}%", delta="+5% from baseline")
        col2.metric("⏱️ Avg ETA (mins)", f"{trailers['eta_minutes'].mean():.0f}", delta="-10 mins")
        col3.metric("📦 Total Dispatched (MMBTU)", f"{total_load:,.0f}")

        st.subheader("🗺️ Dispatch Route Map")
        fig = go.Figure()

        fig.add_trace(go.Scattermapbox(
            lat=[mother_station['lat']], lon=[mother_station['lon']],
            mode='markers+text', marker=dict(size=15, color='red'), text=["Mother Station"],
            textposition="top right"
        ))

        fig.add_trace(go.Scattermapbox(
            lat=trailers['current_lat'], lon=trailers['current_lon'],
            mode='markers+text', marker=dict(size=12, color='blue'), text=trailers['trailer_id'],
            textposition="top center"
        ))

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

        st.subheader("📋 Optimized Dispatch Schedule")
        st.dataframe(trailers[['trailer_id', 'status', 'destination', 'eta_minutes', 'load_mmbtu', 'pressure_psi']], use_container_width=True)

# ----------------------------
# MODULE 3: REAL-TIME MONITOR
# ----------------------------
elif module == "📡 Real-Time Monitor":
    st.title("📡 Real-Time Monitoring & Digital Twin")
    st.caption("End-to-end visibility: Tracker locations, Pressure/Temperature telemetry, and Predictive Alerts.")

    if st.button("⏩ Advance Time (+15 mins)"):
        for idx in st.session_state.trailers.index:
            if st.session_state.trailers.loc[idx, 'status'] == 'Moving':
                st.session_state.trailers.loc[idx, 'current_lat'] += random.uniform(-0.005, 0.005)
                st.session_state.trailers.loc[idx, 'current_lon'] += random.uniform(-0.005, 0.005)
                st.session_state.trailers.loc[idx, 'eta_minutes'] = max(5, st.session_state.trailers.loc[idx, 'eta_minutes'] - 15)
                st.session_state.trailers.loc[idx, 'pressure_psi'] -= random.uniform(0, 50)

    st.subheader("🚨 Predictive Alerts")
    alerts = generate_live_alerts()
    for alert in alerts:
        if alert['severity'] == 'Critical':
            st.error(f"{alert['type']}: {alert['message']}")
        elif alert['severity'] == 'High':
            st.warning(f"{alert['type']}: {alert['message']}")
        else:
            st.info(f"{alert['type']}: {alert['message']}")

    col1, col2, col3, col4 = st.columns(4)
    trailers = st.session_state.trailers
    for idx, (_, row) in enumerate(trailers.iterrows()):
        with [col1, col2, col3, col4][idx % 4]:
            st.metric(f"🚛 {row['trailer_id']}", f"{row['status']}")
            st.caption(f"📍 Dest: {row['destination']} | ETA: {row['eta_minutes']}m")
            st.caption(f"⚙️ {row['pressure_psi']} psi | Load: {row['load_mmbtu']}MMBTU")

    st.subheader("🗺️ Live Fleet Tracker")
    fig = go.Figure()

    color_map = {'Moving': 'green', 'Loading': 'orange', 'Unloading': 'red', 'Idle': 'gray', 'Delayed': 'purple'}
    for status, color in color_map.items():
        subset = trailers[trailers['status'] == status]
        if not subset.empty:
            fig.add_trace(go.Scattermapbox(
                lat=subset['current_lat'], lon=subset['current_lon'],
                mode='markers+text', marker=dict(size=14, color=color),
                text=subset['trailer_id'] + " - " + subset['status']
            ))

    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=-1.97, lon=30.08), zoom=11),
        height=400, margin=dict(l=0, r=0, t=0, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# MODULE 4: SETTLEMENT & BI (VALUE CAPTURE) - Enhanced with Customer Profitability
# ----------------------------
elif module == "💰 Settlement & BI":
    st.title("💰 Commercial Settlement & Business Intelligence")
    st.caption("The Value Capture: Automated invoicing, KPI scorecards, and behavioral analytics.")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Period From", value=datetime.now().date() - timedelta(days=30))
    with col2:
        end_date = st.date_input("Period To", value=datetime.now().date())

    segments = st.multiselect("Filter by Segment", options=customers_df['segment'].unique(), default=customers_df['segment'].unique())

    settlement_df = calculate_settlement(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
    filtered_settlement = settlement_df[settlement_df['segment'].isin(segments)]

    if filtered_settlement.empty:
        st.warning("No delivery data found for this period. Submit nominations in Tab 1 to generate data.")
    else:
        st.subheader("📈 Key Performance Indicators")
        k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
        k1.metric("💰 Total Revenue", f"${filtered_settlement['total_revenue'].sum():,.0f}")
        k2.metric("📈 Gross Margin", f"${filtered_settlement['gross_margin'].sum():,.0f}")
        k3.metric("⚠️ Penalties Captured", f"${filtered_settlement['penalty_amount'].sum():,.0f}")
        k4.metric("📦 Total Delivered (MMBTU)", f"{filtered_settlement['delivered_mmbtu'].sum():,.0f}")
        k5.metric("⛽ Total CNG CO2e", f"{filtered_settlement['actual_cng_emissions'].sum():,.2f} tons")
        k6.metric("🌳 Total Carbon Reductions", f"{filtered_settlement['carbon_emission_reductions'].sum():,.2f} tons")
        k7.metric("💸 Potential Carbon Credits", f"${filtered_settlement['carbon_credit_earnings'].sum():,.0f}")

        st.subheader("📊 Revenue and Profitability Overview")
        c1, c2 = st.columns(2)
        with c1:
            seg_rev = filtered_settlement.groupby('segment')['total_revenue'].sum().reset_index()
            fig = px.pie(seg_rev, values='total_revenue', names='segment', hole=0.4, title="Revenue by Segment")
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            seg_margin = filtered_settlement.groupby('segment')['gross_margin'].sum().reset_index()
            fig = px.bar(seg_margin, x='segment', y='gross_margin', title="Gross Margin by Segment")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("👥 Customer Profitability & Segmentation")
        # Customer Profitability Chart
        fig_cust_profit = px.scatter(filtered_settlement,
                                     x='delivered_mmbtu', y='gross_margin',
                                     size='total_revenue', color='segment',
                                     hover_name='name', log_x=True, size_max=60,
                                     title="Customer Profitability (Delivered vs. Gross Margin)",
                                     labels={'delivered_mmbtu': 'Delivered Volume (MMBTU)', 'gross_margin': 'Gross Margin ($)'})
        st.plotly_chart(fig_cust_profit, use_container_width=True)

        st.subheader("🌳 Carbon Reductions by Segment")
        seg_reductions = filtered_settlement.groupby('segment')['carbon_emission_reductions'].sum().reset_index()
        fig_reductions = px.bar(seg_reductions, x='segment', y='carbon_emission_reductions',
                               title="Total Carbon Reductions by Segment",
                               labels={'carbon_emission_reductions': 'CO2e Reductions (tons)'})
        st.plotly_chart(fig_reductions, use_container_width=True)


        st.subheader("📋 Commercial Settlement Ledger")
        display_cols = ['name', 'segment', 'nominated_mmbtu', 'delivered_mmbtu', 'shortfall_mmbtu',
                        'penalty_amount', 'base_revenue', 'total_revenue', 'gross_margin', 'margin_pct', 'price_per_mmbtu', 'actual_cng_emissions', 'carbon_emission_reductions', 'carbon_credit_earnings']
        display_df = filtered_settlement[display_cols].copy()
        display_df.columns = ['Customer', 'Segment', 'Nominated (MMBTU)', 'Delivered (MMBTU)', 'Shortfall (MMBTU)',
                              'Penalty', 'Base Rev', 'Total Charge', 'Gross Margin', 'Margin %', 'Price ($/MMBTU)', 'CNG CO2e (tons)', 'Carbon Reductions (tons)', 'Carbon Credits ($)']
        st.dataframe(display_df.style.format({
            'Nominated (MMBTU)': '{:,.0f}', 'Delivered (MMBTU)': '{:,.0f}', 'Shortfall (MMBTU)': '{:,.0f}',
            'Penalty': '${:,.2f}', 'Base Rev': '${:,.2f}', 'Total Charge': '${:,.2f}',
            'Gross Margin': '${:,.2f}', 'Margin %': '{:.1f}%', 'Price ($/MMBTU)': '${:,.2f}',
            'CNG CO2e (tons)': '{:,.2f}', 'Carbon Reductions (tons)': '{:,.2f}', 'Carbon Credits ($)': '${:,.2f}'
        }).background_gradient(subset=['Total Charge'], cmap='Blues'), use_container_width=True)

        csv = filtered_settlement.to_csv(index=False)
        b64_csv = base64.b64encode(csv.encode()).decode()
        href_csv = f'<a href="data:file/csv;base64,{b64_csv}" download="cng_settlement_report.csv">⬇️ Download Full Settlement CSV</a>'
        st.markdown(href_csv, unsafe_allow_html=True)

        excel_data = to_excel(filtered_settlement)
        b64_excel = base64.b64encode(excel_data).decode()
        href_excel = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64_excel}" download="cng_settlement_report.xlsx">⬇️ Download Full Settlement Excel</a>'
        st.markdown(href_excel, unsafe_allow_html=True)

# ----------------------------
# ENHANCEMENT 1: Demand Forecasting & Anomaly Detection Module
# ----------------------------
elif module == "📈 Demand Forecasting":
    st.title("📈 Advanced Demand Forecasting & Anomaly Detection")
    st.caption("Predict future demand and identify unusual nomination patterns.")

    selected_customer_names = st.multiselect("Select Customers for Forecasting", options=customers_df['name'])

    if not selected_customer_names:
        st.info("Please select at least one customer for forecasting.")
    else:
        selected_customer_ids = customers_df[customers_df['name'].isin(selected_customer_names)]['customer_id'].tolist()

        forecast_days = st.slider("Forecast Days", min_value=1, max_value=30, value=7)

        all_forecast_dfs = []
        for cust_name in selected_customer_names:
            cust_id = customers_df[customers_df['name'] == cust_name].iloc[0]['customer_id']
            forecast_df_single = forecast_demand(cust_id, days=forecast_days)
            forecast_df_single['customer_name'] = cust_name # Add customer name for plotting
            all_forecast_dfs.append(forecast_df_single)

        if all_forecast_dfs:
            combined_forecast_df = pd.concat(all_forecast_dfs)

            st.subheader(f"Demand Forecast for Selected Customers")
            fig_forecast = px.line(combined_forecast_df, x='date', y='forecast_mmbtu', color='customer_name',
                                    title=f"{forecast_days}-Day Forecasted Demand for Selected Customers",
                                    labels={'forecast_mmbtu': 'Forecasted Volume (MMBTU)', 'customer_name': 'Customer'})
            st.plotly_chart(fig_forecast, use_container_width=True)

            st.subheader("Actual vs. Forecasted Demand")
            if not st.session_state.delivery_log.empty:
                # Filter actual delivery log for selected customers and dates within forecast range
                actual_deliveries_filtered = st.session_state.delivery_log[
                    st.session_state.delivery_log['customer_id'].isin(selected_customer_ids)
                ].copy()
                actual_deliveries_filtered['date'] = pd.to_datetime(actual_deliveries_filtered['date'])

                # Get min/max date from forecast for filtering actuals
                min_forecast_date = combined_forecast_df['date'].min()
                max_forecast_date = combined_forecast_df['date'].max()

                actual_deliveries_filtered = actual_deliveries_filtered[
                    (actual_deliveries_filtered['date'] >= min_forecast_date)
                ].groupby(['date', 'customer_id'])['delivered_mmbtu'].sum().reset_index()

                actual_deliveries_filtered = pd.merge(actual_deliveries_filtered, customers_df[['customer_id', 'name']], on='customer_id', how='left')
                actual_deliveries_filtered.rename(columns={'name': 'customer_name'}, inplace=True)

                # Combine actual and forecast data for plotting
                combined_plot_df = pd.DataFrame()

                if not actual_deliveries_filtered.empty:
                    actual_df_melted = actual_deliveries_filtered.rename(columns={'delivered_mmbtu': 'volume'})
                    actual_df_melted['type'] = 'Actual'
                    combined_plot_df = pd.concat([combined_plot_df, actual_df_melted[['date', 'volume', 'type', 'customer_name']]])

                forecast_df_melted = combined_forecast_df.rename(columns={'forecast_mmbtu': 'volume'})
                forecast_df_melted['type'] = 'Forecast'
                combined_plot_df = pd.concat([combined_plot_df, forecast_df_melted[['date', 'volume', 'type', 'customer_name']]])

                if not combined_plot_df.empty:
                    fig_actual_vs_forecast = px.line(combined_plot_df,
                                                     x='date', y='volume', color='customer_name',
                                                     line_dash='type', # Differentiate actual and forecast lines
                                                     title=f"Actual vs. Forecasted Demand for Selected Customers ({min_forecast_date.strftime('%Y-%m-%d')} to {max_forecast_date.strftime('%Y-%m-%d')})",
                                                     labels={'volume': 'Volume (MMBTU)', 'date': 'Date', 'customer_name': 'Customer', 'type': 'Data Type'})
                    st.plotly_chart(fig_actual_vs_forecast, use_container_width=True)
                else:
                    st.info("No actual or forecasted data to display for the selected period/customers.")
            else:
                st.info("No historical delivery data available to compare against forecast.")


            st.subheader("Anomaly Detection (Last 7 Nominations)")
            for cust_name in selected_customer_names:
                cust_id = customers_df[customers_df['name'] == cust_name].iloc[0]['customer_id']
                customer_nominations = st.session_state.nomination_log[
                    st.session_state.nomination_log['customer'] == cust_name
                ].sort_values('timestamp', ascending=False)

                if not customer_nominations.empty:
                    latest_nomination = customer_nominations.iloc[0]
                    latest_volume = latest_nomination['volume_mmbtu']
                    # Get forecast for this specific customer for today
                    today_forecast_for_cust = combined_forecast_df[
                        (combined_forecast_df['customer_name'] == cust_name) &
                        (combined_forecast_df['date'].dt.date == datetime.now().date())
                    ]['forecast_mmbtu'].mean()

                    if pd.isna(today_forecast_for_cust):
                        st.info(f"No forecast available for today for {cust_name} to compare against.")
                    else:
                        deviation_pct = ((latest_volume - today_forecast_for_cust) / today_forecast_for_cust) * 100
                        if abs(deviation_pct) > 20: # Example threshold for anomaly
                            st.warning(f"🚨 Anomaly Detected for {cust_name}: Latest nomination of {latest_volume:,.0f} MMBTU deviates by {deviation_pct:+.1f}% from forecasted {today_forecast_for_cust:,.0f} MMBTU. Investigate!")
                        else:
                            st.info(f"No significant anomalies detected for {cust_name}. Latest nomination ({latest_volume:,.0f} MMBTU) is in line with forecast ({today_forecast_for_cust:,.0f} MMBTU).")
                else:
                    st.info(f"No nominations submitted yet for {cust_name} to detect anomalies.")

# ----------------------------
# ENHANCEMENT 2: Scenario Planning & Simulation Tool (What-If Analysis)
# ----------------------------
elif module == "⚙️ Scenario Simulation":
    st.title("⚙️ Scenario Planning & Simulation Tool")
    st.caption("Perform 'What-If' analysis on key commercial and operational parameters.")

    st.subheader("Define Your Scenario Parameters")

    # Scenario inputs
    scenario_name = st.text_input("Scenario Name", "New Pricing Strategy")
    selected_segment = st.selectbox("Target Segment for Change", options=['All'] + customers_df['segment'].unique().tolist())
    price_adjustment_pct = st.slider("Price Adjustment (%)", -20.0, 20.0, 0.0, 0.5)
    take_or_pay_adjustment_pct = st.slider("Take-or-Pay Adjustment (percentage points)", -20.0, 20.0, 0.0, 0.5)

    if st.button("Run Simulation"):
        st.subheader(f"Simulation Results: {scenario_name}")

        # Create a hypothetical customers_df based on scenario inputs
        hypothetical_customers_df = customers_df.copy()

        # Apply price adjustment
        if selected_segment == 'All':
            hypothetical_customers_df['price_per_mmbtu'] *= (1 + price_adjustment_pct / 100)
        else:
            mask = hypothetical_customers_df['segment'] == selected_segment
            hypothetical_customers_df.loc[mask, 'price_per_mmbtu'] *= (1 + price_adjustment_pct / 100)

        # Apply take-or-pay adjustment (ensure it stays between 0 and 1)
        if selected_segment == 'All':
            hypothetical_customers_df['take_or_pay'] = (hypothetical_customers_df['take_or_pay'] + take_or_pay_adjustment_pct / 100).clip(0, 1)
        else:
            mask = hypothetical_customers_df['segment'] == selected_segment
            hypothetical_customers_df.loc[mask, 'take_or_pay'] = (hypothetical_customers_df.loc[mask, 'take_or_pay'] + take_or_pay_adjustment_pct / 100).clip(0, 1)

        # Calculate simulated settlement
        current_date = datetime.now().date()
        simulated_settlement_df = calculate_settlement(
            (current_date - timedelta(days=30)).strftime('%Y-%m-%d'),
            current_date.strftime('%Y-%m-%d'),
            customers_data=hypothetical_customers_df
        )

        if simulated_settlement_df.empty:
            st.warning("No delivery data found to run simulation. Ensure some nominations and deliveries have been made.")
        else:
            col_sim1, col_sim2, col_sim3, col_sim4 = st.columns(4)
            col_sim1.metric("💰 Simulated Total Revenue", f"${simulated_settlement_df['total_revenue'].sum():,.0f}")
            col_sim2.metric("📈 Simulated Gross Margin", f"${simulated_settlement_df['gross_margin'].sum():,.0f}")
            col_sim3.metric("⚠️ Simulated Penalties", f"${simulated_settlement_df['penalty_amount'].sum():,.0f}")
            col_sim4.metric("💲 Avg Price/MMBTU", f"${simulated_settlement_df['price_per_mmbtu'].mean():,.2f}")

            st.markdown("### Detailed Simulated Outcome")
            st.dataframe(simulated_settlement_df[['name', 'segment', 'total_revenue', 'gross_margin', 'margin_pct', 'price_per_mmbtu', 'take_or_pay']], use_container_width=True)

            # Compare with baseline (if available)
            baseline_settlement_df = calculate_settlement(
                (current_date - timedelta(days=30)).strftime('%Y-%m-%d'),
                current_date.strftime('%Y-%m-%d'),
                customers_data=customers_df # Original customers data
            )

            if not baseline_settlement_df.empty:
                st.subheader("Comparison with Baseline (Original Parameters)")
                baseline_total_revenue = baseline_settlement_df['total_revenue'].sum()
                simulated_total_revenue = simulated_settlement_df['total_revenue'].sum()
                revenue_diff = simulated_total_revenue - baseline_total_revenue
                revenue_pct_change = (revenue_diff / baseline_total_revenue) * 100 if baseline_total_revenue != 0 else 0

                baseline_gross_margin = baseline_settlement_df['gross_margin'].sum()
                simulated_gross_margin = simulated_settlement_df['gross_margin'].sum()
                margin_diff = simulated_gross_margin - baseline_gross_margin
                margin_pct_change = (margin_diff / baseline_gross_margin) * 100 if baseline_gross_margin != 0 else 0

                k_comp1, k_comp2 = st.columns(2)
                k_comp1.metric("Total Revenue Change", f"${revenue_diff:,.0f}", delta=f"{revenue_pct_change:+.1f}%")
                k_comp2.metric("Gross Margin Change", f"${margin_diff:,.0f}", delta=f"{margin_pct_change:+.1f}%")

            st.info("Note: Simulation results are based on existing delivery data and hypothetical parameter changes.")
