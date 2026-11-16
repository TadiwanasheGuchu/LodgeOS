# 0001 — Modular monolith

**Status:** Accepted, 2026-11-16

## Context
LodgeOS has ~22 business domains, but a small team, a first customer with 5–40 rooms, and correctness requirements (bookings, money) that depend on database transactions spanning several domains: a check-in touches reservations, rooms, housekeeping and invoices.

## Decision
One FastAPI application and one PostgreSQL database, with each domain as a module under `backend/app/modules/` that exposes a service layer. Background work runs in Celery workers from the same codebase.

## Consequences
- Cross-domain operations can be one ACID transaction; no distributed sagas.
- One deployment unit and one test suite.
- Module boundaries are enforced by convention and review, not by the network. If a module later needs independent scaling, its service interface is the seam to extract it along.
