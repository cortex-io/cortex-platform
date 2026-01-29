#!/usr/bin/env python3
"""
Seed the Qdrant learning collections with successful routing patterns.

This script populates the routing_queries collection with known good
query->tool->layer mappings so similarity-based routing can work immediately.

Usage:
    python seed_learning.py [--qdrant-url URL]
"""

import asyncio
import argparse
import uuid
from datetime import datetime
from sentence_transformers import SentenceTransformer
import httpx

# Seed data: successful query patterns
SEED_PATTERNS = [
    # Client management queries
    {"query": "show me all connected clients", "tool": "get_clients", "layer": "execution-unifi-api"},
    {"query": "list all wireless clients", "tool": "get_clients", "layer": "execution-unifi-api"},
    {"query": "get active client list", "tool": "get_clients", "layer": "execution-unifi-api"},
    {"query": "show connected devices on the network", "tool": "get_clients", "layer": "execution-unifi-api"},
    {"query": "block client with mac address", "tool": "client_management", "layer": "execution-unifi-api"},
    {"query": "unblock the device", "tool": "client_management", "layer": "execution-unifi-api"},
    {"query": "kick this client off the network", "tool": "client_management", "layer": "execution-unifi-api"},

    # Device management queries
    {"query": "list all network devices", "tool": "get_devices", "layer": "execution-unifi-api"},
    {"query": "show me the access points", "tool": "get_devices", "layer": "execution-unifi-api"},
    {"query": "get all switches in the network", "tool": "get_devices", "layer": "execution-unifi-api"},
    {"query": "restart the main access point", "tool": "restart_device", "layer": "execution-unifi-api"},
    {"query": "reboot the switch in the server room", "tool": "restart_device", "layer": "execution-unifi-api"},
    {"query": "locate device u6-pro-01", "tool": "locate_device", "layer": "execution-unifi-api"},

    # Network management queries
    {"query": "list all networks", "tool": "get_networks", "layer": "execution-unifi-api"},
    {"query": "show the VLANs configured", "tool": "get_networks", "layer": "execution-unifi-api"},
    {"query": "get network configuration", "tool": "get_networks", "layer": "execution-unifi-api"},
    {"query": "create a new guest network", "tool": "create_network", "layer": "execution-unifi-api"},
    {"query": "add vlan 100 for IoT devices", "tool": "create_network", "layer": "execution-unifi-api"},

    # WiFi queries
    {"query": "list all wireless networks", "tool": "get_wlans", "layer": "execution-unifi-api"},
    {"query": "show SSIDs", "tool": "get_wlans", "layer": "execution-unifi-api"},
    {"query": "get wifi configuration", "tool": "get_wlans", "layer": "execution-unifi-api"},
    {"query": "create new SSID for guests", "tool": "create_wlan", "layer": "execution-unifi-api"},

    # Firewall queries
    {"query": "list firewall rules", "tool": "get_firewall_rules", "layer": "execution-unifi-api"},
    {"query": "show traffic rules", "tool": "get_firewall_rules", "layer": "execution-unifi-api"},
    {"query": "get security policies", "tool": "get_firewall_rules", "layer": "execution-unifi-api"},
    {"query": "create firewall rule to block port 22", "tool": "create_firewall_rule", "layer": "execution-unifi-api"},

    # Diagnostic queries (SSH layer)
    {"query": "troubleshoot connectivity issues", "tool": "diagnostics", "layer": "execution-unifi-ssh"},
    {"query": "diagnose the network problem", "tool": "diagnostics", "layer": "execution-unifi-ssh"},
    {"query": "debug slow internet", "tool": "diagnostics", "layer": "execution-unifi-ssh"},
    {"query": "show device logs", "tool": "get_logs", "layer": "execution-unifi-ssh"},
    {"query": "get system logs from the gateway", "tool": "get_logs", "layer": "execution-unifi-ssh"},
    {"query": "check routing table", "tool": "get_routes", "layer": "execution-unifi-ssh"},
    {"query": "show routes on the router", "tool": "get_routes", "layer": "execution-unifi-ssh"},
]


async def seed_qdrant(qdrant_url: str):
    """Seed Qdrant with successful routing patterns."""
    print(f"Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    print(f"Connecting to Qdrant at {qdrant_url}...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check connection
        resp = await client.get(f"{qdrant_url}/collections/routing_queries")
        if resp.status_code != 200:
            print(f"Error: Cannot access routing_queries collection: {resp.status_code}")
            return

        print(f"Generating embeddings for {len(SEED_PATTERNS)} patterns...")
        queries = [p["query"] for p in SEED_PATTERNS]
        embeddings = model.encode(queries, convert_to_numpy=True).tolist()

        # Prepare points
        points = []
        for i, pattern in enumerate(SEED_PATTERNS):
            point = {
                "id": str(uuid.uuid4()),
                "vector": embeddings[i],
                "payload": {
                    "query_id": str(uuid.uuid4()),
                    "query_text": pattern["query"],
                    "route_type": "keyword",  # These are keyword-routable patterns
                    "tool": pattern["tool"],
                    "execution_layer": pattern["layer"],
                    "confidence": 0.95,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True,  # Mark as successful
                    "success_rate": 1.0,  # 100% success rate
                    "sample_count": 10,  # Pretend we've seen this 10 times
                    "avg_latency_ms": 150,  # Fast execution time
                    "site": "default",
                }
            }
            points.append(point)

        print(f"Upserting {len(points)} points to Qdrant...")
        resp = await client.put(
            f"{qdrant_url}/collections/routing_queries/points",
            json={"points": points},
            params={"wait": "true"}
        )

        if resp.status_code in [200, 201]:
            print(f"Successfully seeded {len(points)} routing patterns!")
        else:
            print(f"Error: {resp.status_code} - {resp.text}")

        # Verify
        resp = await client.post(
            f"{qdrant_url}/collections/routing_queries/points/count",
            json={"exact": True}
        )
        count = resp.json().get("result", {}).get("count", 0)
        print(f"Total points in routing_queries: {count}")


def main():
    parser = argparse.ArgumentParser(description="Seed Qdrant learning collections")
    parser.add_argument(
        "--qdrant-url",
        default="http://localhost:6333",
        help="Qdrant URL (default: http://localhost:6333)"
    )
    args = parser.parse_args()

    asyncio.run(seed_qdrant(args.qdrant_url))


if __name__ == "__main__":
    main()
