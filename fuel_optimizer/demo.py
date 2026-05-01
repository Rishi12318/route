import urllib.request
import json

url = 'http://127.0.0.1:8000/api/plan-route/'
payload = {
    "start_location": "Houston, TX",
    "end_location": "Miami, FL"
}

# Convert payload to bytes
data = json.dumps(payload).encode('utf-8')

# Create the POST request
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

print("Sending Request to API...")
try:
    # Send the request and read the response
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())
        
        # We delete the massive route_geometry from the printout so it's easier to read
        if "route_geometry" in result:
            del result["route_geometry"]
            
        print("\n--- API RESPONSE ---")
        print(json.dumps(result, indent=2))
        
except Exception as e:
    print("Error:", e)
    print("Make sure your Django server is running! (python manage.py runserver)")
