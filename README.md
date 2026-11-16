# LodgeOS

**Hospitality, intelligently managed.**

LodgeOS is a multi-tenant hospitality management platform for guesthouses, lodges, boutique hotels and multi-property operators, starting in Namibia and Zimbabwe.

> Status: **Phase 0 (Foundation) in progress.** See [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.12+, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic |
| Data | PostgreSQL 17 with Row-Level Security, Redis |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI, React Hook Form, Zod |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Quick start

```bash
docker compose up -d postgres redis
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run pytest
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev                             # http://localhost:3000
```

Creating a first organisation and owner: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Repository layout

```
backend/        FastAPI application, migrations, tests
frontend/       Next.js application
infra/          Database initialisation and, later, deployment configuration
docs/           Product, architecture, security and design documentation
docs/decisions/ Architecture decision records
CLAUDE.md       Project instructions and non-negotiable rules
```

## Documentation

- [Product requirements](docs/PRODUCT_REQUIREMENTS.md)
- [System architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [API specification](docs/API_SPECIFICATION.md)
- [Security](docs/SECURITY.md)
- [Design system](docs/DESIGN_SYSTEM.md)
- [Integrations](docs/INTEGRATIONS.md)
- [Deployment](docs/DEPLOYMENT.md)
