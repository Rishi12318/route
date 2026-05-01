# Intelligent Fuel Route Optimization API - Auxiliary System

## Overview
This system provides the data processing pipeline, interactive UI, and validation suite for the Fuel Route Optimization backend. It leverages OSRM for real-road routing and a greedy look-ahead algorithm for fuel stop optimization.

## System Architecture
The system consists of three main modules:
1. **Data Preprocessing**: Geocodes raw fuel price data and creates a spatial index for the API.
2. **Interactive UI**: A premium Streamlit dashboard for visualizing routes and fuel stops.
3. **Validation Suite**: Automated testing of API correctness, performance, and boundary cases.

## Key Features
- **Real-Road Routing**: Uses OSRM API for accurate driving geometry.
- **Cost Minimization**: Greedy look-ahead algorithm ensures fuel is bought at the cheapest possible locations within range.
- **Geocoding**: Offline US city geocoder converts address data to coordinates without external API calls.
- **Interactive Visualization**: Full Folium map integration showing the route and recommended gas stations.

## Technical Stack
- **Backend**: Django 5.2, Django REST Framework
- **Data**: Pandas, NumPy
- **UI**: Streamlit, Folium
- **Routing**: OSRM (Open Source Routing Machine)

## Performance
- **Preprocessing**: < 2s for 8k+ rows.
- **API Response**: ~500ms - 1500ms (depending on route length).
- **Filtering**: Efficient corridor-based station selection.
