"""c-top - Cortex Operations Dashboard

htop-style monitoring for the Cortex platform.

Layers:
  1 - Cluster: K8s resources, services, chat layer metrics
  2 - Network: Tailscale mesh, Traefik ingress
  3 - Workers: htop-style agent/task process list
  4 - Fabric: MCP servers, Qdrant, routing patterns
"""

__version__ = "0.1.0"
