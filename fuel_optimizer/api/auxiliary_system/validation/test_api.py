import requests
import json
import time
import argparse
from typing import List, Dict, Any

class APIValidator:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.results = []
        self.stats = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "times": []
        }

    def run_test(self, name: str, payload: Dict[str, Any], expected_status: int = 200, logic_check=None):
        self.stats["total_tests"] += 1
        t0 = time.time()
        try:
            r = requests.post(self.endpoint, json=payload, timeout=15)
            elapsed = (time.time() - t0) * 1000
            self.stats["times"].append(elapsed)
            
            success = (r.status_code == expected_status)
            error_msg = ""
            
            if success and logic_check and r.status_code == 200:
                logic_errors = logic_check(r.json())
                if logic_errors:
                    success = False
                    error_msg = "; ".join(logic_errors)
            elif not success:
                error_msg = f"Expected {expected_status}, got {r.status_code}. Response: {r.text[:100]}"

            if success:
                self.stats["passed"] += 1
                self.results.append({"test_name": name, "status": "PASS", "time_ms": round(elapsed, 2)})
            else:
                self.stats["failed"] += 1
                self.results.append({
                    "test_name": name, 
                    "status": "FAIL", 
                    "expected": str(expected_status), 
                    "actual": str(r.status_code),
                    "error_message": error_msg
                })
                
        except Exception as e:
            self.stats["failed"] += 1
            self.results.append({"test_name": name, "status": "ERROR", "error_message": str(e)})

    def generate_report(self, output_path: str):
        avg_time = sum(self.stats["times"]) / len(self.stats["times"]) if self.stats["times"] else 0
        p95_time = sorted(self.stats["times"])[int(len(self.stats["times"])*0.95)] if self.stats["times"] else 0
        
        report = {
            "test_summary": {
                "total_tests": self.stats["total_tests"],
                "passed": self.stats["passed"],
                "failed": self.stats["failed"],
                "execution_time_seconds": round(sum(self.stats["times"])/1000, 2)
            },
            "performance_metrics": {
                "avg_response_time_ms": round(avg_time, 2),
                "p95_response_time_ms": round(p95_time, 2),
                "max_response_time_ms": round(max(self.stats["times"], default=0), 2),
                "min_response_time_ms": round(min(self.stats["times"], default=0), 2)
            },
            "failed_tests": [r for r in self.results if r["status"] in ("FAIL", "ERROR")],
            "system_classification": "Production Ready" if self.stats["failed"] == 0 and p95_time < 2000 else "Needs Improvement",
            "recommendations": []
        }
        
        if self.stats["failed"] > 0:
            report["recommendations"].append("Fix failing functional tests")
        if p95_time > 2000:
            report["recommendations"].append("Optimize routing/filtering performance")

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        return report

def validate_logic(data: Dict[str, Any]) -> List[str]:
    errors = []
    if data.get("distance_km", 0) < 0: errors.append("Negative distance")
    if data.get("fuel_cost_usd", 0) < 0: errors.append("Negative fuel cost")
    
    # Distance/Duration sanity check
    if data.get("distance_km", 0) > 0:
        avg_speed = data["distance_km"] / (data["duration_minutes"] / 60)
        if not (30 < avg_speed < 150):
            errors.append(f"Implausible speed: {avg_speed:.1f} km/h")
            
    # Refuel logic
    dist_miles = data.get("distance_km", 0) / 1.60934
    if dist_miles > 500 and not data.get("refuel_stops"):
        errors.append("Long route (>500 miles) but no refuel stops returned")
        
    return errors

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://localhost:8000/api/plan-route/")
    parser.add_argument("--report", default="validation_report.json")
    args = parser.parse_args()

    v = APIValidator(args.endpoint)
    
    # 1. Functional Tests
    v.run_test("Valid Short Route (LA to Anaheim)", 
               {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 33.8366, "end_lng": -117.9143}, 
               logic_check=validate_logic)
    
    v.run_test("Valid Long Route (LA to Las Vegas)", 
               {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 36.1699, "end_lng": -115.1398}, 
               logic_check=validate_logic)

    v.run_test("Cross Country (LA to NY)", 
               {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 40.7128, "end_lng": -74.0060}, 
               logic_check=validate_logic)

    # 2. Validation Tests
    v.run_test("Invalid Latitude (95)", 
               {"start_lat": 95.0, "start_lng": -118.2437, "end_lat": 36.1699, "end_lng": -115.1398}, 
               expected_status=400)
    
    v.run_test("Missing Parameter", 
               {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 36.1699}, 
               expected_status=400)

    v.run_test("Same Start/End", 
               {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 34.0522, "end_lng": -118.2437}, 
               logic_check=validate_logic)

    # 3. Concurrent/Stress
    for i in range(5):
        v.run_test(f"Concurrency Test {i+1}", 
                   {"start_lat": 34.0522, "start_lng": -118.2437, "end_lat": 36.1699, "end_lng": -115.1398}, 
                   logic_check=validate_logic)

    report = v.generate_report(args.report)
    print(f"\n✅ Validation complete. Passed: {report['test_summary']['passed']}/{report['test_summary']['total_tests']}")
    print(f"📊 P95 Response Time: {report['performance_metrics']['p95_response_time_ms']} ms")
    print(f"📝 Report saved to: {args.report}")
