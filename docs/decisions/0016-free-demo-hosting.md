# 0016 — Free hosting for demos and pilots

**Status:** Accepted, 2026-11-24

## Context
The product owner wants LodgeOS online at no cost, to show it to lodges and let a pilot property try it. Free plans exist, but each has limits that matter for a booking system. This ADR records which services are used, and what "free" does and does not cover. It is not the production setup.

## Decision
- **Render (free web services, Frankfurt)** runs two services from `render.yaml`: the API (Docker image from `backend/`) and the web app (Next.js from `frontend/`). The web app forwards `/api/*` to the API, so cookies stay first-party (ADR-0005).
- **Neon (free Postgres)** instead of Render's free Postgres, which is deleted after 30 days. `infra/neon/setup.sql` creates the two roles (owner for migrations, app role without RLS bypass) and the `btree_gist` extension without superuser rights. The app connects to Neon's **direct** endpoint, not the pooler, because it sets per-transaction RLS settings and asyncpg prepares statements.
- **Upstash (free Redis)** for rate limits and the test-mode mailbox, over TLS (`rediss://`).
- **One process per service.** Free Render has no background workers or pre-deploy steps, so:
  - the API's start script (`backend/deploy/start.sh`) applies migrations, creates the first organisation once (`--if-empty`), then serves;
  - the worker (email delivery, expiring booking holds) runs inside the API (`LODGEOS_RUN_WORKER_IN_API=true`).
- **Environment `staging`.** Emails stay in test mode (the mock provider is refused in `production`), which is right for a demo.
- **Vercel is not used for the web app**: its free Hobby plan is for non-commercial personal use only, and LodgeOS is commercial.
- Rehearsed before release on a local database set up like Neon (non-superuser admin): setup script, migrations, first organisation, sign-in, restart without duplication.

## Consequences
- **Sleep.** Free services sleep after about 15 minutes without visitors; the first visit then takes about a minute. The worker only runs while the API is awake, so booking holds expire on the next visit after they are due.
- **Hours.** Render gives 750 free instance hours per month per workspace, shared by both services. Two services kept busy all month would use more than that.
- **Photos.** Free services have no persistent disk; uploaded photos disappear on redeploy or restart. For lasting photos, set the S3 variables to a free bucket (e.g. Cloudflare R2) (ADR-0014).
- **Data.** Free Neon has limited history for restores and a small storage quota. Use it for demos and a pilot with test data, not for real guest records or real money.
- Moving to paid plans needs no code change: separate worker service, pre-deploy migrations, real email and storage providers, backups (Phase 6).
