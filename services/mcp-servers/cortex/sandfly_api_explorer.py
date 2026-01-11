#!/usr/bin/env python3
"""
Sandfly API Explorer - Daryl-1
Systematically explores and documents the Sandfly Security API
"""
import requests
import json
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SandflyExplorer:
    def __init__(self):
        self.base_url = "https://10.88.140.176/v4"
        self.username = "admin"
        self.password = "emphasize-art-nibble-arguable-paradox-flick-unpack"
        self.token = None
        self.endpoints_found = {}

    def authenticate(self):
        """Authenticate and get access token"""
        print(f"\n{'='*80}")
        print(f"AUTHENTICATING TO SANDFLY API")
        print(f"{'='*80}")

        url = f"{self.base_url}/auth/login"
        payload = {
            "username": self.username,
            "password": self.password
        }

        try:
            response = requests.post(url, json=payload, verify=False, timeout=10)
            print(f"POST {url}")
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                print(f"✓ Authentication successful")
                print(f"Token preview: {self.token[:20]}...")
                print(f"Response keys: {list(data.keys())}")
                return True
            else:
                print(f"✗ Authentication failed: {response.text[:200]}")
                return False
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False

    def headers(self):
        """Get request headers"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def explore_endpoint(self, endpoint, method="GET", payload=None, params=None):
        """Explore a single endpoint"""
        url = f"{self.base_url}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers(), params=params, verify=False, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=self.headers(), json=payload, verify=False, timeout=10)
            else:
                return None

            print(f"\n{method} {endpoint}")
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"✓ Success - Response type: {type(data).__name__}")

                    if isinstance(data, dict):
                        print(f"  Keys: {list(data.keys())[:10]}")
                        if 'data' in data and isinstance(data['data'], list):
                            print(f"  Data items: {len(data['data'])}")
                            if data['data']:
                                print(f"  First item keys: {list(data['data'][0].keys())[:10]}")
                        if 'total' in data:
                            print(f"  Total count: {data['total']}")
                    elif isinstance(data, list):
                        print(f"  List length: {len(data)}")
                        if data:
                            print(f"  First item keys: {list(data[0].keys())[:10]}")

                    return {
                        "endpoint": endpoint,
                        "method": method,
                        "status": response.status_code,
                        "response": data,
                        "headers": dict(response.headers)
                    }
                except json.JSONDecodeError:
                    print(f"  Response (text): {response.text[:200]}")
                    return {
                        "endpoint": endpoint,
                        "method": method,
                        "status": response.status_code,
                        "response": response.text[:500],
                        "headers": dict(response.headers)
                    }
            else:
                print(f"✗ Failed: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"✗ Error: {e}")
            return None

    def comprehensive_discovery(self):
        """Systematically discover all API endpoints"""
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE API DISCOVERY")
        print(f"{'='*80}")

        # Known endpoints from current exporter
        endpoints_to_test = [
            # System/Info
            ("/version", "GET", None, None),
            ("/health", "GET", None, None),
            ("/status", "GET", None, None),
            ("/info", "GET", None, None),
            ("/stats", "GET", None, None),
            ("/system", "GET", None, None),

            # Hosts
            ("/hosts", "GET", None, {"page": 1, "size": 10}),
            ("/hosts", "POST", {"filter": {}, "page": 1, "size": 10}, None),
            ("/hosts/summary", "GET", None, None),
            ("/hosts/stats", "GET", None, None),

            # Results/Scans
            ("/results", "POST", {"filter": {}, "page": 1, "size": 10}, None),
            ("/results", "GET", None, {"page": 1, "size": 10}),
            ("/results/summary", "GET", None, None),
            ("/results/stats", "GET", None, None),

            # Alerts
            ("/alerts", "GET", None, {"page": 1, "size": 10}),
            ("/alerts", "POST", {"filter": {}, "page": 1, "size": 10}, None),
            ("/alerts/summary", "GET", None, None),
            ("/alerts/active", "GET", None, None),

            # Sandboxes
            ("/sandboxes", "GET", None, None),
            ("/sandboxes", "POST", {"filter": {}, "page": 1, "size": 10}, None),
            ("/sandboxes/stats", "GET", None, None),

            # Policies
            ("/policies", "GET", None, None),
            ("/policies/summary", "GET", None, None),

            # Schedules
            ("/schedules", "GET", None, None),
            ("/schedules", "POST", {"filter": {}, "page": 1, "size": 10}, None),

            # Users
            ("/users", "GET", None, None),
            ("/users/me", "GET", None, None),

            # Activity/Audit
            ("/activity", "GET", None, {"page": 1, "size": 10}),
            ("/audit", "GET", None, {"page": 1, "size": 10}),

            # Tags/Categories
            ("/tags", "GET", None, None),
            ("/categories", "GET", None, None),

            # Metrics (might expose internal metrics)
            ("/metrics", "GET", None, None),
            ("/prometheus", "GET", None, None),
        ]

        print(f"\nTesting {len(endpoints_to_test)} potential endpoints...")

        for endpoint, method, payload, params in endpoints_to_test:
            result = self.explore_endpoint(endpoint, method, payload, params)
            if result:
                self.endpoints_found[endpoint] = result

        print(f"\n{'='*80}")
        print(f"DISCOVERY COMPLETE")
        print(f"{'='*80}")
        print(f"Found {len(self.endpoints_found)} working endpoints")

    def save_results(self, filename):
        """Save exploration results to file"""
        with open(filename, 'w') as f:
            json.dump(self.endpoints_found, f, indent=2, default=str)
        print(f"\n✓ Results saved to: {filename}")

if __name__ == "__main__":
    explorer = SandflyExplorer()

    if explorer.authenticate():
        explorer.comprehensive_discovery()
        explorer.save_results("/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/sandfly_api_discovery.json")

        print("\n" + "="*80)
        print("API EXPLORATION COMPLETE")
        print("="*80)
        print(f"Working endpoints discovered: {len(explorer.endpoints_found)}")
        print("\nNext: Review sandfly_api_discovery.json and create comprehensive documentation")
    else:
        print("\n✗ Failed to authenticate - cannot proceed with discovery")
