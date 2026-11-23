# 0010 — Payments, allocations and refunds

**Status:** Accepted, 2026-11-23

## Context
Money comes in before, during and after a stay: deposits on booking, card or cash at check-out, EFT from a company weeks later. Some of it is returned. Staff must always see what an invoice still owes, the books must show what was actually received (not just invoiced), and every movement must remain traceable. Card data is never handled by LodgeOS (gateways come in Phase 4).

## Decision
- **Payments record money received**: method (cash, card, bank transfer, mobile money, other), amount (> 0), currency, date received (property timezone), payer, reference (slip or EFT reference, never card numbers), optional booking. A payment is never edited or deleted.
- **Allocations link payments to invoices**, append-only. Allocating writes a positive row; releasing writes a negative row. For every payment and invoice pair the running sum stays ≥ 0. A payment's unallocated amount is a deposit or credit on account.
  - An allocation cannot exceed the invoice's balance or the payment's unallocated amount. Currencies must match (no exchange in this milestone).
  - **Invoice balance** = total − credit notes − net allocations. It goes negative when a credit note follows payment; that is an overpayment to release and refund.
- **Refunds record money returned**, from a payment's unallocated amount, with method, reason and date. A refund is a separate immutable row.
- **Reversal** corrects a payment recorded in error (no money moved): the payment gets `reversed_at`, `reversed_by` and a reason, once; its allocations are released by negative rows in the same transaction. A payment with refunds cannot be reversed.
- **Database enforcement:** allocations and refunds are insert-only for the app role. A trigger allows exactly one change to a payment: setting the reversal fields while they are empty. CHECK constraints keep amounts positive (allocation rows non-zero).
- **Concurrency:** allocating, releasing, refunding and reversing lock the payment row, then the invoice row (always in that order), so two staff cannot over-allocate or over-refund.
- **Idempotency:** each payment and refund carries a client-generated `idempotency_key`, unique per organisation. Re-submitting returns the original record rather than recording money twice. External gateway webhooks (Phase 4) will use the same column.
- **Reconciliation (cash-up):** payments and refunds per day and method, for a property and date range, with totals per currency, so cash in the drawer and card-machine totals can be checked against LodgeOS.
- **Permissions:** `payments.view`, `payments.manage` (record, allocate, release), `payments.refund` (refunds and reversals), property-scoped. Front desk records payments; owners, managers and accountants refund and reverse.

## Consequences
- Invoiced value and cash received are separate records and reports.
- A booking's deposit can be taken before any invoice exists and allocated later.
- Multi-currency settlement and gateway integration need their own decisions.
