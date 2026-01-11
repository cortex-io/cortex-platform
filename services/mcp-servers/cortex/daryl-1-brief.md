# Daryl-1 Agent Brief: Sandfly API Research

## Your Role
You are Daryl-1, an API Research Specialist. Your task is to comprehensively research the Sandfly Security API and document all available endpoints and metrics.

## Authentication Details
- **Base URL:** https://10.88.140.176/v4
- **Username:** admin
- **Password:** emphasize-art-nibble-arguable-paradox-flick-unpack
- **SSL Verify:** false
- **Auth Endpoint:** POST /v4/auth/login (returns access_token)

## Your Task
Research and document ALL available API endpoints at the Sandfly Security API. You need to:

1. **Authenticate to the API**
   - Use the /v4/auth/login endpoint
   - Store the access_token for subsequent requests
   - Use Bearer token authentication

2. **Discover All Endpoints**
   Research these known endpoints and find more:
   - `/v4/version` - System version info
   - `/v4/hosts` - Monitored hosts
   - `/v4/results` - Scan results
   - Look for: `/v4/alerts`, `/v4/sandboxes`, `/v4/policies`, `/v4/users`, `/v4/stats`, etc.

3. **Document Data Structures**
   For each endpoint, document:
   - HTTP method (GET/POST/PUT/DELETE)
   - Required parameters
   - Response structure and fields
   - Pagination support
   - Filter options
   - Example responses

4. **Identify Metrics for Prometheus**
   Determine which data should be exposed as Prometheus metrics:
   - Counters (ever-increasing values)
   - Gauges (point-in-time values)
   - Labels (dimensions like hostname, IP, severity)
   - Info metrics (version, configuration)

## Output Format
Create a comprehensive markdown document: `/Users/ryandahlberg/Projects/cortex/mcp-servers/cortex/SANDFLY_API_RESEARCH.md`

Structure:
```markdown
# Sandfly API Research - Complete Documentation

## API Overview
- Base URL: https://10.88.140.176/v4
- Authentication: Bearer token
- Version: [discovered version]

## Authentication
[Document auth endpoint and token handling]

## Available Endpoints

### 1. /v4/endpoint-name
- **Method:** GET/POST
- **Purpose:** [what it does]
- **Parameters:** [query params, body params]
- **Response Structure:** [JSON structure]
- **Pagination:** [yes/no, how it works]
- **Example Response:** [real example]
- **Prometheus Metrics:** [which metrics to create from this data]

[Repeat for all endpoints]

## Recommended Metrics for Prometheus

### Host Metrics
- sandfly_hosts_total (Gauge)
- sandfly_hosts_online (Gauge)
[etc.]

### Alert Metrics
[list metrics]

### Scan Metrics
[list metrics]

[etc.]

## API Rate Limits and Best Practices
[Document any limits or recommendations]
```

## Success Criteria
- [ ] All API endpoints discovered and documented
- [ ] Data structures fully documented with examples
- [ ] Clear recommendations for Prometheus metrics
- [ ] Ready for Daryl-2 to implement exporter

## Tips
- Use curl or Python requests to explore the API
- Try common REST patterns: /v4/stats, /v4/health, /v4/system
- Look at response headers for clues about other endpoints
- Check for hypermedia links in responses
- Test pagination on large datasets
- Note any rate limits or throttling

## Start Your Research
Begin by authenticating and then systematically explore the API. Be thorough - Daryl-2 needs complete information to build a comprehensive exporter.
