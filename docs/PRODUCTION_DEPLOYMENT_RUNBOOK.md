# Production Deployment & Operations Runbook

**Document Reference:** `docs/PRODUCTION_DEPLOYMENT_RUNBOOK.md`  
**Platform Owner:** TechMasters Innovations Private Limited  
**Platform:** Bagodi E-Commerce Platform (Anchor Merchant: Bagodi, Bidar, Karnataka)  
**Phase:** 11 — End-to-End System Integration, Performance Benchmarking & Production Hardening  
**Date:** November 2026  
**Status:** Authoritative Standard Operating Procedure (SOP)  

---

## 1. System Architecture & Deployment Topology

The Bagodi E-Commerce Platform backend is built as a high-performance, asynchronous Python service running FastAPI on Uvicorn ASGI workers, backed by PostgreSQL 16+ with connection pooling (`asyncpg`), and integrated with real-world provider sandboxes (Razorpay, Twilio, Shiprocket).

```
                      +-----------------------------+
                      |   Cloudflare / WAF Edge     |
                      | (DDoS, SSL/TLS Termination) |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |      NGINX Reverse Proxy    |
                      |  (Rate Limiting, Gzip, SSL) |
                      +--------------+--------------+
                                     |
                                     v
       +-------------------------------------------------------------+
       |                  Uvicorn ASGI Process Cluster               |
       |  Worker 1          Worker 2          Worker 3      Worker N |
       |  (FastAPI)         (FastAPI)         (FastAPI)     (FastAPI)|
       +-----------------------------+-------------------------------+
                                     |
                                     v
       +-------------------------------------------------------------+
       |                  PostgreSQL 16+ Database Cluster            |
       |     Primary (Read/Write)      <--->     Read Replica(s)     |
       |     Connection Pooler (PgBouncer, max_pool_size: 20-50)     |
       +-------------------------------------------------------------+
```

---

## 2. Environment Variables & Secret Configuration

The backend application enforces strict configuration isolation. In production environments (`ENVIRONMENT=production`), the application **refuses to start** if any mock provider is selected, if debug flags are enabled, or if default development secrets are detected.

### 2.1 Complete Environment Catalog

| Variable Name | Required | Default / Staging | Production Requirement / Description |
| :--- | :---: | :--- | :--- |
| `ENVIRONMENT` | Yes | `development` | Set strictly to `production`. |
| `DEBUG` | Yes | `false` | Must be strictly `false`. |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` | Production PostgreSQL connection URI with SSL (`sslmode=require`). |
| `SECRET_KEY` | Yes | Dev placeholder | Cryptographically secure 256-bit random hex key (`openssl rand -hex 32`). Must never match dev defaults. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `15` | JWT Access Token expiration window (recommended: 15 minutes). |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | JWT Refresh Token rotation expiration window (recommended: 7 days). |
| `OTP_EXPIRE_SECONDS` | No | `300` | SMS OTP expiration window (5 minutes). |
| `OTP_PROVIDER` | Yes | `twilio` (or `mock` in dev) | Must be `twilio` in production. |
| `TWILIO_ACCOUNT_SID` | If Twilio | `AC...` | Production Twilio Account SID from Console. |
| `TWILIO_AUTH_TOKEN` | If Twilio | `...` | Production Twilio Auth Token. |
| `TWILIO_PHONE_NUMBER` | If Twilio | `+1...` | Verified Twilio sender phone number or Alphanumeric Sender ID. |
| `TWILIO_WHATSAPP_NUMBER` | If Twilio | `whatsapp:+1...` | Approved Twilio WhatsApp Business number. |
| `PAYMENT_PROVIDER` | Yes | `razorpay` (or `mock` in dev)| Must be `razorpay` in production. |
| `RAZORPAY_KEY_ID` | If Razorpay | `rzp_test_...` | Live Razorpay Key ID (`rzp_live_...`). |
| `RAZORPAY_KEY_SECRET` | If Razorpay | `...` | Live Razorpay Key Secret. |
| `RAZORPAY_WEBHOOK_SECRET` | If Razorpay | `...` | Secret configured in Razorpay Dashboard for webhook signature verification. |
| `COURIER_PROVIDER` | Yes | `shiprocket` (or `mock` in dev)| Must be `shiprocket` in production. |
| `SHIPROCKET_API_USER` | If Shiprocket| `...` | Shiprocket API registered email/username. |
| `SHIPROCKET_API_PASSWORD` | If Shiprocket| `...` | Shiprocket API registered password. |
| `SHIPROCKET_WEBHOOK_TOKEN`| If Shiprocket| `...` | Bearer token configured in Shiprocket webhook settings. |
| `CORS_ORIGINS` | Yes | `["http://localhost:3000"]` | Whitelisted production frontend domains, e.g. `["https://bagodi.com", "https://admin.bagodi.com"]`. |

### 2.2 Production Guard Lifespan Check
As implemented in `backend/app/core/config.py` and invoked in `backend/app/main.py`:
```python
if settings.ENVIRONMENT == "production":
    if settings.DEBUG:
        raise RuntimeError("CRITICAL: DEBUG cannot be enabled in production")
    if settings.SECRET_KEY in ["dev-secret-key-change-in-production", ""]:
        raise RuntimeError("CRITICAL: Default SECRET_KEY forbidden in production")
    if settings.PAYMENT_PROVIDER == "mock" or settings.OTP_PROVIDER == "mock" or settings.COURIER_PROVIDER == "mock":
        raise RuntimeError("CRITICAL: Mock providers are strictly forbidden in production")
