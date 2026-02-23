# EVA ERP Monitoring Runbook

## What Is Monitored

The monitoring runner executes periodic checks for:

- ERP database (`erp-db`)
- EVA database (`eva-db`)
- ERP API (`erp-api`)
- ERP frontend (`erp-frontend`)
- FMAccesorios ERP frontend (`fmac-erp-frontend`)
- FMAccesorios ERP backend (`fmac-erp-backend`)
- FMAccesorios ERP database (`fmac-erp-db`, requires `MONITORING_FMAC_ERP_DB_URL`)
- EVA API (`eva-api`)
- Supabase Auth (`supabase-auth`, when Supabase URL is configured)
- Supabase Admin (`supabase-admin`, when Supabase URL is configured)
- OpenAI API (`openai-api`)
- FacturAPI (`facturapi-api`)
- EVA WhatsApp endpoint (`eva-whatsapp`, only if configured)

## Trigger Rules

- A check status is `up`, `degraded`, or `down`.
- `degraded` and `down` count as failures.
- Auth-protected checks can define allowed statuses (for FM backend, `401/403` are treated as reachable = `up`).
- Issue opens automatically after:
- `MONITORING_FAILURE_THRESHOLD_CRITICAL` consecutive failures for critical checks.
- `MONITORING_FAILURE_THRESHOLD_DEFAULT` consecutive failures for non-critical checks.
- Issue auto-resolves after `MONITORING_RECOVERY_THRESHOLD` consecutive successful checks.
- Existing resolved issues are automatically reopened on regression.

## Alerting

- If `MONITORING_SLACK_WEBHOOK_URL` is configured, Slack notifications are sent on:
- issue opened
- issue reopened
- issue resolved

## Endpoints

- `GET /health/liveness`: process alive.
- `GET /health`: core DB readiness summary.
- `GET /health/readiness`: DB + critical dependency readiness.
- `GET /api/v1/eva-platform/monitoring/services`: current status snapshot.
- `GET /api/v1/eva-platform/monitoring/overview`: issue summary KPIs.
- `GET /api/v1/eva-platform/monitoring/issues`: issue list.
- `GET /api/v1/eva-platform/monitoring/checks`: recent check history.

## Operational Notes

- The monitoring runner starts automatically with the API app lifespan.
- Checks are persisted into `admin_monitoring_checks`.
- Incidents are managed in `admin_monitoring_issues`.
- If Eva DB is not configured, monitoring endpoints still return live service checks, but issue/check history will be empty.
