---
title: "From Monolithic LLM to Serverless Layer Fabric: Building AI That Scales to Zero"
date: 2026-01-25
description: "How I evolved from a single UniFi LLM to a composable AI architecture where every capability is a serverless layer."
tags: ["ai", "kubernetes", "unifi", "serverless", "keda", "homelab"]
draft: true
---

# From Monolithic LLM to Serverless Layer Fabric

*Building AI infrastructure that sleeps when you don't need it.*

## The Problem

I wanted Claude-level AI capabilities for my homelab infrastructure—specifically for managing my UniFi network. But running a 7B parameter model 24/7 on my k3s cluster would eat 6-8GB of RAM just sitting idle, waiting for the occasional "block this client" command.

That's wasteful. And it doesn't scale.

## The Journey

### Stage 1: The Obvious Approach

My first instinct was straightforward: fine-tune a model on UniFi documentation, deploy it with vLLM, and call it a day.

```
User Query → Fine-tuned LLM → UniFi API → Result
```

Simple. But expensive. That LLM would be burning resources even when no one was asking it anything.

### Stage 2: Layer Stacks

I'd already built a "Layer Activator" pattern for my Cortex project—serverless stacks that scale to zero via KEDA. Each domain (network, k8s, security) gets its own stack that wakes on demand.

So I thought: what if the LLM is just another component in the stack?

```
┌─────────────────────────────────────────┐
│           NETWORK STACK                  │
├─────────────────────────────────────────┤
│  UniFi LLM (replaces MoE Router)        │
│  ↓                                       │
│  Qdrant (vector memory)                 │
│  ↓                                       │
│  UniFi MCP (tool execution)             │
│  ↓                                       │
│  Telemetry                              │
└─────────────────────────────────────────┘
         KEDA: Scales 0→1→0
```

Better. The whole stack sleeps when idle. But there's still a problem: when it wakes, I'm loading a 3GB model just to route "list clients" to an API call.

### Stage 3: The Insight

Here's the key realization:

**90% of my queries are simple.**

- "Block client aa:bb:cc:dd:ee:ff" → pattern match → API call
- "Show me all devices" → pattern match → API call
- "Restart the AP in the kitchen" → pattern match → API call

These don't need an LLM at all. They need a regex and a REST client.

Only 10% of queries require actual reasoning:
- "Why is the WiFi slow in the office?"
- "What client is causing network issues?"
- "Help me troubleshoot the guest network"

So why load a multi-gigabyte model for every query?

### Stage 4: Layer Fabric

The architecture inverted. Instead of "LLM per domain," I built "capability per layer":

```
┌─────────────────────────────────────────────────────────────┐
│                    QUERY                                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ACTIVATOR (Always On, ~128MB)                   │
│  • Keyword routing (90% of queries)                          │
│  • Wake appropriate layers                                   │
│  • Proxy to execution                                        │
└─────────────────────────────┬───────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  REASONING    │    │    MEMORY     │    │  EXECUTION    │
│  (Scale 0→1)  │    │  (Always On)  │    │  (Scale 0→1)  │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ Classifier    │    │   Qdrant      │    │  UniFi API    │
│  (0.5B)       │    │   ~512MB      │    │   ~200MB      │
│               │    │               │    │               │
│ SLM (3.8B)    │    │               │    │  SSH Gateway  │
│  ~2.5GB       │    │               │    │   ~100MB      │
└───────────────┘    └───────────────┘    └───────────────┘
```

Each capability is its own layer:
- **Routing** stays on (tiny footprint)
- **Memory** stays on (vectors persist learning)
- **Reasoning** wakes only for complex queries
- **Execution** wakes only when there's work to do

## The Numbers

| State | Memory | What's Active |
|-------|--------|---------------|
| **Idle** | ~640MB | Activator + Qdrant |
| **Simple Query** | ~840MB | + API Execution |
| **Complex Query** | ~3.3GB | + SLM Reasoning |

Compared to always-on:

| Approach | Idle Memory | Active Memory |
|----------|-------------|---------------|
| Monolithic LLM | 6-8GB | 6-8GB |
| Layer Fabric | 640MB | 3.3GB |

**That's 85%+ memory savings when idle.**

## Cold Start Reality

The trade-off is cold start latency:

| Layer | Cold Start |
|-------|------------|
| Execution (API) | ~3s |
| Execution (SSH) | ~3s |
| Classifier (0.5B) | ~5s |
| SLM (3.8B) | ~12s |

For a "block this client" command that hits the keyword router:
- **Warm path**: ~200ms (keyword match + API call)
- **Cold path**: ~3.5s (wake execution layer + API call)

For a complex query requiring reasoning:
- **Warm path**: ~2s (SLM inference + execution)
- **Cold path**: ~15s (wake SLM + inference + execution)

Is 15 seconds acceptable for "why is WiFi slow"? For my homelab, absolutely. The alternative is 24/7 resource consumption for queries I might make twice a day.

## The Learning Loop

Here's where it gets interesting. Every operation feeds back:

```
Query → Tool → Outcome → Qdrant
```

The Qdrant layer stores:
- Query embeddings
- Which tool was selected
- Whether it succeeded
- Timestamp and context

Next time a similar query comes in:
1. Embed the query
2. Vector similarity search in Qdrant
3. If high match → skip LLM, use cached tool selection
4. If low match → route to SLM for reasoning

Over time:
- Week 1: 10% queries skip LLM (keyword matches only)
- Week 4: 40% queries skip LLM (learned patterns)
- Week 12: 70%+ queries skip LLM (comprehensive coverage)

**The system gets faster the more you use it.**

## What's Next

This architecture isn't UniFi-specific. The pattern applies to any domain:

```
Domain → [Activator] → [Reasoning Layers] → [Execution Layers] → [Memory]
```

I'm extending this to:
- **Proxmox** (VM management)
- **Kubernetes** (cluster operations)
- **Security** (vulnerability scanning, compliance)

The vision: a unified AI fabric where I can ask "create a VM, deploy a k8s cluster, and set up monitoring" and the appropriate layers wake, coordinate, and execute.

## Try It Yourself

The code is open source: [github.com/ry-ops/unifi-layer-fabric](https://github.com/ry-ops/unifi-layer-fabric)

Prerequisites:
- k8s cluster (k3s works great)
- KEDA + HTTP Add-on
- ~4GB RAM available
- UniFi controller

```bash
# Deploy with ArgoCD
kubectl apply -f argocd/applicationset.yaml
```

Or follow the [Quick Start Guide](https://github.com/ry-ops/unifi-layer-fabric/blob/main/docs/QUICKSTART.md).

## Conclusion

The key insight: **AI doesn't need to be always-on to be useful.**

By decomposing capabilities into serverless layers, you get:
- 85%+ memory savings when idle
- Sub-second response for simple queries
- Full reasoning capability when needed
- Continuous learning from operations

It's not about having the biggest model. It's about having the right capability at the right time.

---

*Follow my homelab journey at [ry-ops.dev](https://ry-ops.dev) or connect on [GitHub](https://github.com/ry-ops).*
