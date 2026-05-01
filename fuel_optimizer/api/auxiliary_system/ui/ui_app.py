import streamlit as st
import requests
import folium
from streamlit_folium import folium_static
import json
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="Intelligent Fuel Route Optimizer",
    page_icon="🛣️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS for Premium Look ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #ff3333;
        border: none;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    h1 {
        color: #ffffff;
        font-family: 'Inter', sans-serif;
    }
    .metric-card {
        background-color: #1e2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #30363d;
        text-align: center;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #00d4ff;
    }
    .metric-label {
        font-size: 14px;
        color: #8b949e;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
st.sidebar.title("⚙️ API Configuration")
api_url = st.sidebar.text_input("Backend Endpoint", "http://localhost:8000/api/plan-route/")
st.sidebar.markdown("---")
st.sidebar.info("This tool optimizes refueling stops along your route to minimize total cost.")

# --- Header ---
st.title("🛣️ Intelligent Fuel Route Optimizer")
st.markdown("Optimize your trip with data-driven fueling stops.")

# --- Input Section ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📍 Start Location")
    start_location = st.text_input("City, State", value="Los Angeles, CA", help="e.g. Los Angeles, CA")

with col2:
    st.subheader("🏁 Destination")
    end_location = st.text_input("End City, State", value="Las Vegas, NV", help="e.g. Las Vegas, NV")

# --- Action Button ---
if st.button("🚀 Calculate Optimal Route"):
    payload = {
        "start_location": start_location,
        "end_location": end_location
    }
    
    with st.spinner("🔍 Computing optimal route and fuel stops..."):
        start_time = time.time()
        try:
            response = requests.post(api_url, json=payload, timeout=30)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                # --- Success Metrics ---
                st.success(f"Route calculated successfully in {elapsed:.2f} seconds!")
                
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.markdown(f'<div class="metric-card"><div class="metric-value">{data["distance_km"]:.1f} km</div><div class="metric-label">Total Distance</div></div>', unsafe_allow_html=True)
                with m2:
                    st.markdown(f'<div class="metric-card"><div class="metric-value">{data["duration_minutes"]:.0f} min</div><div class="metric-label">Est. Duration</div></div>', unsafe_allow_html=True)
                with m3:
                    st.markdown(f'<div class="metric-card"><div class="metric-value">${data["fuel_cost_usd"]:.2f}</div><div class="metric-label">Total Fuel Cost</div></div>', unsafe_allow_html=True)
                with m4:
                    st.markdown(f'<div class="metric-card"><div class="metric-value">{len(data["refuel_stops"])}</div><div class="metric-label">Refuel Stops</div></div>', unsafe_allow_html=True)
                
                # --- Map Section ---
                st.subheader("🗺️ Route Map")
                
                # Map center and bounds
                resolved_start = data.get("resolved_start", {"lat": 34.05, "lng": -118.24})
                resolved_end = data.get("resolved_end", {"lat": 36.16, "lng": -115.13})
                m = folium.Map(location=[(resolved_start["lat"] + resolved_end["lat"])/2, (resolved_start["lng"] + resolved_end["lng"])/2], zoom_start=6, tiles="cartodbpositron")
                
                # Plot route line
                if "route_geometry" in data and data["route_geometry"]:
                    geojson_route = folium.GeoJson(data["route_geometry"], name="Route", style_function=lambda x: {'color': '#ff4b4b', 'weight': 5})
                    geojson_route.add_to(m)
                
                # Add Start/End markers
                folium.Marker([resolved_start["lat"], resolved_start["lng"]], popup="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)
                folium.Marker([resolved_end["lat"], resolved_end["lng"]], popup="End", icon=folium.Icon(color="red", icon="stop")).add_to(m)
                
                # Add Fuel Stop markers
                for stop in data["refuel_stops"]:
                    name = stop.get('Truckstop Name', 'Fuel Stop')
                    city = stop.get('City', '')
                    state = stop.get('State', '')
                    location = f" ({city}, {state})" if city and state else ""
                    popup_text = f"<b>{name}{location}</b><br>Price: ${stop['price']}/gal"
                    
                    folium.Marker(
                        [stop["lat"], stop["lng"]],
                        popup=folium.Popup(popup_text, max_width=300),
                        tooltip=f"{name}: ${stop['price']}/gal",
                        icon=folium.Icon(color="orange", icon="gas-pump", prefix="fa")
                    ).add_to(m)
                
                # Display Map
                folium_static(m, width=1000, height=600)
                
                # --- Raw Data Expander ---
                with st.expander("📦 View Raw API Response"):
                    st.json(data)
                    
            else:
                st.error(f"❌ API Error ({response.status_code}): {response.text}")
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to API. Is the server running at " + api_url + "?")
        except Exception as e:
            st.error(f"💥 An unexpected error occurred: {str(e)}")

# --- Footer ---
st.markdown("---")
st.markdown("© 2026 Intelligent Fuel Systems | Powered by Django & OSRM")
