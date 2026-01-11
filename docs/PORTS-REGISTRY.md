# Cortex Ports Registry

**CRITICAL**: This file must be manually updated whenever Cortex creates any service that uses a port.

## Active Port Assignments

| Port | Service | Status | Configuration | Date Assigned | Notes |
|------|---------|--------|---------------|---------------|-------|
| 9000 | API Dashboard | ✅ Active | `.env` (API_PORT) | 2025-11-27 | Main dashboard and API server |

## Reserved Ports (Not Yet Used)

| Port | Reserved For | Date Reserved | Notes |
|------|-------------|---------------|-------|
| - | - | - | No reserved ports |

## Port Change History

| Date | Port | Service | Change Type | Reason | Changed By |
|------|------|---------|-------------|--------|------------|
| 2025-11-27 | 9000 | API Dashboard | Moved from 5001 | Conflict with other apps | User request |

## Retired Ports

| Port | Service | Active Dates | Reason for Retirement |
|------|---------|--------------|----------------------|
| 5001 | API Dashboard | Unknown - 2025-11-27 | Moved to 9000 due to port conflicts |
| 3000 | API Dashboard (old) | Unknown - 2025-11-27 | Consolidated to port 9000 |

---

## Port Assignment Rules

### Before Assigning a New Port

1. **Check Availability**:
   ```bash
   lsof -i :PORT_NUMBER
   # If empty, port is available
   ```

2. **Choose Safe Port Range**:
   - **Recommended**: 9000-9999 (application servers)
   - **Alternative**: 8000-8999 (development servers)
   - **Avoid**: 3000, 5000, 5001, 8080, 8888 (commonly used by other apps)

3. **Get Approval**:
   - All port assignments require critical task approval
   - See `docs/PORT-POLICY.md` for approval process

4. **Update This File**:
   - Add to "Active Port Assignments" table
   - Document in "Port Change History"

### When Adding a New Service

If Cortex needs to create a new service that requires a port:

1. **Select Next Available Port**:
   ```bash
   # Find first available port in range
   for port in {9001..9010}; do
     if ! lsof -i :$port > /dev/null 2>&1; then
       echo "Port $port is available"
       break
     fi
   done
   ```

2. **Update Configuration**:
   - Add to `.env` file (e.g., `SERVICE_NAME_PORT=9001`)
   - Update service configuration files

3. **Update This Registry**:
   - Add entry to "Active Port Assignments"
   - Add entry to "Port Change History"
   - Commit changes with clear message

4. **Update Documentation**:
   - Update `QUICK-START.md` if user-facing
   - Update `ARCHITECTURE.md` if architectural component
   - Update `docs/RUNBOOKS.md` with operational procedures

---

## Port Usage Guidelines

### DO:
- ✅ Check this registry before assigning ports
- ✅ Update this file immediately after port assignment
- ✅ Use ports 9000-9999 for new services
- ✅ Document the purpose and configuration
- ✅ Test port availability before starting service

### DO NOT:
- ❌ Assign ports without checking this registry
- ❌ Use ports below 1024 (require root)
- ❌ Use commonly-used ports (3000, 5000, 8080)
- ❌ Forget to update this file after assignment
- ❌ Hardcode port numbers (use environment variables)

---

## Future Services (Planning)

When Cortex expands to include these services, they will need ports:

| Planned Service | Suggested Port | Priority | Notes |
|----------------|----------------|----------|-------|
| Worker Metrics Service | 9001 | Low | If separate from dashboard |
| Task Queue Monitor | 9002 | Low | If real-time monitoring needed |
| LLM Gateway | 9003 | Low | If direct LLM access API needed |
| Security Scanner API | 9004 | Medium | If security master needs API |

*Note: These are suggestions only. Check availability before assigning.*

---

## Quick Reference Commands

### Check All Cortex Ports
```bash
# List all ports used by Cortex (node processes)
lsof -iTCP -sTCP:LISTEN | grep node | grep -E "9000|9001|9002|9003|9004"
```

### Check Specific Port
```bash
# Check if port is in use
lsof -i :9000

# Check from registry
cat docs/PORTS-REGISTRY.md | grep "| 9000"
```

### Verify Dashboard Port
```bash
# Check .env configuration
cat .env | grep API_PORT

# Test connectivity
curl http://localhost:$(cat .env | grep API_PORT | cut -d'=' -f2)/api/health
```

### Find Next Available Port
```bash
# Scan for next available port in Cortex range
for port in {9000..9010}; do
  if ! lsof -i :$port > /dev/null 2>&1; then
    echo "✓ Port $port is available"
  else
    echo "✗ Port $port is in use"
  fi
done
```

---

## Conflict Resolution

If a port conflict occurs:

1. **Identify the Conflict**:
   ```bash
   lsof -i :PORT_NUMBER
   # Shows which process is using the port
   ```

2. **Determine Priority**:
   - Is the other service critical?
   - Is Cortex service critical?
   - Which was using the port first?

3. **Take Action**:
   - **Move Cortex service**: Follow procedure in `docs/PORT-POLICY.md`
   - **Move other service**: Coordinate with other app owner
   - **Use different port**: Assign next available from this registry

4. **Update Registry**:
   - Update "Active Port Assignments"
   - Add to "Port Change History"
   - Document reason for change

---

## Maintenance

### Weekly Check
```bash
# Verify all registered ports are actually in use
cat docs/PORTS-REGISTRY.md | grep "✅ Active" | grep -oE "[0-9]{4,5}" | while read port; do
  if lsof -i :$port > /dev/null 2>&1; then
    echo "✓ Port $port: In use as expected"
  else
    echo "⚠ Port $port: Registered but not in use"
  fi
done
```

### Monthly Audit
1. Review "Active Port Assignments"
2. Verify all services are still needed
3. Check for unused ports
4. Update status if services retired

---

## Contact

For port assignment questions or conflicts:
- **Review**: `docs/PORT-POLICY.md`
- **Approval**: Use governance critical task approval
- **Emergency**: See "Emergency Port Change Procedure" in `docs/PORT-POLICY.md`

---

## Change Log

| Date | Change | Modified By |
|------|--------|-------------|
| 2025-11-27 | Created ports registry with port 9000 for API Dashboard | Claude Code |

---

**Last Updated**: 2025-11-27
**Next Review**: 2025-12-27

**Remember**: This registry is only accurate if manually updated. Always update this file when assigning, changing, or retiring ports.