```

---

## 3. Containerized Deployment & Startup Sequence

### 3.1 Dockerfile Specification
```dockerfile
# Multi-stage production Dockerfile
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install
COPY backend /app

# Non-root user for security
RUN addgroup --system --gid 1001 bagodi && \
    adduser --system --uid 1001 --ingroup bagodi bagodi && \
    chown -R bagodi:bagodi /app

USER bagodi

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

### 3.2 Automated Startup Sequence
In any container orchestration platform (Kubernetes, AWS ECS, Docker Compose), services must start in the following strict order:
1. **PostgreSQL Database Ready:** Health probe must return exit code 0 (`pg_isready -h db -U postgres`).
2. **Database Migrations:** Run Alembic migration to `head` via an init-container or pre-deploy job:
   ```bash
   alembic upgrade head
   ```
   *Safety check:* If migrations fail, the deployment immediately halts; the web server containers must **never** boot on an unmigrated database.
3. **Application Boot:** Uvicorn workers initialize, run lifespan configuration validation, establish database connection pools, and start listening on port 8000.
4. **Outbox Worker Dispatcher:** Launch the background transactional outbox worker process:
   ```bash
   python -m app.modules.notifications.outbox_worker
   ```

---

## 4. Health Check Probes & Monitoring

The application exposes two dedicated health endpoints for Kubernetes / load balancer health checking:

### 4.1 Liveness Probe (`GET /api/v1/health`)
- **Purpose:** Verifies that the Uvicorn process is responsive and not deadlocked.
- **Response:** `200 OK` `{"status": "ok", "timestamp": "2026-11-09T04:00:00Z"}`.
- **Kubernetes Configuration:**
  ```yaml
  livenessProbe:
    httpGet:
      path: /api/v1/health
      port: 8000
    initialDelaySeconds: 5
    periodSeconds: 10
    failureThreshold: 3
  ```

### 4.2 Readiness Probe (`GET /api/v1/health/ready`)
- **Purpose:** Verifies that the service has active connectivity to the PostgreSQL database pool and that critical background channels are clear.
- **Behavior:** Executes a lightweight `SELECT 1` ping across the connection pool. Returns `503 Service Unavailable` if the database is unreachable, removing the pod from ingress traffic routing.
- **Kubernetes Configuration:**
  ```yaml
  readinessProbe:
    httpGet:
      path: /api/v1/health/ready
      port: 8000
    initialDelaySeconds: 10
    periodSeconds: 5
    failureThreshold: 2
  ```

