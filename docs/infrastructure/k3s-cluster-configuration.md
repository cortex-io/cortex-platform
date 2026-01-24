# K3s Cluster Configuration

This document covers the k3s cluster infrastructure configuration for the Cortex platform.

## Cluster Overview

| Node | Role | IP Address |
|------|------|------------|
| k3s-master01 | control-plane, etcd, master | 10.88.145.190 |
| k3s-master02 | control-plane, etcd, master | 10.88.145.193 |
| k3s-master03 | control-plane, etcd, master | 10.88.145.196 |
| k3s-worker01 | worker | 10.88.145.191 |
| k3s-worker02 | worker | 10.88.145.192 |
| k3s-worker03 | worker | 10.88.145.194 |
| k3s-worker04 | worker | 10.88.145.195 |

## SSH Access

```bash
ssh k3s@<node-ip>
# Password: toor
```

## Internal Docker Registry Configuration

The cluster uses an internal Docker registry for custom images. All nodes must be configured to use HTTP (not HTTPS) for the internal registry.

### Registry Configuration File

Location: `/etc/rancher/k3s/registries.yaml`

```yaml
mirrors:
  docker.io:
    endpoint:
      - "http://10.88.145.196:30500"
      - "https://registry-1.docker.io"
  "10.43.170.72:5000":
    endpoint:
      - "http://10.43.170.72:5000"
  "docker-registry.cortex-chat.svc.cluster.local:5000":
    endpoint:
      - "http://docker-registry.cortex-chat.svc.cluster.local:5000"
```

### Applying Registry Configuration

To update the registry configuration across all nodes:

```bash
# Update all nodes
for NODE in 10.88.145.190 10.88.145.193 10.88.145.196 10.88.145.191 10.88.145.192 10.88.145.194 10.88.145.195; do
  sshpass -p 'toor' ssh -o StrictHostKeyChecking=no k3s@$NODE "echo '<config>' | sudo tee /etc/rancher/k3s/registries.yaml"
done

# Restart workers (can be parallel)
for NODE in 10.88.145.191 10.88.145.192 10.88.145.194 10.88.145.195; do
  sshpass -p 'toor' ssh k3s@$NODE "sudo systemctl restart k3s-agent" &
done
wait

# Restart masters (one at a time to maintain quorum)
for NODE in 10.88.145.190 10.88.145.193 10.88.145.196; do
  sshpass -p 'toor' ssh k3s@$NODE "sudo systemctl restart k3s"
  sleep 15
done
```

### Internal Registry Details

| Service | Namespace | ClusterIP | Port |
|---------|-----------|-----------|------|
| docker-registry | cortex-chat | 10.43.170.72 | 5000 |
| docker-registry-nodeport | cortex-chat | - | 30501 |

### Pushing Images to Internal Registry

```bash
# Tag the image
docker tag myimage:latest 10.43.170.72:5000/myimage:latest

# Push (from within cluster network or via NodePort)
docker push 10.43.170.72:5000/myimage:latest
```

### Available Images

Check available images in the registry:

```bash
kubectl exec -n cortex-chat deploy/docker-registry -- \
  ls /var/lib/registry/docker/registry/v2/repositories/
```

## Troubleshooting

### ImagePullBackOff - HTTP/HTTPS Mismatch

**Symptom:**
```
Failed to pull image "10.43.170.72:5000/image:latest":
http: server gave HTTP response to HTTPS client
```

**Solution:** Ensure `/etc/rancher/k3s/registries.yaml` is configured on the node and k3s has been restarted.

### ImagePullBackOff - Image Not Found

**Symptom:**
```
Failed to pull image: not found
```

**Solution:** Verify the image exists in the registry and is tagged correctly.

## Related Documentation

- [Tailscale DNS Configuration](./tailscale-dns-configuration.md)
- [Layer Activator Guide](./layer-activator-guide.md)
- [Monitoring Exporters](./monitoring-exporters.md)
