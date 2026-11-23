# Deployment

Status: **local development only.** No staging or production environment exists. Do not deploy to production without explicit approval (`CLAUDE.md` §16).

## Local development

Requirements: Docker, Python 3.12+, [uv](https://docs.astral.sh/uv/).

```bash
docker compose up -d postgres redis
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m app.cli bootstrap-organisation \
  --name "Demo Guesthouse" --slug demo-guesthouse \
  --currency NAD --timezone Africa/Windhoek --country NA \
  --owner-email owner@demo-guesthouse.example.com --owner-name "Demo Owner"
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

Frontend (second terminal):

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000, forwards /api/* to the API on :8000
```

Add staff to an organisation (until invitations exist):

```bash
uv run python -m app.cli add-member --org demo-guesthouse \
  --email desk@demo-guesthouse.example.com --name "Front Desk" --role receptionist
```

Frontend checks: `npm run lint`, `npm run typecheck`, `npm test`. End-to-end (needs Postgres, Redis and migrations; starts the API and a production build itself): `npm run build && npm run e2e`.

Backend tests (needs the compose Postgres and Redis running; creates and drops `lodgeos_test`):

```bash
cd backend && uv run pytest
```

The database roles are created by `infra/postgres/init/01-roles.sh` the first time the Postgres volume is initialised. To start over: `docker compose down -v`.

## Container image

```bash
docker build -t lodgeos-api backend
```

Behind a TLS-inspecting proxy, pass its CA as a build secret (not stored in the image):

```bash
docker build --secret id=extra_ca,src=/path/to/ca.crt -t lodgeos-api backend
```

The image runs as uid 10001 and does **not** run migrations on start. Migrations are an explicit release step run with the owner credentials:

```bash
docker run --rm -e LODGEOS_MIGRATION_DATABASE_URL=... lodgeos-api alembic upgrade head
```

## Email worker

Emails are written to the `notifications` outbox by the API and delivered by a separate process (ADR-0011). In Compose it is the `worker` service; elsewhere run:

```bash
python -m app.cli deliver-notifications            # runs until stopped, polls every 5 s
python -m app.cli deliver-notifications --once     # deliver what is due, then exit
```

The worker needs only `LODGEOS_DATABASE_URL` (the `lodgeos_app` role) and `LODGEOS_REDIS_URL`. Provider settings:

| Variable | Default | Notes |
|---|---|---|
| `LODGEOS_EMAIL_PROVIDER` | `mock` | `mock` records messages in Redis (`mock-mailbox`) and sends nothing; the UI labels them "test mode". Production refuses `mock` |
| `LODGEOS_EMAIL_FROM_ADDRESS` | `bookings@lodgeos.local` | Sender address on a domain with SPF, DKIM and DMARC set up for the provider |
| `LODGEOS_SMTP_HOST`, `LODGEOS_SMTP_PORT` | `localhost`, `587` | Provider's SMTP submission host |
| `LODGEOS_SMTP_USERNAME`, `LODGEOS_SMTP_PASSWORD` | none | Keep the password in the secret store, never in the repository |
| `LODGEOS_SMTP_SECURITY` | `starttls` | `starttls` (587), `tls` (465) or `none` (local testing only) |

## Production checklist (to be completed in Phase 6)

- Choose an email provider, set the SMTP variables, configure SPF/DKIM/DMARC, and send one real message per template before go-live.
- Separate, generated passwords for `postgres`, `lodgeos_owner` and `lodgeos_app`; the API receives only the `lodgeos_app` URL.
- Frontend: set `LODGEOS_API_ORIGIN` to the internal API address; serve both behind the same domain.
- `LODGEOS_ENVIRONMENT=production` (disables `/docs` and `/openapi.json`), `LODGEOS_COOKIE_SECURE=true`.
- TLS at Caddy or Nginx; forward `X-Forwarded-For` and restrict `--forwarded-allow-ips` to the proxy.
- Postgres and Redis not exposed publicly.
- Automated backups with a tested restore procedure.
- Monitoring of `/health/ready`.
