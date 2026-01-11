# Cortex Automation Daemons

## Overview

Automated cleanup and recovery systems deployed in the Cortex cluster to handle common operational issues without manual intervention.

## Deployed Daemons

### 1. Zombie Cleanup Daemon ⚰️
**Purpose:** Automatically detects and removes orphaned/stuck pods

**What it cleans:**
- **Unknown pods** older than 5 minutes (orphaned from node restarts)
- **CrashLoopBackOff pods** with >100 restarts

**Check interval:** 60 seconds

**Logs:**
```bash
kubectl logs -n cortex-system -l app=zombie-cleanup-daemon -f
```

**Example output:**
```
[Wed Dec 24 22:15:06 UTC 2025] Checking for zombie pods...
  ✓ No zombie pods found
  ✓ No excessive CrashLoop pods
```

---

### 2. Auto-Fix Daemon 🔧
**Purpose:** Automatically fixes common infrastructure issues

**What it fixes:**
- **Stuck volume attachments** (older than 5 minutes)
- **ContainerCreating pods** stuck for >10 minutes
- **ImagePullBackOff pods** stuck for >15 minutes

**Check interval:** 120 seconds (2 minutes)

**Logs:**
```bash
kubectl logs -n cortex-system -l app=auto-fix-daemon -f
```

**Example output:**
```
[Wed Dec 24 22:15:01 UTC 2025] Running auto-fix checks...
  → Checking for stuck volume attachments...
    Found stuck volumes:
      → Deleting csi-0b469c9593d173194c94d6e26c35138b5c2e3395861878cc83447a15540529be
volumeattachment.storage.k8s.io "..." deleted
    ✓ No stuck ContainerCreating pods
    ✓ No stuck ImagePullBackOff pods
```

---

## Permissions

Both daemons run under the `cortex-cleanup-sa` service account with these permissions:

```yaml
ClusterRole: cortex-cleanup-role
- pods: get, list, delete
- deployments/statefulsets: get, list, patch
- volumeattachments: get, list, delete, watch
- pods/log: get
```

---

## How It Works

### Zombie Cleanup Process
1. **Detect Unknown pods** - Query all pods with `status.phase=Unknown`
2. **Age check** - Only clean if >5 minutes old
3. **Force delete** - `kubectl delete pod --force --grace-period=0`
4. **CrashLoop check** - Find pods with >100 restarts
5. **Scale down** - Scale parent deployment to 0 replicas

### Auto-Fix Process
1. **Scan for issues** - Check volume attachments, pod status
2. **Age/threshold check** - Only fix if stuck beyond threshold
3. **Apply fix** - Delete stuck resources, restart pods
4. **Log action** - Record what was fixed

---

## Monitoring

### Check daemon status
```bash
kubectl get pods -n cortex-system | grep daemon
```

Expected output:
```
auto-fix-daemon-7d67f8f579-hvpsw         1/1     Running
zombie-cleanup-daemon-6d5bbd894-mm2ch    1/1     Running
```

### Watch real-time activity
```bash
# Zombie cleanup
stern -n cortex-system zombie-cleanup-daemon

# Auto-fix
stern -n cortex-system auto-fix-daemon

# Both together
stern -n cortex-system '(zombie|auto-fix)'
```

### View recent actions
```bash
# Last 100 lines from both daemons
kubectl logs -n cortex-system -l cortex.component=automation --tail=100
```

---

## Configuration

### Adjust check intervals

**Zombie cleanup interval:**
```bash
kubectl set env deployment/zombie-cleanup-daemon -n cortex-system CLEANUP_INTERVAL=120
```

**Auto-fix interval:**
```bash
kubectl set env deployment/auto-fix-daemon -n cortex-system FIX_INTERVAL=180
```

### Disable a daemon
```bash
# Scale to 0 to disable
kubectl scale deployment zombie-cleanup-daemon -n cortex-system --replicas=0

# Scale back to 1 to enable
kubectl scale deployment zombie-cleanup-daemon -n cortex-system --replicas=1
```

