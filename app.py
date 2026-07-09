
# app.py - Complete CNG Commercial Prototype (All 4 Modules)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import base64
import random
import matplotlib.pyplot as plt # Added to resolve ImportError for background_gradient
import io # Added for Excel export

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
        'load_mmbtu': [1200, 800, 900, 0] # Changed from load_kg to load_mmbtu
    })

if 'nomination_log' not in st.session_state:
    st.session_state.nomination_log = pd.DataFrame(columns=[
        'timestamp', 'customer', 'type', 'volume_mmbtu', 'status' # Changed
    ])

if 'delivery_log' not in st.session_state:
    # This will be fed by the Dispatch module
    st.session_state.delivery_log = pd.DataFrame(columns=[
        'date', 'customer_id', 'delivered_mmbtu' # Changed
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
        'price_per_mmbtu': [1.85, 1.90, 1.75, 2.50, 2.45, 2.55, 2.20, 2.30, 1.95, 2.15], # Changed from base_price
        'take_or_pay': [0.80, 0.80, 0.85, 0.0, 0.0, 0.0, 0.0, 0.0, 0.75, 0.0],
        'mdq_mmbtu': [2000, 1800, 2200, 800, 750, 900, 500, 450, 1600, 400], # Changed from mdq_kg
        'lat': [-1.94, -1.99, -2.02, -1.96, -1.92, -1.95, -1.93, -1.91, -2.10, -1.89],
        'lon': [30.06, 30.12, 29.98, 30.08, 30.14, 30.05, 30.09, 30.11, 29.95, 30.15]
    })
    return customers

customers_df = load_static_data()
mother_station = {'lat': -1.9441, 'lon': 30.0619}

# ----------------------------
# 4. CORE FUNCTIONS FOR EACH MODULE
# ----------------------------

def validate_nomination(customer_id, volume_mmbtu): # Changed parameter name
    """Checks MDQ limit for customer."""
    customer = customers_df[customers_df['customer_id'] == customer_id]
    if customer.empty:
        return False, "Customer not found."
    mdq = customer.iloc[0]['mdq_mmbtu'] # Changed column name
    if volume_mmbtu > mdq: # Changed variable name
        # Original logic removed as per request to remove MDQ limit restriction
        pass # No validation needed if MDQ limit is removed as a hard restriction
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
    total_load = trailers['load_mmbtu'].sum() # Changed column name

    # Simulate a dispatched route (for map)
    dispatched_orders = []
    for _, row in trailers.iterrows():
        if row['destination'] != 'Mother Station':
            dispatched_orders.append({
                'trailer': row['trailer_id'],
                'to': row['destination'],
                'eta': row['eta_minutes'],
                'load': row['load_mmbtu'] # Changed column name
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


def get_customer_crm_data(nomination_log_df, delivery_log_df, customers_df):
    """Processes historical nomination and delivery data for CRM insights per customer."""
    if nomination_log_df.empty and delivery_log_df.empty:
        return pd.DataFrame(columns=['date', 'customer_id', 'customer_name', 'segment', 'nominated_mmbtu', 'delivered_mmbtu'])

def predict_customer_demand(customer_name, nomination_log_df, periods=7):
    """Generates a demand forecast for a specific customer using Prophet."""
    customer_df = nomination_log_df[nomination_log_df['customer'] == customer_name].copy()
    if customer_df.empty or len(customer_df) < 2 or 'timestamp' not in customer_df.columns or 'volume_mmbtu' not in customer_df.columns:
        return pd.DataFrame(columns=['ds', 'yhat', 'yhat_lower', 'yhat_upper'])
    df_prophet = customer_df.copy()
    df_prophet['timestamp'] = pd.to_datetime(df_prophet['timestamp'])
    df_prophet['ds'] = df_prophet['timestamp'].dt.to_period('D').dt.to_timestamp()
    # Aggregate total daily volume for the specific customer
    daily_demand = df_prophet.groupby('ds')['volume_mmbtu'].sum().reset_index()
    daily_demand.rename(columns={'volume_mmbtu': 'y'}, inplace=True)
    if len(daily_demand) < 2: # Prophet needs at least two data points after aggregation
        return pd.DataFrame(columns=['ds', 'yhat', 'yhat_lower', 'yhat_upper'])
    # Initialize and fit the Prophet model
    model = Prophet(seasonality_mode='multiplicative', daily_seasonality=True)
    model.fit(daily_demand)
    # Create a future dataframe for predictions
    future = model.make_future_dataframe(periods=periods)
    # Make predictions
    forecast = model.predict(future)
    return forecast


