# Observability Architecture

Comprehensive observability system for monitoring, debugging, and alerting.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      REQUEST FLOW                                │
├─────────────────────────────────────────────────────────────────┤
│  Request ──► RequestContextMiddleware ──► Route Handler          │
│      │              │                           │                │
│      │         Set request_id              Process request       │
│      │         Bind to logs                     │                │
│      │              │                           │                │
│      │              ▼                           ▼                │
│      │      ┌──────────────┐           ┌──────────────┐         │
│      │      │ structlog    │           │ Sentry       │         │
│      │      │ (all logs)   │           │ (errors)     │         │
│      │      └──────────────┘           └──────────────┘         │
│      │                                                          │
│      │         Record metrics                                   │
│      │              │                                           │
│      │              ▼                                           │
│      │      ┌──────────────┐                                    │
│      │      │ PerfMetrics  │──► /health/metrics                 │
│      │      │ (in-memory)  │                                    │
│      │      └──────────────┘                                    │
│      │                                                          │
│      │         Sample slow/error requests                       │
│      │              │                                           │
│      │              ▼                                           │
│      │      ┌──────────────┐                                    │
│      │      │ RequestTrace │──► request_trace table             │
│      │      │ (async DB)   │                                    │
│      │      └──────────────┘                                    │
│      │                                                          │
│      ▼                                                          │
│  Response with X-Request-ID header                              │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Request Context (`app/middleware/context.py`)

Every request gets a unique identifier for tracing:

```python
# Headers
X-Request-ID: req_abc123      # Unique per request (generated or passed)
X-Correlation-ID: corr_xyz    # For distributed tracing across services
```

**Features:**
- Auto-generates request ID if not provided
- Validates IDs to prevent log injection attacks
- Binds to structlog for automatic log enrichment
- Returns request_id in response headers

### 2. Performance Metrics (`app/core/perf_metrics.py`)

In-memory metrics aggregated per endpoint:

```python
{
    "/api/v1/cards": {
        "count": 1523,
        "latencies": [12.3, 45.6, ...],  # Rolling window
        "status_codes": {"200": 1500, "500": 23}
    }
}
```

**Exposed via `/health/metrics`:**
```json
{
    "endpoints": {
        "/api/v1/cards": {
            "count": 1523,
            "p50_ms": 23.4,
            "p95_ms": 89.2,
            "p99_ms": 156.7,
            "error_rate": 0.015
        }
    },
    "uptime_seconds": 3600
}
```

### 3. Request Trace Sampling (`request_trace` table)

Slow or error requests are persisted for debugging:

```sql
CREATE TABLE request_trace (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(64),
    method VARCHAR(10),
    path VARCHAR(500),
    status_code INTEGER,
    duration_ms FLOAT,
    user_id INTEGER,
    error_type VARCHAR(100),
    error_message VARCHAR(1000),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Sampling rules:**
- Requests slower than 500ms
- Requests with 5xx status codes
- Bounded queue (max 50 concurrent) to prevent overload

### 4. Sentry Integration (`app/core/sentry.py`)

Optional error tracking with Sentry:

```python
# Configuration
SENTRY_DSN=https://xxx@sentry.io/123
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions
```

**Features:**
- Automatic exception capture
- Performance tracing
- User context (user_id, email)
- Request context (request_id, path, method)
- Environment tagging

### 5. Circuit Breakers (`app/core/circuit_breaker.py`)

Protect against cascade failures:

```
CLOSED ──(5 failures)──► OPEN ──(60s timeout)──► HALF-OPEN
   ▲                                                  │
   └──────────────(3 successes)───────────────────────┘
```

**Status endpoint `/health/circuits`:**
```json
{
    "circuits": {
        "ebay": {"state": "closed", "failure_count": 0},
        "blokpax": {"state": "open", "failure_count": 5, "opens_at": "..."},
        "opensea": {"state": "half_open", "success_count": 2}
    },
    "all_healthy": false
}
```

**Discord alerts:**
- Circuit OPEN: Scraper failing, blocked
- Circuit HALF-OPEN: Testing recovery
- Circuit CLOSED: Recovered

## Browser Manager Safety

The browser scraper has multiple safety limits:

```
┌─────────────────────────────────────────────────────────────┐
│                   RESTART LIMITS                             │
├─────────────────────────────────────────────────────────────┤
│  Per-cycle limit (BROWSER_MAX_RESTARTS=3)                   │
│    └─► Extended cooldown with exponential backoff           │
│                                                             │
│  Absolute limit (BROWSER_MAX_TOTAL_RESTARTS=20)             │
│    └─► RuntimeError - manual intervention required          │
│                                                             │
│  Memory limit (BROWSER_MAX_PAGES_BEFORE_RESTART=25)         │
│    └─► Proactive restart to prevent memory leaks            │
└─────────────────────────────────────────────────────────────┘
```

**Exponential backoff:**
```
Cycle 1: 10s cooldown
Cycle 2: 20s cooldown  (10 * 2^1)
Cycle 3: 40s cooldown  (10 * 2^2)
Cycle 4: 80s cooldown  (10 * 2^3)
...
Max: 300s (5 minutes)
```

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Basic liveness check |
| `/health/detailed` | DB, scheduler, scraper status |
| `/health/circuits` | Circuit breaker states |
| `/health/metrics` | Performance metrics |

## Debugging Workflows

### Find all logs for a request

```bash
# In Railway/Docker logs
grep "request_id=req_abc123" logs.txt
```

### Investigate slow requests

```sql
SELECT * FROM request_trace
WHERE duration_ms > 1000
ORDER BY created_at DESC
LIMIT 20;
```

### Check error patterns

```sql
SELECT path, status_code, COUNT(*), AVG(duration_ms)
FROM request_trace
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY path, status_code
ORDER BY COUNT(*) DESC;
```

### Monitor circuit breaker history

```sql
SELECT * FROM circuit_breaker_state
ORDER BY updated_at DESC
LIMIT 50;
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `SENTRY_DSN` | `""` | Sentry DSN (empty = disabled) |
| `SENTRY_ENVIRONMENT` | `production` | Environment tag |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Transaction sample rate |
| `TRACE_QUEUE_MAX_SIZE` | `50` | Max concurrent trace writes |
| `BROWSER_MAX_TOTAL_RESTARTS` | `20` | Hard browser restart limit |
