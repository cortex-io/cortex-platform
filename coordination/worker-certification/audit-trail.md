# Cortex Audit Trail System

**Enterprise-Grade Audit Logging for AI Agent Operations**

Version: 1.0.0
Last Updated: 2025-12-09
Classification: Internal - Security Critical

---

## Table of Contents

1. [Overview](#overview)
2. [Operation Logging Requirements](#operation-logging-requirements)
3. [Immutable Audit Log Design](#immutable-audit-log-design)
4. [Log Format and Schema](#log-format-and-schema)
5. [Retention Policies](#retention-policies)
6. [Compliance Reporting](#compliance-reporting)
7. [Audit Log Storage and Backup](#audit-log-storage-and-backup)
8. [Real-Time Audit Streaming](#real-time-audit-streaming)
9. [Audit Query Interface](#audit-query-interface)
10. [Anomaly Detection](#anomaly-detection)
11. [Audit Log Integrity Verification](#audit-log-integrity-verification)
12. [Implementation Guide](#implementation-guide)

---

## Overview

The Cortex Audit Trail system provides comprehensive, immutable logging of all agent operations, worker activities, and system events. Designed for enterprise compliance (SOC2, ISO27001, GDPR), security monitoring, and forensic analysis.

### Core Principles

- **Immutability**: Append-only logs, cryptographically signed
- **Completeness**: All operations logged with full context
- **Integrity**: Chain-of-custody with cryptographic verification
- **Accessibility**: Real-time querying and streaming
- **Compliance**: SOC2, ISO27001, GDPR, HIPAA ready
- **Performance**: High-throughput, low-latency logging
- **Durability**: Multi-tier backup and archival

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CORTEX OPERATIONS                         │
│  (Masters, Workers, Contractors, Meta-Agent, Dashboard)     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  AUDIT EVENT COLLECTOR                       │
│  - Event validation                                          │
│  - Schema enforcement                                        │
│  - Event enrichment (context, metadata)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  AUDIT EVENT PROCESSOR                       │
│  - Cryptographic signing (HMAC-SHA256)                      │
│  - Chain verification                                        │
│  - Event correlation                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌────────┐  ┌────────┐  ┌──────────┐
    │ APPEND │  │ STREAM │  │ ANOMALY  │
    │  LOG   │  │  API   │  │ DETECTOR │
    └────────┘  └────────┘  └──────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                 IMMUTABLE AUDIT LOG                          │
│  - Active logs (last 90 days)                               │
│  - Warm storage (91-365 days)                               │
│  - Cold archive (1-7 years)                                 │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│              BACKUP & REPLICATION                            │
│  - Real-time replication                                     │
│  - Encrypted backups (3-2-1 strategy)                       │
│  - Offsite archival                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Operation Logging Requirements

### 1. Mandatory Logged Operations

All operations MUST be logged without exception:

#### Agent Operations
- **Master Spawning**: All master agent initialization
- **Worker Spawning**: Worker creation with parent context
- **Task Assignment**: Task delegation and acceptance
- **Handoffs**: Inter-master communication
- **Resource Allocation**: Token/time budgets assigned
- **Task Completion**: Success, failure, or timeout
- **Agent Termination**: Normal or abnormal shutdown

#### Authentication & Authorization
- **Permit Issuance**: Non-union worker permits
- **Certification Checks**: Union status verification
- **Access Grants**: File/resource access approvals
- **Access Denials**: Permission failures
- **Role Changes**: Permission elevation/reduction
- **Session Management**: Start, end, timeout

#### Data Operations
- **File Access**: Read, write, execute operations
- **Configuration Changes**: System configuration updates
- **Code Modifications**: Source code changes
- **Credential Access**: Secrets/keys retrieval
- **Data Export**: Data leaving system boundaries
- **Data Deletion**: Permanent data removal

#### System Operations
- **Process Execution**: Command execution
- **Network Activity**: External API calls
- **Service Starts/Stops**: System service lifecycle
- **Error Events**: Exceptions and failures
- **Security Events**: Intrusion attempts, violations
- **Performance Events**: Resource exhaustion, slowdowns

### 2. Logging Event Structure

Every logged operation MUST include:

```json
{
  "event_id": "uuid-v4",
  "timestamp": "ISO-8601 with microseconds",
  "event_type": "enum from event_types",
  "severity": "DEBUG|INFO|WARN|ERROR|CRITICAL|SECURITY",
  "actor": {
    "agent_id": "master/worker/contractor ID",
    "agent_type": "master|worker|contractor|meta_agent|human",
    "certification": "union|non_union|contractor|uncertified",
    "session_id": "session tracking"
  },
  "operation": {
    "action": "specific operation performed",
    "resource": "target resource",
    "outcome": "success|failure|partial",
    "reason": "failure reason if applicable"
  },
  "context": {
    "task_id": "associated task",
    "parent_id": "parent agent/operation",
    "correlation_id": "request tracing",
    "source_file": "originating file",
    "line_number": "code location"
  },
  "details": {
    "...operation-specific data..."
  },
  "integrity": {
    "signature": "HMAC-SHA256 of event",
    "previous_hash": "hash of previous event",
    "chain_sequence": "sequential number"
  }
}
```

### 3. Sensitive Data Handling

**MUST NOT LOG**:
- Raw passwords or credentials
- Full API keys (log last 4 chars only)
- Personal Identifiable Information (PII) without consent
- Sensitive health/financial data
- Full file contents (log checksums instead)

**MUST REDACT**:
- Environment variables (whitelist safe vars)
- Command arguments containing secrets
- API request/response bodies (sanitize first)
- Error messages with embedded credentials

**MUST ENCRYPT**:
- Audit logs at rest
- Audit logs in transit
- Backup archives
- Long-term storage

---

## Immutable Audit Log Design

### 1. Append-Only Architecture

Audit logs are **strictly append-only**:

- **No Updates**: Events cannot be modified after writing
- **No Deletions**: Events cannot be deleted (retention manages lifecycle)
- **Write-Once**: Single write operation per event
- **Sequential**: Events ordered by timestamp and sequence number

### 2. File Structure

```
coordination/audit-logs/
├── active/                          # Last 90 days
│   ├── 2025/
│   │   ├── 12/
│   │   │   ├── 09/
│   │   │   │   ├── audit-2025-12-09-00.jsonl      # Hourly files
│   │   │   │   ├── audit-2025-12-09-00.jsonl.sig  # Signature
│   │   │   │   ├── audit-2025-12-09-01.jsonl
│   │   │   │   ├── audit-2025-12-09-01.jsonl.sig
│   │   │   │   └── ...
│   │   │   └── audit-index-2025-12-09.json        # Daily index
│   │   └── audit-checksum-2025-12.sha256          # Monthly checksum
│   └── audit-manifest.json                         # Active manifest
├── warm/                            # 91-365 days (compressed)
│   └── 2025/
│       └── audit-2025-Q4.tar.gz.enc               # Quarterly archives
├── cold/                            # 1-7 years (encrypted archives)
│   └── audit-2024.tar.gz.enc
├── audit-chain.json                 # Blockchain-style chain state
├── audit-keys/                      # Signing keys (encrypted)
│   ├── signing-key-2025.key.enc
│   └── verification-keys.json
└── integrity/                       # Integrity verification data
    ├── merkle-roots.json
    └── verification-log.jsonl
```

### 3. Log File Format

**JSONL (JSON Lines)** for efficiency:

```jsonl
{"event_id":"550e8400-e29b-41d4-a716-446655440000","timestamp":"2025-12-09T10:30:45.123456Z",...}
{"event_id":"550e8400-e29b-41d4-a716-446655440001","timestamp":"2025-12-09T10:30:46.234567Z",...}
{"event_id":"550e8400-e29b-41d4-a716-446655440002","timestamp":"2025-12-09T10:30:47.345678Z",...}
```

### 4. Immutability Enforcement

#### File System Protections

```bash
# Set immutable attribute (Linux)
chattr +i audit-2025-12-09-00.jsonl

# Set append-only (Linux)
chattr +a audit-2025-12-09-current.jsonl

# Read-only permissions
chmod 444 audit-2025-12-09-00.jsonl

# macOS: Use file flags
chflags uchg audit-2025-12-09-00.jsonl  # Immutable
chflags uappnd audit-current.jsonl     # Append-only
```

#### Application-Level Protections

```javascript
// Write-once verification
const fs = require('fs').promises;

async function appendAuditEvent(event) {
  const logFile = getCurrentAuditFile();

  // Verify file is append-only mode
  const stats = await fs.stat(logFile);
  if (!stats.mode & 0o200) {
    throw new Error('Audit log not in append mode');
  }

  // Calculate event signature
  const signature = calculateEventSignature(event);
  event.integrity.signature = signature;

  // Atomic append with file lock
  const fd = await fs.open(logFile, 'a', 0o444);
  try {
    await fd.write(JSON.stringify(event) + '\n');
  } finally {
    await fd.close();
  }

  // Verify write
  await verifyLastEvent(event.event_id);
}
```

### 5. Chain-of-Custody

Events are linked in a blockchain-style chain:

```json
{
  "event_id": "current-event-uuid",
  "integrity": {
    "signature": "HMAC-SHA256(event_data + secret_key)",
    "previous_hash": "SHA256(previous_event)",
    "chain_sequence": 1234567,
    "merkle_root": "merkle tree root of batch"
  }
}
```

**Chain Verification**:

```bash
#!/bin/bash
# Verify audit chain integrity

verify_audit_chain() {
  local audit_file="$1"
  local previous_hash=""
  local sequence=0

  while IFS= read -r line; do
    sequence=$((sequence + 1))

    # Extract current event hash
    current_hash=$(echo "$line" | jq -r '.integrity.signature')
    stored_previous=$(echo "$line" | jq -r '.integrity.previous_hash')
    stored_sequence=$(echo "$line" | jq -r '.integrity.chain_sequence')

    # Verify sequence
    if [ "$stored_sequence" -ne "$sequence" ]; then
      echo "ERROR: Chain break at sequence $sequence"
      return 1
    fi

    # Verify previous hash
    if [ -n "$previous_hash" ] && [ "$stored_previous" != "$previous_hash" ]; then
      echo "ERROR: Hash mismatch at sequence $sequence"
      return 1
    fi

    previous_hash="$current_hash"
  done < "$audit_file"

  echo "Chain verified: $sequence events"
  return 0
}
```

---

## Log Format and Schema

### 1. Core Event Schema

```json
{
  "$schema": "https://cortex.local/schemas/audit-event-v1.json",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-12-09T10:30:45.123456Z",
  "event_type": "worker.spawned",
  "severity": "INFO",
  "version": "1.0.0",

  "actor": {
    "agent_id": "development-master-001",
    "agent_type": "master",
    "agent_role": "development_master",
    "certification": "union",
    "session_id": "session-abc123",
    "user_id": "system",
    "ip_address": "127.0.0.1",
    "hostname": "cortex-primary"
  },

  "operation": {
    "action": "spawn_worker",
    "resource": "feature-implementer-worker-001",
    "resource_type": "worker",
    "outcome": "success",
    "duration_ms": 245,
    "reason": null,
    "error_code": null
  },

  "context": {
    "task_id": "task-implement-audit-trail",
    "parent_id": "development-master-001",
    "correlation_id": "req-xyz789",
    "trace_id": "trace-001",
    "session_context": "development_session",
    "source_file": "/coordination/masters/development/run.sh",
    "line_number": 142,
    "git_commit": "c6507ccb",
    "environment": "production"
  },

  "details": {
    "worker_type": "feature-implementer",
    "token_allocation": 15000,
    "time_limit_minutes": 60,
    "task_description": "Implement audit trail system",
    "knowledge_base_refs": [
      "implementation-patterns.jsonl"
    ],
    "resource_constraints": {
      "max_memory_mb": 512,
      "max_cpu_percent": 50
    }
  },

  "integrity": {
    "signature": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "previous_hash": "d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35",
    "chain_sequence": 1234567,
    "merkle_root": "f5ca38f748a1d6eaf726b8a42fb575c3c71f1864a8143301782de13da2d9202b",
    "signature_algorithm": "HMAC-SHA256",
    "key_id": "audit-key-2025"
  },

  "compliance": {
    "retention_class": "operational",
    "retention_days": 2555,
    "encryption_required": true,
    "pii_present": false,
    "gdpr_applicable": true,
    "hipaa_applicable": false,
    "soc2_control": "CC6.1",
    "iso27001_control": "A.12.4.1"
  },

  "metadata": {
    "log_version": "1.0.0",
    "schema_version": "1.0.0",
    "ingestion_timestamp": "2025-12-09T10:30:45.150000Z",
    "processing_latency_ms": 5,
    "storage_tier": "active"
  }
}
```

### 2. Event Type Taxonomy

Events are categorized hierarchically:

```
agent.*               - Agent lifecycle events
  agent.master.spawned
  agent.master.terminated
  agent.worker.spawned
  agent.worker.completed
  agent.contractor.invoked
  agent.handoff.created
  agent.handoff.accepted

auth.*                - Authentication & authorization
  auth.permit.issued
  auth.permit.revoked
  auth.certification.verified
  auth.access.granted
  auth.access.denied
  auth.session.started
  auth.session.expired

data.*                - Data operations
  data.file.read
  data.file.write
  data.file.delete
  data.config.changed
  data.secret.accessed
  data.export.initiated
  data.backup.created

system.*              - System operations
  system.process.executed
  system.api.called
  system.service.started
  system.service.stopped
  system.resource.allocated
  system.resource.exhausted

security.*            - Security events
  security.vulnerability.detected
  security.intrusion.attempted
  security.policy.violated
  security.scan.completed
  security.patch.applied

compliance.*          - Compliance events
  compliance.report.generated
  compliance.audit.requested
  compliance.retention.applied
  compliance.deletion.executed
```

### 3. Severity Levels

```
DEBUG      - Detailed diagnostic information
INFO       - Normal operational events
WARN       - Warning conditions (degraded but functional)
ERROR      - Error conditions (operation failed)
CRITICAL   - Critical system failures
SECURITY   - Security-relevant events (always retained)
```

### 4. Schema Validation

All events validated against JSON Schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Cortex Audit Event",
  "type": "object",
  "required": [
    "event_id",
    "timestamp",
    "event_type",
    "severity",
    "actor",
    "operation",
    "context",
    "integrity"
  ],
  "properties": {
    "event_id": {
      "type": "string",
      "format": "uuid"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "event_type": {
      "type": "string",
      "pattern": "^[a-z]+\\.[a-z]+\\.[a-z_]+$"
    },
    "severity": {
      "type": "string",
      "enum": ["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL", "SECURITY"]
    }
  }
}
```

---

## Retention Policies

### 1. Retention Classes

| Class | Duration | Storage Tier | Compression | Encryption | Use Case |
|-------|----------|--------------|-------------|------------|----------|
| **Operational** | 90 days | Active SSD | None | At-rest | Day-to-day operations |
| **Regulatory** | 7 years | Cold Archive | gzip | AES-256 | SOC2, ISO27001 compliance |
| **Security** | 7 years | Warm+Cold | gzip | AES-256 | Security incidents |
| **Legal Hold** | Indefinite | Cold Archive | gzip | AES-256 | Litigation/investigation |
| **Diagnostic** | 30 days | Active SSD | None | At-rest | DEBUG level logs |
| **Financial** | 7 years | Cold Archive | gzip | AES-256 | Financial transactions |

### 2. Retention Rules

```json
{
  "retention_rules": [
    {
      "rule_id": "operational-default",
      "event_types": ["agent.*", "system.*"],
      "severity": ["INFO", "WARN"],
      "retention_days": 90,
      "storage_tiers": [
        {"tier": "active", "days": 90}
      ],
      "deletion_policy": "automatic"
    },
    {
      "rule_id": "security-events",
      "event_types": ["security.*", "auth.*"],
      "severity": ["WARN", "ERROR", "CRITICAL", "SECURITY"],
      "retention_days": 2555,
      "storage_tiers": [
        {"tier": "active", "days": 90},
        {"tier": "warm", "days": 275},
        {"tier": "cold", "days": 2190}
      ],
      "deletion_policy": "manual_approval_required"
    },
    {
      "rule_id": "compliance-soc2",
      "compliance_tags": ["soc2"],
      "retention_days": 2555,
      "storage_tiers": [
        {"tier": "active", "days": 90},
        {"tier": "warm", "days": 275},
        {"tier": "cold", "days": 2190}
      ],
      "deletion_policy": "automatic_with_audit"
    },
    {
      "rule_id": "legal-hold",
      "legal_hold": true,
      "retention_days": -1,
      "storage_tiers": [
        {"tier": "cold", "days": -1}
      ],
      "deletion_policy": "never"
    }
  ]
}
```

### 3. Storage Tier Lifecycle

```
Event Created
     │
     ▼
┌─────────────┐
│   ACTIVE    │  0-90 days
│   (Hot)     │  - JSONL files
│   SSD       │  - Indexed
└──────┬──────┘  - Real-time queries
       │
       ▼ (Day 91)
┌─────────────┐
│    WARM     │  91-365 days
│  (Medium)   │  - Compressed (gzip)
│   HDD       │  - Indexed
└──────┬──────┘  - Slower queries
       │
       ▼ (Day 366)
┌─────────────┐
│    COLD     │  1-7 years
│  (Archive)  │  - Encrypted archives
│  S3/Glacier │  - Batch retrieval
└──────┬──────┘  - Compliance retention
       │
       ▼ (After retention)
┌─────────────┐
│  DELETION   │  Secure deletion
│  (Purge)    │  - Crypto shredding
│   Audit     │  - Deletion logged
└─────────────┘
```

### 4. Automated Retention Management

```bash
#!/bin/bash
# Automated retention policy enforcement

AUDIT_DIR="/Users/ryandahlberg/Projects/cortex/coordination/audit-logs"

manage_retention() {
  local current_date=$(date -u +%s)

  # Move active → warm (after 90 days)
  find "$AUDIT_DIR/active" -type f -name "audit-*.jsonl" -mtime +90 | while read file; do
    echo "Moving to warm storage: $file"
    compress_and_move "$file" "$AUDIT_DIR/warm/"
  done

  # Move warm → cold (after 365 days)
  find "$AUDIT_DIR/warm" -type f -mtime +365 | while read file; do
    echo "Moving to cold storage: $file"
    encrypt_and_archive "$file" "$AUDIT_DIR/cold/"
  done

  # Delete expired cold storage (after retention period)
  find "$AUDIT_DIR/cold" -type f -mtime +2555 | while read file; do
    if can_delete "$file"; then
      echo "Deleting expired: $file"
      secure_delete "$file"
    else
      echo "Retention extended (legal hold): $file"
    fi
  done
}

compress_and_move() {
  local file="$1"
  local dest="$2"

  # Verify integrity before moving
  verify_file_integrity "$file" || return 1

  # Compress
  gzip -9 "$file"

  # Move to warm storage
  mv "${file}.gz" "$dest"

  # Update index
  update_storage_index "$file" "warm"
}

encrypt_and_archive() {
  local file="$1"
  local dest="$2"

  # Encrypt with AES-256
  openssl enc -aes-256-cbc -salt \
    -in "$file" \
    -out "${dest}/$(basename ${file}).enc" \
    -pass file:/path/to/encryption.key

  # Verify encryption
  openssl enc -d -aes-256-cbc \
    -in "${dest}/$(basename ${file}).enc" \
    -pass file:/path/to/encryption.key | \
    cmp - "$file" || return 1

  # Remove unencrypted
  secure_delete "$file"

  # Update index
  update_storage_index "$file" "cold"
}

secure_delete() {
  local file="$1"

  # Log deletion
  log_audit_event "data.file.delete" "$file"

  # Overwrite with random data (3 passes)
  shred -vfz -n 3 "$file"

  # Remove
  rm -f "$file"
}
```

### 5. Legal Hold Management

```json
{
  "legal_holds": [
    {
      "hold_id": "legal-hold-2025-001",
      "case_id": "CASE-2025-123",
      "created_at": "2025-12-01T00:00:00Z",
      "created_by": "legal@cortex.local",
      "status": "active",
      "scope": {
        "date_range": {
          "start": "2025-11-01T00:00:00Z",
          "end": "2025-11-30T23:59:59Z"
        },
        "event_types": ["security.*", "auth.*"],
        "actors": ["worker-suspicious-001"]
      },
      "retention_override": "indefinite",
      "deletion_prohibited": true,
      "access_restrictions": {
        "authorized_personnel": ["legal-team", "security-team"],
        "export_allowed": false,
        "notification_required": true
      }
    }
  ]
}
```

---

## Compliance Reporting

### 1. SOC2 Compliance

**SOC2 Trust Service Criteria Mapping**:

| Criteria | Control | Audit Events | Reporting |
|----------|---------|--------------|-----------|
| **CC6.1** | Logical access controls | `auth.*` | Access reports, failed logins |
| **CC6.2** | Prior to credential issuance | `auth.permit.issued` | Permit issuance audit |
| **CC6.3** | Credential removal | `auth.permit.revoked` | Deprovisioning reports |
| **CC7.2** | System monitoring | `system.*`, `security.*` | Security event dashboard |
| **CC7.3** | Incident response | `security.intrusion.*` | Incident timeline |
| **CC8.1** | Change management | `data.config.changed` | Change audit trail |

**SOC2 Audit Report Generation**:

```bash
#!/bin/bash
# Generate SOC2 compliance report

generate_soc2_report() {
  local start_date="$1"
  local end_date="$2"
  local output_file="$3"

  cat > "$output_file" <<EOF
# SOC2 Compliance Report
Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Period: $start_date to $end_date

## CC6.1 - Logical Access Controls

### Access Grants
EOF

  # Query access grants
  query_audit_logs \
    --event-type "auth.access.granted" \
    --start "$start_date" \
    --end "$end_date" \
    --format report >> "$output_file"

  cat >> "$output_file" <<EOF

### Access Denials
EOF

  # Query access denials
  query_audit_logs \
    --event-type "auth.access.denied" \
    --start "$start_date" \
    --end "$end_date" \
    --format report >> "$output_file"

  # Continue for all SOC2 controls...
}
```

### 2. ISO27001 Compliance

**ISO27001 Control Mapping**:

| Control | Name | Audit Events | Evidence |
|---------|------|--------------|----------|
| **A.9.2.1** | User registration | `auth.permit.issued` | User provisioning logs |
| **A.9.2.2** | User access provisioning | `auth.access.granted` | Access grant logs |
| **A.9.2.6** | Access rights removal | `auth.permit.revoked` | Deprovisioning logs |
| **A.12.4.1** | Event logging | All events | Complete audit trail |
| **A.12.4.2** | Protection of log info | `integrity.*` | Chain verification logs |
| **A.12.4.3** | Admin logs | `system.*` with `admin` role | Privileged access logs |
| **A.16.1.4** | Assessment of security events | `security.*` | Security incident logs |

### 3. GDPR Compliance

**GDPR Requirements**:

- **Article 30**: Records of processing activities
- **Article 32**: Security of processing (audit logs)
- **Article 33**: Breach notification (security events)
- **Article 15**: Right of access (data subject queries)
- **Article 17**: Right to erasure (deletion logs)

**GDPR Audit Features**:

```json
{
  "gdpr_compliance": {
    "pii_detection": {
      "enabled": true,
      "auto_redaction": true,
      "pii_types": ["email", "ip_address", "user_id"]
    },
    "data_subject_requests": {
      "access_query": "query by actor.user_id",
      "export_format": "json",
      "deletion_audit": true
    },
    "breach_notification": {
      "severity_threshold": "SECURITY",
      "auto_alert": true,
      "notification_window_hours": 72
    },
    "retention_limits": {
      "default_retention_days": 2555,
      "pii_retention_days": 365,
      "consent_based": true
    }
  }
}
```

### 4. Compliance Report Templates

#### SOC2 Audit Report

```markdown
# SOC2 Type II Audit Report
**Audit Period**: [START] to [END]
**Report Date**: [DATE]
**Auditor**: [NAME]

## Executive Summary
- Total Events Logged: [COUNT]
- Security Events: [COUNT]
- Access Violations: [COUNT]
- Compliance Score: [PERCENTAGE]

## CC6 - Logical and Physical Access Controls

### CC6.1 - Access Authorization
- Access requests: [COUNT]
- Approvals: [COUNT]
- Denials: [COUNT]
- Approval rate: [PERCENTAGE]

[DETAILED EVENT LISTING]

### CC6.2 - Credential Issuance
[...]

## CC7 - System Monitoring

### CC7.2 - Security Monitoring
- Intrusion attempts: [COUNT]
- Vulnerability scans: [COUNT]
- Incidents detected: [COUNT]

[DETAILED ANALYSIS]
```

#### ISO27001 Audit Report

```markdown
# ISO27001 Compliance Audit
**Certification Scope**: Information Security Management System
**Audit Date**: [DATE]
**Standard Version**: ISO/IEC 27001:2022

## A.9 - Access Control

### A.9.2.1 - User Registration and Deregistration
- New permits issued: [COUNT]
- Permits revoked: [COUNT]
- Active permits: [COUNT]

Evidence: See audit events [EVENT_IDS]

### A.12.4 - Logging and Monitoring

#### A.12.4.1 - Event Logging
- Total events logged: [COUNT]
- Event types covered: [LIST]
- Completeness: 100%

#### A.12.4.2 - Protection of Log Information
- Integrity checks passed: [COUNT/TOTAL]
- Chain verification: PASSED
- Unauthorized access attempts: 0

[DETAILED FINDINGS]
```

---

## Audit Log Storage and Backup

### 1. Storage Architecture

```
PRIMARY STORAGE
├── Local SSD (Active Logs)
│   └── /coordination/audit-logs/active/
│       └── RAID-1 mirrored
│
SECONDARY STORAGE
├── NAS (Warm Storage)
│   └── /mnt/audit-warm/
│       └── RAID-5 protected
│
TERTIARY STORAGE
├── S3-Compatible (Cold Archive)
│   └── s3://cortex-audit-archive/
│       └── Versioning enabled
│       └── Encryption at rest
│
OFFSITE BACKUP
└── Remote Backup Service
    └── Encrypted incremental backups
    └── 3-2-1 backup strategy
```

### 2. Backup Strategy (3-2-1 Rule)

- **3 Copies**: Primary + 2 backups
- **2 Media Types**: SSD + HDD/S3
- **1 Offsite**: Remote backup location

```bash
#!/bin/bash
# Automated backup script

AUDIT_DIR="/Users/ryandahlberg/Projects/cortex/coordination/audit-logs"
BACKUP_REMOTE="s3://cortex-audit-backup"
BACKUP_LOCAL="/mnt/backup/audit"

backup_audit_logs() {
  local timestamp=$(date -u +%Y%m%d-%H%M%S)
  local backup_id="audit-backup-${timestamp}"

  echo "Starting backup: $backup_id"

  # 1. Local incremental backup
  rsync -av --link-dest="$BACKUP_LOCAL/latest" \
    "$AUDIT_DIR/" \
    "$BACKUP_LOCAL/$backup_id/"

  ln -sfn "$BACKUP_LOCAL/$backup_id" "$BACKUP_LOCAL/latest"

  # 2. Remote encrypted backup
  tar -czf - "$AUDIT_DIR" | \
    openssl enc -aes-256-cbc -salt -pass file:/etc/cortex/backup.key | \
    aws s3 cp - "$BACKUP_REMOTE/$backup_id.tar.gz.enc"

  # 3. Verify backup integrity
  verify_backup "$backup_id"

  # 4. Update backup manifest
  update_backup_manifest "$backup_id"

  echo "Backup completed: $backup_id"
}

verify_backup() {
  local backup_id="$1"

  # Download and verify remote backup
  aws s3 cp "$BACKUP_REMOTE/$backup_id.tar.gz.enc" - | \
    openssl enc -d -aes-256-cbc -pass file:/etc/cortex/backup.key | \
    tar -tzf - > /dev/null

  if [ $? -eq 0 ]; then
    echo "Backup verified: $backup_id"
    return 0
  else
    echo "ERROR: Backup verification failed: $backup_id"
    alert_backup_failure "$backup_id"
    return 1
  fi
}
```

### 3. Backup Schedule

```json
{
  "backup_schedule": {
    "incremental": {
      "frequency": "hourly",
      "retention": "7 days",
      "type": "rsync_incremental"
    },
    "daily": {
      "frequency": "daily",
      "time": "02:00 UTC",
      "retention": "30 days",
      "type": "full_encrypted"
    },
    "weekly": {
      "frequency": "weekly",
      "day": "Sunday",
      "time": "03:00 UTC",
      "retention": "90 days",
      "type": "full_encrypted_offsite"
    },
    "monthly": {
      "frequency": "monthly",
      "day": 1,
      "time": "04:00 UTC",
      "retention": "7 years",
      "type": "archive_encrypted_offsite"
    }
  }
}
```

### 4. Disaster Recovery

**Recovery Time Objective (RTO)**: 4 hours
**Recovery Point Objective (RPO)**: 1 hour

```bash
#!/bin/bash
# Disaster recovery procedure

disaster_recovery() {
  local recovery_point="$1"  # Timestamp to recover to

  echo "DISASTER RECOVERY INITIATED"
  echo "Recovery Point: $recovery_point"

  # 1. Stop audit ingestion
  stop_audit_ingestion

  # 2. Identify backup to restore
  local backup_id=$(find_backup_at_time "$recovery_point")
  echo "Restoring from backup: $backup_id"

  # 3. Restore from remote backup
  aws s3 cp "$BACKUP_REMOTE/$backup_id.tar.gz.enc" - | \
    openssl enc -d -aes-256-cbc -pass file:/etc/cortex/backup.key | \
    tar -xzf - -C /tmp/audit-recovery/

  # 4. Verify integrity
  verify_chain_integrity /tmp/audit-recovery/

  # 5. Restore to production
  rsync -av /tmp/audit-recovery/ "$AUDIT_DIR/"

  # 6. Resume audit ingestion
  start_audit_ingestion

  # 7. Log recovery event
  log_audit_event "system.disaster_recovery" \
    --recovery-point "$recovery_point" \
    --backup-id "$backup_id"

  echo "DISASTER RECOVERY COMPLETED"
}
```

### 5. Storage Monitoring

```bash
#!/bin/bash
# Monitor storage capacity and health

monitor_storage() {
  local threshold_percent=80

  # Check active storage
  local active_usage=$(df -h "$AUDIT_DIR/active" | awk 'NR==2 {print $5}' | tr -d '%')

  if [ "$active_usage" -gt "$threshold_percent" ]; then
    alert_storage_critical "Active storage at ${active_usage}%"
    trigger_retention_cleanup
  fi

  # Check backup storage
  local backup_usage=$(df -h "$BACKUP_LOCAL" | awk 'NR==2 {print $5}' | tr -d '%')

  if [ "$backup_usage" -gt "$threshold_percent" ]; then
    alert_storage_warning "Backup storage at ${backup_usage}%"
  fi

  # Check S3 storage
  local s3_size=$(aws s3 ls --summarize --recursive "$BACKUP_REMOTE" | \
    grep "Total Size" | awk '{print $3}')

  echo "Storage Status:"
  echo "  Active: ${active_usage}%"
  echo "  Backup: ${backup_usage}%"
  echo "  S3: $s3_size bytes"
}
```

---

## Real-Time Audit Streaming

### 1. Streaming Architecture

```
┌─────────────────┐
│  Audit Events   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│     Event Stream Processor          │
│  - Event validation                 │
│  - Enrichment                       │
│  - Routing                          │
└────────┬────────────────────────────┘
         │
    ┌────┴────┬────────────┬──────────┐
    ▼         ▼            ▼          ▼
┌────────┐ ┌──────┐ ┌──────────┐ ┌────────┐
│  File  │ │ SIEM │ │ Dashboard│ │Webhook │
│  Log   │ │      │ │          │ │        │
└────────┘ └──────┘ └──────────┘ └────────┘
```

### 2. Event Streaming API

```javascript
// Real-time event streaming
const EventEmitter = require('events');
const fs = require('fs');

class AuditStreamManager extends EventEmitter {
  constructor() {
    super();
    this.streams = new Map();
    this.filters = new Map();
  }

  // Subscribe to audit stream
  subscribe(streamId, filter = {}) {
    const stream = {
      id: streamId,
      filter: filter,
      lastEventId: null,
      createdAt: new Date()
    };

    this.streams.set(streamId, stream);

    // Return stream handle
    return {
      on: (event, handler) => {
        this.on(`${streamId}:${event}`, handler);
      },
      close: () => {
        this.unsubscribe(streamId);
      }
    };
  }

  // Unsubscribe from stream
  unsubscribe(streamId) {
    this.streams.delete(streamId);
    this.removeAllListeners(streamId);
  }

  // Publish event to all matching streams
  publishEvent(event) {
    for (const [streamId, stream] of this.streams) {
      if (this.matchesFilter(event, stream.filter)) {
        this.emit(`${streamId}:event`, event);
        stream.lastEventId = event.event_id;
      }
    }
  }

  // Check if event matches stream filter
  matchesFilter(event, filter) {
    if (filter.event_types && !filter.event_types.some(t =>
      event.event_type.startsWith(t.replace('*', '')))) {
      return false;
    }

    if (filter.severity && !filter.severity.includes(event.severity)) {
      return false;
    }

    if (filter.actors && !filter.actors.includes(event.actor.agent_id)) {
      return false;
    }

    return true;
  }

  // Stream from file (tail -f behavior)
  streamFromFile(filePath, streamId) {
    const stream = fs.createReadStream(filePath);

    stream.on('data', (chunk) => {
      const lines = chunk.toString().split('\n');

      for (const line of lines) {
        if (line.trim()) {
          try {
            const event = JSON.parse(line);
            this.publishEvent(event);
          } catch (e) {
            console.error('Invalid event JSON:', e);
          }
        }
      }
    });

    // Watch for new events
    fs.watch(filePath, (eventType) => {
      if (eventType === 'change') {
        // Re-read new content
        stream.resume();
      }
    });
  }
}

// Usage
const streamManager = new AuditStreamManager();

// Subscribe to security events
const securityStream = streamManager.subscribe('security-monitor', {
  event_types: ['security.*', 'auth.access.denied'],
  severity: ['WARN', 'ERROR', 'CRITICAL', 'SECURITY']
});

securityStream.on('event', (event) => {
  console.log('Security event detected:', event);

  if (event.severity === 'CRITICAL') {
    alertSecurityTeam(event);
  }
});
```

### 3. WebSocket Streaming

```javascript
// WebSocket server for real-time audit streaming
const WebSocket = require('ws');

class AuditWebSocketServer {
  constructor(port) {
    this.wss = new WebSocket.Server({ port });
    this.clients = new Map();

    this.wss.on('connection', (ws, req) => {
      const clientId = generateClientId();

      this.clients.set(clientId, {
        ws: ws,
        authenticated: false,
        subscriptions: []
      });

      ws.on('message', (message) => {
        this.handleMessage(clientId, message);
      });

      ws.on('close', () => {
        this.clients.delete(clientId);
      });
    });
  }

  handleMessage(clientId, message) {
    const client = this.clients.get(clientId);
    const msg = JSON.parse(message);

    switch (msg.type) {
      case 'authenticate':
        this.authenticate(clientId, msg.token);
        break;

      case 'subscribe':
        if (client.authenticated) {
          this.subscribe(clientId, msg.filter);
        }
        break;

      case 'unsubscribe':
        this.unsubscribe(clientId, msg.subscriptionId);
        break;
    }
  }

  broadcast(event, filter) {
    for (const [clientId, client] of this.clients) {
      if (client.authenticated && this.matchesSubscription(event, client.subscriptions)) {
        client.ws.send(JSON.stringify({
          type: 'event',
          event: event
        }));
      }
    }
  }
}

// Start WebSocket server
const wsServer = new AuditWebSocketServer(8080);

// Broadcast audit events
streamManager.on('event', (event) => {
  wsServer.broadcast(event);
});
```

### 4. SIEM Integration

```bash
#!/bin/bash
# Forward audit events to SIEM (e.g., Splunk, ELK)

forward_to_siem() {
  local siem_endpoint="${SIEM_ENDPOINT:-https://siem.cortex.local:8088/services/collector}"
  local siem_token="${SIEM_TOKEN}"

  # Tail audit log and forward
  tail -F "$AUDIT_DIR/active/$(date +%Y/%m/%d)/audit-$(date +%Y-%m-%d-%H).jsonl" | \
  while IFS= read -r event; do
    # Transform to SIEM format
    local siem_event=$(echo "$event" | jq '{
      time: .timestamp,
      source: "cortex-audit",
      sourcetype: "audit:cortex",
      event: .
    }')

    # Forward to SIEM
    curl -X POST "$siem_endpoint" \
      -H "Authorization: Splunk $siem_token" \
      -H "Content-Type: application/json" \
      -d "$siem_event"
  done
}

# Run in background
forward_to_siem &
```

### 5. Dashboard Integration

```javascript
// Real-time dashboard updates
const dashboardSocket = io('http://localhost:3000');

// Subscribe to audit stream
const auditStream = streamManager.subscribe('dashboard-feed', {
  severity: ['WARN', 'ERROR', 'CRITICAL', 'SECURITY']
});

auditStream.on('event', (event) => {
  // Push to dashboard
  dashboardSocket.emit('audit:event', {
    timestamp: event.timestamp,
    severity: event.severity,
    event_type: event.event_type,
    summary: generateEventSummary(event)
  });

  // Update real-time metrics
  updateMetrics(event);
});

function updateMetrics(event) {
  const metrics = {
    total_events: incrementCounter('total_events'),
    events_by_severity: incrementCounter(`severity:${event.severity}`),
    events_by_type: incrementCounter(`type:${event.event_type}`)
  };

  dashboardSocket.emit('metrics:update', metrics);
}
```

---

## Audit Query Interface

### 1. Query CLI

```bash
#!/bin/bash
# Audit log query interface

query_audit_logs() {
  local query_file="$1"

  cat > /tmp/audit-query.jq <<'EOF'
# JQ query builder
select(
  (.timestamp >= $start_time) and
  (.timestamp <= $end_time) and
  (if $event_type then (.event_type | startswith($event_type)) else true end) and
  (if $severity then (.severity == $severity) else true end) and
  (if $actor then (.actor.agent_id == $actor) else true end)
)
EOF

  # Query parameters
  local start_time="${START_TIME:-$(date -u -v-1d +%Y-%m-%dT%H:%M:%SZ)}"
  local end_time="${END_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
  local event_type="${EVENT_TYPE}"
  local severity="${SEVERITY}"
  local actor="${ACTOR}"

  # Search audit logs
  find "$AUDIT_DIR/active" -type f -name "audit-*.jsonl" | \
  xargs cat | \
  jq --arg start_time "$start_time" \
     --arg end_time "$end_time" \
     --arg event_type "$event_type" \
     --arg severity "$severity" \
     --arg actor "$actor" \
     -f /tmp/audit-query.jq
}

# Usage examples:
# EVENT_TYPE="security.*" SEVERITY="CRITICAL" query_audit_logs
# ACTOR="worker-001" START_TIME="2025-12-09T00:00:00Z" query_audit_logs
```

### 2. Query API

```javascript
// Audit query API
const express = require('express');
const app = express();

app.post('/api/audit/query', authenticate, async (req, res) => {
  const {
    start_time,
    end_time,
    event_types,
    severity,
    actors,
    limit = 1000,
    offset = 0
  } = req.body;

  try {
    const results = await queryAuditLogs({
      start_time,
      end_time,
      event_types,
      severity,
      actors,
      limit,
      offset
    });

    res.json({
      total: results.total,
      limit: limit,
      offset: offset,
      events: results.events
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

async function queryAuditLogs(query) {
  const { start_time, end_time, event_types, severity, actors, limit, offset } = query;

  // Build query filter
  const filter = {};

  if (start_time || end_time) {
    filter.timestamp = {};
    if (start_time) filter.timestamp.$gte = start_time;
    if (end_time) filter.timestamp.$lte = end_time;
  }

  if (event_types) {
    filter.event_type = { $in: event_types };
  }

  if (severity) {
    filter.severity = Array.isArray(severity) ? { $in: severity } : severity;
  }

  if (actors) {
    filter['actor.agent_id'] = { $in: actors };
  }

  // Execute query (using file-based search or database)
  const results = await searchAuditFiles(filter, { limit, offset });

  return results;
}
```

### 3. Advanced Query DSL

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "range": {
            "timestamp": {
              "gte": "2025-12-09T00:00:00Z",
              "lte": "2025-12-09T23:59:59Z"
            }
          }
        },
        {
          "terms": {
            "event_type": ["security.intrusion.attempted", "auth.access.denied"]
          }
        }
      ],
      "should": [
        {
          "term": {
            "severity": "CRITICAL"
          }
        },
        {
          "term": {
            "severity": "SECURITY"
          }
        }
      ],
      "minimum_should_match": 1
    }
  },
  "aggregations": {
    "by_severity": {
      "terms": {
        "field": "severity"
      }
    },
    "by_actor": {
      "terms": {
        "field": "actor.agent_id"
      }
    },
    "timeline": {
      "date_histogram": {
        "field": "timestamp",
        "interval": "1h"
      }
    }
  },
  "sort": [
    {
      "timestamp": "desc"
    }
  ],
  "size": 100
}
```

### 4. Pre-built Query Templates

```json
{
  "query_templates": {
    "security_incidents": {
      "name": "Security Incidents Last 24h",
      "description": "All security events in the last 24 hours",
      "query": {
        "event_types": ["security.*"],
        "severity": ["WARN", "ERROR", "CRITICAL", "SECURITY"],
        "time_range": "last_24h"
      }
    },
    "failed_authentications": {
      "name": "Failed Authentication Attempts",
      "description": "All failed auth attempts",
      "query": {
        "event_types": ["auth.access.denied", "auth.permit.revoked"],
        "operation.outcome": "failure"
      }
    },
    "privileged_access": {
      "name": "Privileged Access Audit",
      "description": "All privileged operations",
      "query": {
        "actor.certification": "union",
        "event_types": ["data.config.changed", "system.process.executed"],
        "severity": ["INFO", "WARN", "ERROR"]
      }
    },
    "data_modifications": {
      "name": "Data Modification Audit",
      "description": "All data write/delete operations",
      "query": {
        "event_types": ["data.file.write", "data.file.delete", "data.config.changed"]
      }
    }
  }
}
```

---

## Anomaly Detection

### 1. Anomaly Detection Engine

```javascript
// Anomaly detection for audit logs
class AuditAnomalyDetector {
  constructor() {
    this.baselines = new Map();
    this.anomalies = [];
    this.thresholds = {
      failed_auth_rate: 0.05,      // 5% failure rate
      event_rate_stddev: 3,        // 3 standard deviations
      unusual_time_hours: [0, 1, 2, 3, 4, 5],  // 12am-6am
      token_exhaustion_percent: 90
    };
  }

  // Detect anomalies in event stream
  async detectAnomalies(events) {
    const anomalies = [];

    // 1. Failed authentication spike
    const authAnomalies = this.detectAuthAnomalies(events);
    anomalies.push(...authAnomalies);

    // 2. Unusual access patterns
    const accessAnomalies = this.detectAccessAnomalies(events);
    anomalies.push(...accessAnomalies);

    // 3. Resource exhaustion
    const resourceAnomalies = this.detectResourceAnomalies(events);
    anomalies.push(...resourceAnomalies);

    // 4. Unusual timing
    const timingAnomalies = this.detectTimingAnomalies(events);
    anomalies.push(...timingAnomalies);

    // 5. Privilege escalation
    const privilegeAnomalies = this.detectPrivilegeAnomalies(events);
    anomalies.push(...privilegeAnomalies);

    return anomalies;
  }

  // Detect authentication anomalies
  detectAuthAnomalies(events) {
    const anomalies = [];

    // Calculate failure rate by actor
    const authEvents = events.filter(e => e.event_type.startsWith('auth.'));
    const failuresByActor = new Map();

    for (const event of authEvents) {
      const actor = event.actor.agent_id;

      if (!failuresByActor.has(actor)) {
        failuresByActor.set(actor, { total: 0, failed: 0 });
      }

      const stats = failuresByActor.get(actor);
      stats.total++;

      if (event.operation.outcome === 'failure') {
        stats.failed++;
      }
    }

    // Check for anomalous failure rates
    for (const [actor, stats] of failuresByActor) {
      const failureRate = stats.failed / stats.total;

      if (failureRate > this.thresholds.failed_auth_rate && stats.total > 5) {
        anomalies.push({
          type: 'high_auth_failure_rate',
          severity: 'WARN',
          actor: actor,
          failure_rate: failureRate,
          total_attempts: stats.total,
          failed_attempts: stats.failed,
          description: `Actor ${actor} has ${(failureRate * 100).toFixed(1)}% auth failure rate`
        });
      }
    }

    return anomalies;
  }

  // Detect unusual access patterns
  detectAccessAnomalies(events) {
    const anomalies = [];

    // Check for access to unusual resources
    const accessEvents = events.filter(e =>
      e.event_type.startsWith('data.') ||
      e.event_type.startsWith('system.')
    );

    const accessByActor = new Map();

    for (const event of accessEvents) {
      const actor = event.actor.agent_id;

      if (!accessByActor.has(actor)) {
        accessByActor.set(actor, new Set());
      }

      accessByActor.get(actor).add(event.operation.resource);
    }

    // Compare to baseline
    for (const [actor, resources] of accessByActor) {
      const baseline = this.baselines.get(`access:${actor}`);

      if (baseline) {
        const newResources = [...resources].filter(r => !baseline.has(r));

        if (newResources.length > 0) {
          anomalies.push({
            type: 'unusual_resource_access',
            severity: 'INFO',
            actor: actor,
            new_resources: newResources,
            description: `Actor ${actor} accessed ${newResources.length} new resources`
          });
        }
      }

      // Update baseline
      this.baselines.set(`access:${actor}`, resources);
    }

    return anomalies;
  }

  // Detect resource exhaustion
  detectResourceAnomalies(events) {
    const anomalies = [];

    // Check for token exhaustion
    const resourceEvents = events.filter(e =>
      e.event_type === 'agent.worker.spawned' ||
      e.event_type === 'system.resource.exhausted'
    );

    for (const event of resourceEvents) {
      if (event.event_type === 'system.resource.exhausted') {
        anomalies.push({
          type: 'resource_exhaustion',
          severity: 'WARN',
          actor: event.actor.agent_id,
          resource: event.details.resource_type,
          description: `Resource exhaustion: ${event.details.resource_type}`
        });
      }

      // Check token allocation
      if (event.details?.token_allocation) {
        const tokenUsage = event.details.tokens_used / event.details.token_allocation;

        if (tokenUsage > this.thresholds.token_exhaustion_percent / 100) {
          anomalies.push({
            type: 'high_token_usage',
            severity: 'INFO',
            actor: event.actor.agent_id,
            token_usage_percent: (tokenUsage * 100).toFixed(1),
            description: `High token usage: ${(tokenUsage * 100).toFixed(1)}%`
          });
        }
      }
    }

    return anomalies;
  }

  // Detect unusual timing patterns
  detectTimingAnomalies(events) {
    const anomalies = [];

    for (const event of events) {
      const hour = new Date(event.timestamp).getUTCHours();

      // Check for activity during unusual hours
      if (this.thresholds.unusual_time_hours.includes(hour)) {
        if (event.severity !== 'DEBUG' && event.event_type !== 'system.monitoring') {
          anomalies.push({
            type: 'unusual_timing',
            severity: 'INFO',
            actor: event.actor.agent_id,
            hour: hour,
            event_type: event.event_type,
            description: `Activity at unusual hour: ${hour}:00 UTC`
          });
        }
      }
    }

    return anomalies;
  }

  // Detect privilege escalation
  detectPrivilegeAnomalies(events) {
    const anomalies = [];

    // Track certification changes
    const certChanges = events.filter(e =>
      e.event_type === 'auth.permit.issued' ||
      e.event_type === 'auth.certification.verified'
    );

    for (const event of certChanges) {
      if (event.details?.previous_certification &&
          event.details?.new_certification) {

        if (event.details.previous_certification === 'non_union' &&
            event.details.new_certification === 'union') {
          anomalies.push({
            type: 'privilege_escalation',
            severity: 'WARN',
            actor: event.actor.agent_id,
            from: event.details.previous_certification,
            to: event.details.new_certification,
            description: `Privilege escalation: ${event.details.previous_certification} -> ${event.details.new_certification}`
          });
        }
      }
    }

    return anomalies;
  }
}

// Usage
const detector = new AuditAnomalyDetector();

streamManager.on('batch', async (events) => {
  const anomalies = await detector.detectAnomalies(events);

  for (const anomaly of anomalies) {
    console.log('Anomaly detected:', anomaly);

    if (anomaly.severity === 'WARN' || anomaly.severity === 'CRITICAL') {
      alertSecurityTeam(anomaly);
    }

    // Log anomaly to audit trail
    logAuditEvent('security.anomaly.detected', anomaly);
  }
});
```

### 2. Machine Learning Anomaly Detection

```python
#!/usr/bin/env python3
# ML-based anomaly detection for audit logs

import json
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

class MLAnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.01, random_state=42)
        self.scaler = StandardScaler()
        self.feature_names = [
            'hour_of_day',
            'day_of_week',
            'event_rate',
            'unique_resources',
            'failed_operations',
            'token_usage',
            'operation_duration'
        ]

    def extract_features(self, events):
        """Extract numerical features from events"""
        features = []

        for event in events:
            timestamp = event['timestamp']
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            feature_vector = [
                dt.hour,
                dt.weekday(),
                len(events),  # event rate
                len(set(e['operation']['resource'] for e in events)),
                sum(1 for e in events if e['operation']['outcome'] == 'failure'),
                event.get('details', {}).get('token_usage', 0),
                event['operation'].get('duration_ms', 0)
            ]

            features.append(feature_vector)

        return np.array(features)

    def train(self, historical_events):
        """Train on historical data"""
        features = self.extract_features(historical_events)
        features_scaled = self.scaler.fit_transform(features)
        self.model.fit(features_scaled)

    def detect(self, events):
        """Detect anomalies in new events"""
        features = self.extract_features(events)
        features_scaled = self.scaler.transform(features)

        predictions = self.model.predict(features_scaled)
        anomaly_scores = self.model.score_samples(features_scaled)

        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
            if pred == -1:  # Anomaly
                anomalies.append({
                    'event': events[i],
                    'anomaly_score': float(score),
                    'features': dict(zip(self.feature_names, features[i]))
                })

        return anomalies

# Load and train
detector = MLAnomalyDetector()
historical_events = load_historical_events()
detector.train(historical_events)

# Detect anomalies
new_events = load_recent_events()
anomalies = detector.detect(new_events)

for anomaly in anomalies:
    print(f"Anomaly detected: {anomaly['event']['event_id']}")
    print(f"  Score: {anomaly['anomaly_score']}")
    print(f"  Features: {anomaly['features']}")
```

---

## Audit Log Integrity Verification

### 1. Cryptographic Signing

```bash
#!/bin/bash
# Sign audit events with HMAC-SHA256

SIGNING_KEY_FILE="/Users/ryandahlberg/Projects/cortex/coordination/audit-logs/audit-keys/signing-key-2025.key"

# Generate signing key (once)
generate_signing_key() {
  openssl rand -hex 32 > "$SIGNING_KEY_FILE"
  chmod 400 "$SIGNING_KEY_FILE"
}

# Sign an event
sign_event() {
  local event_json="$1"
  local signing_key=$(cat "$SIGNING_KEY_FILE")

  # Calculate HMAC-SHA256
  local signature=$(echo -n "$event_json" | \
    openssl dgst -sha256 -hmac "$signing_key" | \
    awk '{print $2}')

  echo "$signature"
}

# Verify event signature
verify_event_signature() {
  local event_json="$1"
  local expected_signature="$2"
  local signing_key=$(cat "$SIGNING_KEY_FILE")

  # Recalculate signature
  local calculated_signature=$(echo -n "$event_json" | \
    openssl dgst -sha256 -hmac "$signing_key" | \
    awk '{print $2}')

  if [ "$calculated_signature" = "$expected_signature" ]; then
    return 0  # Valid
  else
    return 1  # Invalid
  fi
}

# Sign event before logging
log_signed_event() {
  local event="$1"

  # Calculate signature
  local signature=$(sign_event "$event")

  # Add signature to event
  local signed_event=$(echo "$event" | jq \
    --arg sig "$signature" \
    '.integrity.signature = $sig')

  # Append to log
  echo "$signed_event" >> "$AUDIT_LOG_FILE"
}
```

### 2. Chain Verification

```javascript
// Verify audit chain integrity
async function verifyAuditChain(logFile) {
  const fs = require('fs').promises;
  const crypto = require('crypto');

  const lines = (await fs.readFile(logFile, 'utf-8')).split('\n').filter(l => l.trim());

  let previousHash = null;
  let sequence = 0;
  const errors = [];

  for (const line of lines) {
    const event = JSON.parse(line);
    sequence++;

    // 1. Verify sequence number
    if (event.integrity.chain_sequence !== sequence) {
      errors.push({
        event_id: event.event_id,
        error: 'sequence_mismatch',
        expected: sequence,
        actual: event.integrity.chain_sequence
      });
    }

    // 2. Verify previous hash
    if (previousHash !== null && event.integrity.previous_hash !== previousHash) {
      errors.push({
        event_id: event.event_id,
        error: 'chain_break',
        expected_hash: previousHash,
        actual_hash: event.integrity.previous_hash
      });
    }

    // 3. Verify signature
    const eventCopy = { ...event };
    const storedSignature = eventCopy.integrity.signature;
    delete eventCopy.integrity.signature;

    const calculatedSignature = crypto
      .createHmac('sha256', signingKey)
      .update(JSON.stringify(eventCopy))
      .digest('hex');

    if (calculatedSignature !== storedSignature) {
      errors.push({
        event_id: event.event_id,
        error: 'signature_invalid',
        expected: calculatedSignature,
        actual: storedSignature
      });
    }

    // Update for next iteration
    previousHash = event.integrity.signature;
  }

  return {
    total_events: sequence,
    errors: errors,
    valid: errors.length === 0
  };
}

// Run verification
const result = await verifyAuditChain('/path/to/audit.jsonl');

if (result.valid) {
  console.log(`Chain verified: ${result.total_events} events`);
} else {
  console.error(`Chain verification failed: ${result.errors.length} errors`);
  console.error(result.errors);
}
```

### 3. Merkle Tree Verification

```javascript
// Build Merkle tree for batch integrity
class MerkleTree {
  constructor(leaves) {
    this.leaves = leaves.map(l => this.hash(l));
    this.tree = this.buildTree(this.leaves);
    this.root = this.tree[this.tree.length - 1][0];
  }

  hash(data) {
    return crypto.createHash('sha256').update(JSON.stringify(data)).digest('hex');
  }

  buildTree(leaves) {
    const tree = [leaves];

    while (tree[tree.length - 1].length > 1) {
      const level = tree[tree.length - 1];
      const nextLevel = [];

      for (let i = 0; i < level.length; i += 2) {
        if (i + 1 < level.length) {
          const combined = level[i] + level[i + 1];
          nextLevel.push(this.hash(combined));
        } else {
          nextLevel.push(level[i]);
        }
      }

      tree.push(nextLevel);
    }

    return tree;
  }

  getRoot() {
    return this.root;
  }

  getProof(index) {
    const proof = [];
    let currentIndex = index;

    for (let level = 0; level < this.tree.length - 1; level++) {
      const levelNodes = this.tree[level];
      const isRightNode = currentIndex % 2 === 1;
      const siblingIndex = isRightNode ? currentIndex - 1 : currentIndex + 1;

      if (siblingIndex < levelNodes.length) {
        proof.push({
          hash: levelNodes[siblingIndex],
          position: isRightNode ? 'left' : 'right'
        });
      }

      currentIndex = Math.floor(currentIndex / 2);
    }

    return proof;
  }

  verify(leaf, proof, root) {
    let hash = this.hash(leaf);

    for (const node of proof) {
      if (node.position === 'left') {
        hash = this.hash(node.hash + hash);
      } else {
        hash = this.hash(hash + node.hash);
      }
    }

    return hash === root;
  }
}

// Build Merkle tree for hourly batch
function buildHourlyMerkleTree(events) {
  const tree = new MerkleTree(events);

  return {
    root: tree.getRoot(),
    timestamp: new Date().toISOString(),
    event_count: events.length,
    first_event: events[0].event_id,
    last_event: events[events.length - 1].event_id
  };
}

// Store Merkle root
function storeMerkleRoot(merkleData) {
  const merkleFile = `${AUDIT_DIR}/integrity/merkle-roots.json`;

  const roots = JSON.parse(fs.readFileSync(merkleFile, 'utf-8'));
  roots.push(merkleData);

  fs.writeFileSync(merkleFile, JSON.stringify(roots, null, 2));
}
```

### 4. Periodic Integrity Audits

```bash
#!/bin/bash
# Automated integrity audit

AUDIT_DIR="/Users/ryandahlberg/Projects/cortex/coordination/audit-logs"

run_integrity_audit() {
  local audit_id="integrity-audit-$(date -u +%Y%m%d-%H%M%S)"
  local report_file="$AUDIT_DIR/integrity/audit-report-${audit_id}.json"

  echo "Starting integrity audit: $audit_id"

  local total_files=0
  local verified_files=0
  local failed_files=0
  local errors=()

  # Verify all active log files
  find "$AUDIT_DIR/active" -type f -name "audit-*.jsonl" | while read file; do
    total_files=$((total_files + 1))

    echo "Verifying: $file"

    # 1. Verify file checksum
    if ! verify_file_checksum "$file"; then
      echo "  ERROR: Checksum mismatch"
      failed_files=$((failed_files + 1))
      errors+=("checksum_mismatch:$file")
      continue
    fi

    # 2. Verify chain integrity
    if ! verify_chain_integrity "$file"; then
      echo "  ERROR: Chain integrity failed"
      failed_files=$((failed_files + 1))
      errors+=("chain_integrity:$file")
      continue
    fi

    # 3. Verify signatures
    if ! verify_all_signatures "$file"; then
      echo "  ERROR: Signature verification failed"
      failed_files=$((failed_files + 1))
      errors+=("signature_verification:$file")
      continue
    fi

    echo "  OK"
    verified_files=$((verified_files + 1))
  done

  # Generate report
  cat > "$report_file" <<EOF
{
  "audit_id": "$audit_id",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scope": "active_logs",
  "summary": {
    "total_files": $total_files,
    "verified": $verified_files,
    "failed": $failed_files
  },
  "errors": $(printf '%s\n' "${errors[@]}" | jq -R . | jq -s .),
  "status": "$([ $failed_files -eq 0 ] && echo 'PASS' || echo 'FAIL')"
}
EOF

  echo "Integrity audit complete: $audit_id"
  echo "Report: $report_file"

  # Alert if failures
  if [ $failed_files -gt 0 ]; then
    alert_integrity_failure "$audit_id" "$report_file"
  fi
}

# Schedule periodic audits
# Run daily at 3 AM
echo "0 3 * * * /path/to/run_integrity_audit.sh" | crontab -
```

---

## Implementation Guide

### 1. Quick Start

```bash
#!/bin/bash
# Initialize audit trail system

CORTEX_ROOT="/Users/ryandahlberg/Projects/cortex"
AUDIT_DIR="$CORTEX_ROOT/coordination/audit-logs"

# 1. Create directory structure
mkdir -p "$AUDIT_DIR"/{active,warm,cold,audit-keys,integrity}
mkdir -p "$AUDIT_DIR/active/$(date +%Y/%m/%d)"

# 2. Generate signing key
openssl rand -hex 32 > "$AUDIT_DIR/audit-keys/signing-key-2025.key"
chmod 400 "$AUDIT_DIR/audit-keys/signing-key-2025.key"

# 3. Initialize chain state
cat > "$AUDIT_DIR/audit-chain.json" <<EOF
{
  "chain_id": "cortex-audit-chain-001",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "last_sequence": 0,
  "last_hash": null,
  "current_file": "$AUDIT_DIR/active/$(date +%Y/%m/%d)/audit-$(date +%Y-%m-%d-%H).jsonl"
}
EOF

# 4. Initialize manifest
cat > "$AUDIT_DIR/active/audit-manifest.json" <<EOF
{
  "manifest_version": "1.0.0",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "files": []
}
EOF

# 5. Initialize Merkle roots
cat > "$AUDIT_DIR/integrity/merkle-roots.json" <<'EOF'
[]
EOF

echo "Audit trail system initialized"
```

### 2. Integration Example

```bash
#!/bin/bash
# Example: Integrating audit logging into a master script

source "$CORTEX_ROOT/coordination/audit-logs/audit-lib.sh"

# Initialize audit session
audit_session_start "development-master-001"

# Log worker spawning
audit_log_event \
  --event-type "agent.worker.spawned" \
  --severity "INFO" \
  --actor "development-master-001" \
  --action "spawn_worker" \
  --resource "feature-implementer-001" \
  --outcome "success" \
  --details '{
    "worker_type": "feature-implementer",
    "token_allocation": 15000,
    "task_description": "Implement feature X"
  }'

# Log task completion
audit_log_event \
  --event-type "agent.worker.completed" \
  --severity "INFO" \
  --actor "feature-implementer-001" \
  --action "complete_task" \
  --resource "task-123" \
  --outcome "success" \
  --details '{
    "duration_seconds": 3600,
    "tokens_used": 12500
  }'

# End audit session
audit_session_end "development-master-001"
```

### 3. Dashboard Integration

```javascript
// Real-time audit dashboard
import { AuditStreamClient } from './audit-stream-client.js';

const auditClient = new AuditStreamClient('ws://localhost:8080');

// Subscribe to real-time events
auditClient.subscribe({
  event_types: ['security.*', 'auth.*'],
  severity: ['WARN', 'ERROR', 'CRITICAL', 'SECURITY']
});

auditClient.on('event', (event) => {
  // Update dashboard UI
  updateEventTimeline(event);
  updateMetricCharts(event);

  if (event.severity === 'CRITICAL' || event.severity === 'SECURITY') {
    showCriticalAlert(event);
  }
});

// Query historical data
async function loadAuditHistory() {
  const events = await auditClient.query({
    start_time: new Date(Date.now() - 24 * 60 * 60 * 1000),
    limit: 1000
  });

  renderAuditTable(events);
}
```

---

## Security Considerations

### 1. Access Control

- **Audit logs are READ-ONLY** for all agents except audit system
- **Write access** restricted to audit logging service
- **Query access** role-based (masters > workers > contractors)
- **Export restrictions** for sensitive logs
- **Encryption** required for all storage and transmission

### 2. Key Management

- **Signing keys** rotated annually
- **Encryption keys** stored in secure key vault
- **Backup keys** encrypted with master key
- **Key access** logged in audit trail

### 3. Tamper Detection

- Cryptographic signatures on all events
- Chain-of-custody verification
- Merkle tree integrity proofs
- Regular automated audits

### 4. Compliance

- SOC2 Type II ready
- ISO27001 compliant
- GDPR privacy controls
- 7-year retention for regulatory logs

---

## Summary

The Cortex Audit Trail system provides:

- **Complete operational visibility** - Every action logged
- **Immutable records** - Append-only, cryptographically signed
- **Enterprise compliance** - SOC2, ISO27001, GDPR ready
- **Real-time monitoring** - Live event streaming and alerting
- **Advanced analytics** - Anomaly detection and ML insights
- **Forensic capability** - Full investigative query interface
- **Data integrity** - Chain verification and Merkle proofs
- **Disaster recovery** - Multi-tier backup and archival

This audit trail system ensures complete accountability, security, and compliance for all Cortex operations.

**Document Version**: 1.0.0
**Effective Date**: 2025-12-09
**Review Cycle**: Quarterly