---

## Thresholds

| Issue Type | Threshold | Action |
|------------|-----------|--------|
| Unknown pod | 5 minutes | Force delete |
| CrashLoop pod | >100 restarts | Scale down deployment |
| Stuck volume | 5 minutes | Delete volumeattachment |
| ContainerCreating | 10 minutes | Restart pod |
| ImagePullBackOff | 15 minutes | Restart pod |

---

## Safety Features

1. **Age/threshold checks** - Never acts immediately, always waits for threshold
2. **No watch permission issues** - Graceful degradation if permissions missing
3. **Idempotent** - Safe to run multiple times
4. **Logging** - All actions logged with timestamps
5. **No data loss** - Only deletes pods/attachments, never data volumes

---

## Troubleshooting

### Daemon not cleaning up pods
```bash
# Check daemon logs for errors
kubectl logs -n cortex-system -l app=zombie-cleanup-daemon --tail=50

# Verify permissions
kubectl auth can-i delete pods --as=system:serviceaccount:cortex-system:cortex-cleanup-sa -A
```

### Auto-fix not deleting volumes
```bash
# Check for permission errors
kubectl logs -n cortex-system -l app=auto-fix-daemon --tail=50 | grep -i forbidden

# Re-apply RBAC
kubectl apply -f k8s/cleanup-daemons.yaml
```

### Daemon pod crashed
```bash
# Check events
kubectl describe pod -n cortex-system -l app=zombie-cleanup-daemon

# Restart daemon
kubectl rollout restart deployment zombie-cleanup-daemon -n cortex-system
```

---

## What Gets Cleaned Automatically

### After Node Restarts ✅
- Unknown pods (from lost node connections)
- Stuck volume attachments
- Pods stuck in ContainerCreating

### After Deployments ✅
- Failed pods stuck in ImagePullBackOff
- CrashLooping pods (if >100 restarts)

### Does NOT Clean ❌
- Running pods
- Recent pods (<5-15 min old depending on issue)
- Stateful resources (StatefulSets, PVCs, PVs)
- Pods with <100 restarts

---

## Integration with Preflight Check

The preflight check script now includes daemon health checks:

```bash
./scripts/preflight-check.sh
```

Output includes:
```
10. Checking Automation Daemons...
✓ Zombie cleanup daemon is Running
✓ Auto-fix daemon is Running
```

---

## Deployment

Deploy/update both daemons:
```bash
kubectl apply -f k8s/cleanup-daemons.yaml
```

This creates:
- `zombie-cleanup-daemon` deployment
- `auto-fix-daemon` deployment
- `cortex-cleanup-sa` service account
- `cortex-cleanup-role` cluster role
- `cortex-cleanup-binding` cluster role binding

---

## Benefits

### Before Automation 😞
- Manual cleanup of Unknown pods after every node restart
- Pods stuck in CrashLoop forever (803+ restarts observed)
- Volume attachments stuck preventing new pods
- Hours of manual troubleshooting

### After Automation 😊
- Automatic cleanup within 5-15 minutes
- No manual intervention needed
- Cluster self-heals from common issues
- Focus on real problems, not routine cleanup

---

## Metrics (Future Enhancement)

TODO: Export metrics for monitoring:
- Number of zombies cleaned per hour
- Number of auto-fixes applied per hour
- Most common issue types
- Time to remediation

Potential exporters:
- Prometheus metrics endpoint
- JSON logs for aggregation
- Events to Kubernetes event stream

---

## Related Documentation

- `docs/PREFLIGHT-PLAYBOOK.md` - Full operational playbook
- `coordination/config/zombie-cleanup-policy.json` - Policy configuration
- `coordination/config/auto-fix-policy.json` - Auto-fix rules
- `k8s/cleanup-daemons.yaml` - Kubernetes deployment manifest
