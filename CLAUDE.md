# LodgeOS — Claude Code Project Instructions

> **Product:** LodgeOS  
> **Category:** Hospitality Management & Property Operations SaaS  
> **Tagline:** Hospitality, intelligently managed.  
> **Markets:** Namibia, Zimbabwe, expandable internationally  
> **Architecture:** Multi-tenant modular monolith  
> **Frontend:** Next.js + TypeScript  
> **Backend:** FastAPI + Python  
> **Database:** PostgreSQL  
> **Infrastructure:** Docker + Ubuntu

---

# 1. Your Role

Act as a senior software architect, product designer, full-stack engineer, database engineer, QA engineer and security engineer.

Build LodgeOS as a production-quality hospitality management platform.

Do not approach this project as a simple CRUD application or a generic dashboard template.

Every feature must solve a genuine hospitality business problem.

Prioritise:
- Correct business logic.
- Excellent user experience.
- Financial accuracy.
- Reliable reservation management.
- Multi-tenant security.
- Maintainable architecture.
- Responsive design.
- Production readiness.

Do not generate the entire application in one pass.

Plan, implement, test and verify each milestone.

# 2. Product Direction

LodgeOS serves:

- Guesthouses.
- Boutique hotels.
- Independent lodges.
- Luxury lodges.
- Safari lodges.
- Resorts.
- Serviced apartments.
- Hotel groups.
- Multi-property hospitality operators.

The platform must support businesses of different sizes without requiring small businesses to use unnecessary enterprise features.

## Commercial model

Use a hybrid business model:

1. Monthly SaaS subscriptions.
2. Annual subscriptions.
3. Once-off onboarding and installation.
4. Enterprise licensing.
5. Custom integrations.
6. Professional training and support.

## Booking approach

Support:

- Direct reservations.
- Walk-in reservations.
- Receptionist bookings.
- Group reservations.
- Corporate bookings.
- Public property booking websites.
- External OTA reservations.
- Booking.com and Expedia integrations through approved connectivity arrangements.

# 3. Technology Stack

## Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Radix UI
- Lucide icons
- React Hook Form
- Zod

## Backend

- Python
- FastAPI
- SQLAlchemy
- Pydantic
- Alembic
- REST API
- OpenAPI documentation

## Infrastructure

- PostgreSQL
- Redis
- Celery
- Docker
- Docker Compose
- Ubuntu
- Caddy or Nginx
- S3-compatible storage
- GitHub Actions

## Testing

- Pytest
- Playwright
- Frontend component tests
- API integration tests
- Security tests

Use a modular monolith initially. Do not introduce microservices without a demonstrated architectural need.

# 4. Architecture

Separate the application into these experiences:

1. Marketing website.
2. Platform administration.
3. Organisation administration.
4. Property operations.
5. Public booking engine.
6. Guest self-service portal.

The platform must support multiple organisations, each with multiple properties.

Every tenant-owned record must be properly scoped.

Use PostgreSQL Row-Level Security as an additional tenant isolation mechanism.

Never trust organisation IDs supplied by the frontend.

# 5. Core Modules

Implement these modules as independent backend domains:

1. Authentication and authorisation.
2. Organisations and tenants.
3. Properties and buildings.
4. Room types and physical rooms.
5. Reservations.
6. Availability.
7. Pricing and rate plans.
8. Guest CRM.
9. Check-in and check-out.
10. Housekeeping.
11. Maintenance.
12. Invoicing.
13. Payments and refunds.
14. Expenses.
15. POS.
16. Activities and additional services.
17. Guest portal.
18. Notifications.
19. Reporting and analytics.
20. External integrations.
21. SaaS subscriptions.
22. Audit logging.

Use explicit service boundaries and avoid unnecessary coupling.

# 6. Critical Business Rules

## Reservations

- Every reservation must have a unique reference.
- Support multiple rooms per reservation.
- Support room-type bookings before physical room allocation.
- Support booking modifications.
- Record cancellation reasons.
- Maintain reservation status history.
- Prevent overlapping physical room allocations.
- Protect room-type inventory against concurrent bookings.
- Use database transactions for availability and booking operations.
- Use idempotency for external booking and payment events.

## Room management

Separate:
- Booking availability.
- Physical occupancy.
- Housekeeping status.
- Maintenance status.

A room being dirty must not be confused with a room being unoccupied or available for sale.

## Pricing

Support:
- Standard rates.
- Seasonal rates.
- Weekend rates.
- Corporate rates.
- Promotional rates.
- Package rates.
- Extra guest charges.
- Configurable taxes.

Preserve the original pricing breakdown on reservations and invoices.

## Financial management

