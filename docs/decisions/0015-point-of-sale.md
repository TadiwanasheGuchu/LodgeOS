# 0015 — Point of sale on top of invoices and payments

**Status:** Accepted, 2026-11-23

## Context
Lodges sell drinks, meals, activities and curios at a bar, restaurant or shop. In-house guests want these on their room bill, settled at check-out; day visitors pay at once. Sales must be fast on a tablet, priced with the property's taxes, and end up in the same books as room revenue, without a second money system.

## Decision
- **Catalogue.** Outlets (`pos_outlets`: Bar, Restaurant, Curio shop) and items (`services`) per property. Each item has a price, whether the price includes tax, and which of the property's taxes apply. Items are archived, never deleted.
- **Each sale is settled when it is rung up**; there are no open tabs in this milestone. A sale is a `pos_orders` row with its items, prices and taxes copied from the catalogue at that moment.
  - **Charge to room:** for a checked-in booking only. The lines are added to that booking's draft invoice (the folio), which is created when needed. If the stay is not yet invoiced, its rooms are added too, so the guest gets one bill at check-out.
  - **Paid now:** a separate invoice is issued at once (to the guest's name or "Walk-in guest"), and the payment is recorded and allocated to it (ADR-0010). The cash-up shows it like any other payment.
- **Money stays in invoicing and payments.** Lines are computed with the ADR-0007 rule through the invoicing service. A POS sale is never edited afterwards: room charges can be removed from the draft folio before it is issued; issued sales are corrected with a credit note (ADR-0009).
- **Idempotency.** Each sale carries a client key, unique per organisation. A tablet that retries after a dropped connection does not charge twice.
- **Permissions.** `pos.sell` (owner, manager, receptionist) and `pos.manage` for the catalogue (owner, manager), property-scoped. Selling needs no invoice or payment permission. The POS service acts on the seller's behalf for the folio and payment, within the property.

## Consequences
- Bar charges appear on the folio and the cash-up with no extra reconciliation.
- Open tabs, kitchen tickets, stock control and card terminals are later work; they can build on `pos_orders`.
