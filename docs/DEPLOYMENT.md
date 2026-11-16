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

Tests (needs the compose Postgres and Redis running; creates and drops `lodgeos_test`):

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

## Production checklist (to be completed in Phase 6)

- Separate, generated passwords for `postgres`, `lodgeos_owner` and `lodgeos_app`; the API receives only the `lodgeos_app` URL.
- `LODGEOS_ENVIRONMENT=production` (disables `/docs` and `/openapi.json`), `LODGEOS_COOKIE_SECURE=true`.
- TLS at Caddy or Nginx; forward `X-Forwarded-For` and restrict `--forwarded-allow-ips` to the proxy.
- Postgres and Redis not exposed publicly.
- Automated backups with a tested restore procedure.
- Monitoring of `/health/ready`.