- Use NUMERIC monetary fields.
- Store currency explicitly.
- Never use floating-point values for money.
- Never delete posted financial transactions.
- Use reversals, adjustments and credit notes.
- Keep payment allocations traceable.
- Distinguish invoice value from cash received.
- Preserve historical exchange rates and pricing snapshots.

## Localisation

Support:
- NAD.
- ZAR.
- USD.
- Additional configurable currencies.
- Property-specific timezones.
- Configurable tax rules.
- Configurable check-in and check-out policies.

Never hardcode country-specific tax assumptions.

# 7. Database Requirements

Use PostgreSQL and SQLAlchemy.

All major entities must use UUID primary keys.

Required database domains:

- organisations
- organisation_users
- properties
- buildings
- users
- roles
- permissions
- user_roles
- room_types
- rooms
- room_blocks
- rate_plans
- seasonal_rates
- reservations
- reservation_rooms
- reservation_guests
- guests
- guest_preferences
- guest_consents
- invoices
- invoice_items
- payments
- payment_allocations
- refunds
- credit_notes
- expenses
- housekeeping_tasks
- maintenance_tickets
- services
- activities
- activity_bookings
- pos_orders
- pos_order_items
- notifications
- integrations
- integration_events
- subscriptions
- subscription_plans
- audit_logs

Use foreign keys, indexes, unique constraints and proper database migrations.

Implement transaction-safe room allocation and inventory management.

Never rely exclusively on frontend validation.

# 8. Security

Follow OWASP security guidance.

Implement:

- Argon2id password hashing or a trusted external identity provider.
- Secure session management.
- Optional MFA.
- RBAC.
- Property-level permissions.
- Tenant isolation.
- PostgreSQL RLS.
- TLS.
- Encrypted secrets.
- Secure file uploads.
- API rate limiting.
- Input validation.
- CSRF protection where applicable.
- Webhook signature validation.
- Audit logs.
- Dependency scanning.
- Backup and recovery procedures.

Never store raw payment card information.

Do not expose sensitive guest information to unauthorised staff.

Platform administrators must not receive unrestricted access to tenant records by default.

# 9. Integrations

Build independent adapters for:

- WhatsApp Business Platform.
- Transactional email.
- Payment gateways.
- SMS providers.
- S3-compatible storage.
- Booking.com.
- Expedia.
- SiteMinder or equivalent channel managers.
- Google Maps.
- Accounting integrations.

Use retry handling, idempotency, integration event logs and reconciliation.

Do not assume that external API access is available without commercial approval.

# 10. Design System — Non-Negotiable

## Brand direction

Forest & Teal.

## Colour palette

| Token | Hex |
|---|---|
| Forest | #123C35 |
| Teal | #24796D |
| Sage | #75A99D |
| Mist | #E5F2EF |
| Cloud | #F7F9F8 |
| White | #FFFFFF |
| Charcoal | #263A36 |

## Absolute colour prohibition

**NO BROWN OF ANY KIND.**

Prohibited:
- Coffee brown.
- Chocolate brown.
- Tan.
- Caramel.
- Bronze.
- Copper.
- Terracotta.
- Rust.
- Earth tones.
- Brownish grey.
- Brown gradients.

This applies to all interfaces, backgrounds, components, icons, illustrations, marketing pages and generated imagery.

Do not introduce alternative brown colours without explicit product-owner approval.

## Typography

- Fraunces: selected display headings.
- DM Sans: interface typography.
- IBM Plex Mono: financial references and identifiers.

## Icons

Use Lucide icons consistently.

Do not use emojis as application navigation icons.

## Anti-AI-generic rules

Never generate:

- Generic SaaS dashboard templates.
- Repetitive card grids.
- Random gradients.
- Purple/blue gradient decorations.
- Glassmorphism everywhere.
- Excessively rounded interfaces.
- Decorative blobs.
- Fake charts.
- Oversized operational headings.
- Random shadows.
- Unnecessary animations.
- Generic stock imagery.
- Repetitive landing-page sections.
- Inconsistent typography.
- Unfinished buttons.
- Non-functional controls.

Design screens around real hospitality workflows.

Use different information architectures for owners, managers, receptionists, housekeeping staff, accountants and guests.

## Design research

Study relevant design patterns from:

- Dribbble.
- Awwwards.
- Behance.
- Lapa Ninja.
- Mobbin.

Study hospitality platforms such as Cloudbeds, Mews and Little Hotelier for workflow inspiration.

Do not copy designs.

Every design decision must serve LodgeOS's identity and usability.

# 11. Responsive Design

Build mobile-first where the user workflow requires it.

Prioritise:

- Mobile housekeeping.
- Mobile guest portal.
- Mobile booking engine.
- Tablet reception.
- Desktop property administration.
- Desktop financial reporting.