---

## 5. Performance & Worker Tuning Guidelines

Based on Phase 11 performance benchmarks:
- **FastAPI/Uvicorn Throughput:** Single-worker baseline achieves 380+ req/s on catalog read operations and 130+ req/s on complex analytical aggregations.
- **Recommended Uvicorn Workers:** Formula: `(2 * CPU_CORES) + 1`. On a standard 4-vCPU production container, run **8 to 9 Uvicorn workers**.
- **PostgreSQL Connection Pool:**
  - `max_overflow`: 10
  - `pool_size`: 20 per worker process
  - PgBouncer in transaction-pooling mode is strongly recommended when scaling beyond 4 container replicas.

---

## 6. Disaster Recovery, Backup & Rollback Runbook

### 6.1 Database Automated Backup Procedure
- **Automated Physical Backup:** Enable Cloud Provider Continuous Archiving / WAL Archiving (WAL-G, AWS RDS Automated Backups, or GCP Cloud SQL PITR) with a 30-day retention window.
- **Logical Schema & Data Dump:** Run daily logical snapshots using the verified backup script:
  ```bash
  cd backend && PYTHONPATH=. .venv/bin/python scripts/backup_and_restore.py
  ```
- **CLI Native Dump:**
  ```bash
  pg_dump -h <host> -U <user> -d <dbname> -F c -b -v -f /backups/bagodi_backup_$(date +%Y%m%d_%H%M%S).dump
  ```

### 6.2 Database Rollback / Downgrade Procedure
If a newly deployed migration causes an unexpected production regression:
1. **Stop Web Traffic:** Point ingress to a static maintenance page or rollback the container image to the previous release.
2. **Inspect Migration DAG:** Verify the target revision hash using Alembic:
   ```bash
   alembic history --verbose
   alembic current
   ```
3. **Execute Single-Step Rollback:**
   ```bash
   alembic downgrade -1
   ```
4. **Targeted Rollback:** To rollback to a known good milestone:
   ```bash
   alembic downgrade <revision_id>
   ```
5. **Verify Database Integrity:** Check table counts and zero dummy records:
   ```bash
   pytest tests/test_db_schema.py -v
   ```

### 6.3 Disaster Recovery Verification Checklist
In the event of complete primary database failure:
1. Promote read-replica to primary via Cloud Console or patroni failover.
2. Update DNS or connection string endpoint in secret manager (`DATABASE_URL`).
3. Restart application deployment pods to re-initialize connection pools.
4. Verify `/api/v1/health/ready` returns `200 OK`.
5. Check outbox queue processing to ensure pending customer notifications resume delivery.

---

## 7. Incident Response & Troubleshooting Protocol

| Symptom | Probable Cause | Diagnostic Command | Remediation Action |
| :--- | :--- | :--- | :--- |
| **HTTP 500 on Checkout** | Inventory deadlock or insufficient stock exception. | `grep "INSUFFICIENT_STOCK" /var/log/uvicorn/app.log` | Verify inventory balance table; ensure concurrent checkout locks release cleanly. |
| **HTTP 503 on `/health/ready`** | PostgreSQL connection pool exhausted. | `SELECT count(*) FROM pg_stat_activity;` | Increase `pool_size` or tune PgBouncer; terminate lingering idle-in-transaction connections. |
| **Notification Backlog** | Transactional outbox worker stalled or Twilio rate-limited. | `SELECT count(*) FROM outbox_messages WHERE status = 'PENDING';` | Restart outbox worker process; inspect Twilio balance and DLT sender ID logs. |
| **Stale Webhook Rejections** | Razorpay or Shiprocket timestamp drift > 300s. | `grep "STALE_WEBHOOK_TIMESTAMP" /var/log/uvicorn/app.log` | Verify NTP server synchronization on application host (`timedatectl status`). |
| **OTP Verification Failures** | Exceeded attempt limit or expired OTP (> 300s). | `SELECT attempts, expires_at FROM otp_requests WHERE phone = '...';` | Instruct customer to request a new OTP code after resend cooldown. |
