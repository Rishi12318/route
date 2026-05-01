# Intelligent Fuel Route Optimizer

### Techniques Used
- **Real-World Routing**: Uses the OSRM (Open Source Routing Machine) API to calculate the precise driving route and polyline geometry between start and destination coordinates.
- **Geocoding & Text-Based Input**: Integrates an offline/in-memory geocoding system to allow users to input simple text locations such as "New York, NY" and map them to latitude and longitude.
- **Greedy Look-Ahead Algorithm**: Projects ahead along the route up to the vehicle's maximum range to identify the cheapest fuel stations and reduce fuel cost.
- **Spatial Data Filtering**: Filters and assigns corridor fuel stations based on haversine distance to narrow down a large station set efficiently.
- **Interactive Visualization**: Uses Leaflet.js to render the route polyline, optimized refueling stops, and calculated fuel cost in real time.

**Tech Stack:** Python, Django REST Framework, JavaScript, Leaflet.js, OSRM API, HTML, CSS.