Support installable PWA functionality.

Optimise for slower Southern African internet connections.

# 12. Performance

Initial engineering targets:

- LCP below 2.5 seconds on representative supported devices.
- Common API response below 500ms at p95 under the defined test load.
- Availability search below 1 second at p95 under the defined test load.
- No duplicate physical room allocations.
- WCAG 2.2 AA accessibility target.

Use pagination, indexing, query optimisation, background processing and image optimisation.

Do not compromise booking correctness for caching performance.

# 13. Testing Requirements

Test:

- Tenant isolation.
- Role permissions.
- Concurrent bookings.
- Reservation cancellations.
- Booking modifications.
- Room availability.
- Check-in and check-out.
- Pricing calculations.
- Invoice generation.
- Partial payments.
- Refunds.
- Payment webhook duplication.
- Currency handling.
- Property timezones.
- Guest portal authorisation.
- Subscription restrictions.
- Backup restoration.

All critical financial and reservation workflows require automated tests.

Do not mark a feature complete until its acceptance tests pass.

# 14. Development Roadmap

Follow this sequence.

## Phase 0 — Foundation
- Repository setup.
- Architecture documentation.
- Docker.
- PostgreSQL.
- Redis.
- Authentication.
- Multi-tenancy.
- Design tokens.
- CI/CD.

## Phase 1 — Property Management
- Organisations.
- Properties.
- Buildings.
- Room types.
- Physical rooms.
- Staff and permissions.
- Rate plans.

## Phase 2 — Reservations
- Availability.
- Reservation engine.
- Booking calendar.
- Guest CRM.
- Pricing.
- Check-in and check-out.

## Phase 3 — Operations and Finance
- Housekeeping.
- Maintenance.
- Invoicing.
- Payments.
- Refunds.
- Reconciliation.
- Notifications.

## Phase 4 — Booking Commerce
- Public booking engine.
- Guest portal.
- Payment integrations.
- Property branding.
- Booking confirmations.

## Phase 5 — Advanced Hospitality
- POS.
- Activities.
- Analytics.
- Subscriptions.
- Channel management.

## Phase 6 — Production Launch
- Security testing.
- Performance testing.
- Backup restoration.
- Pilot deployment.
- Training.
- Monitoring.

# 15. Required Documentation

Maintain:

- README.md
- PROJECT_STATUS.md
- CHANGELOG.md
- docs/PRODUCT_REQUIREMENTS.md
- docs/SYSTEM_ARCHITECTURE.md
- docs/DATABASE_SCHEMA.md
- docs/SECURITY.md
- docs/API_SPECIFICATION.md
- docs/DESIGN_SYSTEM.md
- docs/INTEGRATIONS.md
- docs/DEPLOYMENT.md
- docs/decisions/

Update PROJECT_STATUS.md after every completed milestone.

Document important architectural decisions.

# 16. Claude Code Working Protocol

Before implementation:

1. Inspect the existing repository.
2. Read this entire CLAUDE.md.
3. Identify existing code and dependencies.
4. Prepare a detailed implementation plan.
5. Identify risks and architectural dependencies.
6. Create the required documentation.
7. Establish acceptance criteria.

During implementation:

1. Work module by module.
2. Follow established naming conventions.
3. Use database migrations.
4. Write automated tests.
5. Run backend and frontend checks.
6. Verify actual functionality.
7. Review security.
8. Update project documentation.

After every milestone:

- Report completed functionality.
- Report tests executed.
- Report failed tests.
- Identify incomplete functionality.
- Update PROJECT_STATUS.md.
- Identify the next development milestone.

Never claim an integration works without testing it against the actual provider or a clearly identified mock environment.

Never replace working functionality with placeholders.

Never silently remove existing functionality.

Never expose production credentials.

Do not deploy to production without explicit approval.

Do not add AI attribution to contributions: no `Co-Authored-By` or `Claude-Session` trailers in commit messages, and no "Generated with" lines in pull request descriptions.

# 17. Definition of Done

A module is complete only when:

- Its database schema exists.
- Its migrations work.
- Its backend endpoints work.
- Its permissions are enforced.
- Its frontend is functional.
- Its responsive layouts are verified.
- Its error states are handled.
- Its automated tests pass.
- Its documentation is updated.

# Final Instruction

Build LodgeOS as a serious commercial hospitality platform.

Do not optimise for the number of screens generated.

Optimise for reliability, operational usefulness, design quality, security and customer value.

The first priority is a dependable, sellable MVP that can be demonstrated to a real guesthouse or lodge in Namibia.

Expand the platform only after the foundational workflows have been verified.

**Quality over quantity. Working software over mockups. Hospitality workflows over generic dashboards.**
