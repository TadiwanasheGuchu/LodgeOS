# Architecture Decision Records

One file per significant decision: `NNNN-short-title.md` with Status, Context, Decision, Consequences. Superseded records stay, marked as superseded.

| # | Decision | Status |
|---|---|---|
| 0001 | Modular monolith | Accepted |
| 0002 | Tenant isolation: server-side session plus PostgreSQL RLS | Accepted |
| 0003 | Server-side sessions with cookie and CSRF token | Accepted |
| 0004 | Fixed role map in Phase 0 | Superseded by 0006 |
| 0005 | Frontend served same-origin, rendered per request | Accepted |
| 0006 | Database roles and property-level access | Accepted |
| 0007 | Money representation and tax rounding | Accepted |
| 0008 | Reservation integrity under concurrency | Accepted |
| 0009 | Invoices, numbering and credit notes | Accepted |
| 0010 | Payments, allocations and refunds | Accepted |
| 0011 | Email notifications through an outbox | Accepted |
| 0012 | Public booking engine | Accepted |
| 0013 | Guest portal through secret links | Accepted |
| 0014 | Photos and logos in S3-compatible storage | Accepted |
