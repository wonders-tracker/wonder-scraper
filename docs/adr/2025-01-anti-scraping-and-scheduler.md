# ADR: Stabilize API Thread Usage And Scraper Memory

- **Status:** Accepted  
- **Date:** 2025-12-30  
- **Context:** FastAPI pods on Railway were exhausting kernel threads (`RuntimeError: can't start new thread`) whenever synchronous dependencies (DB sessions, middleware) tried to use AnyIO’s default thread pool. The anti-scraping middleware also stored every IP/fingerprint forever, so memory ballooned under high traffic. Finally, APScheduler + Playwright scrapers ran inside the API process, competing for CPU/RAM with web requests. We needed repeatable resource limits and a way to separate heavy scraping workloads without rewriting the whole stack.

## Decision

1. **Cap AnyIO worker threads & align resource pools**
   - Added `THREADPOOL_MAX_WORKERS` (default 40) and set AnyIO’s thread limiter during FastAPI startup. The DB engine pool now uses `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` so we never open more Postgres connections than available worker threads. The `/api/v1/cards` cache and default limit were reduced via config knobs to keep JSON payloads and TTLCache sizes bounded.  
2. **Bound the anti-scraping state**
   - Each tracked IP now has a TTL (`ANTI_SCRAPING_STATE_TTL_SECONDS`, default 15 min) and there’s a global max (`ANTI_SCRAPING_MAX_TRACKED_IPS`). When either threshold is exceeded, the middleware purges oldest entries, preventing unbounded dictionaries.  
3. **Split or disable the scheduler per service**
   - Introduced `RUN_SCHEDULER`. API pods can set it to `false` while a dedicated worker (via `scripts/run_scheduler_worker.py`) runs APScheduler/Playwright jobs. This isolates heavy scraping from request serving; if desired, we can still keep the scheduler in a single-process deployment by leaving the flag `true`.  
4. **Runtime observability**
   - Added optional RSS logging (`MEMORY_LOG_INTERVAL_SECONDS`) so pods can periodically emit memory usage without needing psutil. This helps us verify that new limits are holding steady after deployments.

## Consequences

- API pods now refuse to spawn more than `THREADPOOL_MAX_WORKERS` async-to-sync threads; excess synchronous work queues instead of crashing the process. DB connections are right-sized and won’t balloon when concurrency spikes.
- The anti-scraping middleware no longer leaks memory as new IPs hit `/api/v1/cards` or `/api/v1/market`. In future we can swap the in-memory store for Redis without changing callers.
- Scrapers can run as a separate Railway worker (`python scripts/run_scheduler_worker.py`), keeping Playwright and APScheduler threads out of the API dyno. Deployments need to set `RUN_SCHEDULER=false` on the API service and `true` on the worker.
- Operations can turn on periodic RSS logs whenever debugging memory pressure. Combined with smaller `/cards` payloads and caches, this should reduce baseline RAM/Gib usage and make memory regressions easier to spot.

These steps collectively mitigate the thread exhaustion class of errors and give us tunable guardrails whenever we need to adjust resource usage for different Railway plans.
