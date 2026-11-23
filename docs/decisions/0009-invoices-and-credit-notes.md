# 0009 — Invoices, numbering and credit notes

**Status:** Accepted, 2026-11-23

## Context
A lodge must hand the guest (or a company) a tax invoice that matches what was sold, numbered without gaps, and that cannot be altered afterwards. Mistakes are corrected with credit notes, never by editing or deleting. Payments (milestone 3.4) will be allocated to invoices, so the invoice is the unit of what is owed.

## Decision
- **Lifecycle:** `draft` → `issued`, or `draft` → `discarded`. Drafts are freely edited and carry no number. Issuing assigns the number, the issue date (property timezone) and freezes the invoice. Issued invoices are never changed or deleted; they are corrected with credit notes. Discarded drafts are kept for the record.
- **Database enforcement:** triggers refuse any UPDATE of an issued invoice's financial or identifying columns, any change to items of an issued invoice, and any change to credit notes and their items. The app role has no DELETE on invoices or credit notes; it may delete items only of drafts (the trigger checks).
- **Numbering:** one gapless sequence per organisation and document kind (`INV-000001`, `CN-000001`), held in `document_sequences` and taken with `SELECT ... FOR UPDATE` in the issuing transaction, so a rolled-back issue does not consume a number. Numbers are unique per organisation (constraint).
- **Lines from bookings:** each booked room becomes one line copied from its price snapshot (net, each tax, total), so the invoice equals the booking exactly. A booked room can be on only one live invoice at a time (draft or issued and not fully credited); this is checked under a lock on the reservation row.
- **Other lines (extras):** description, quantity, unit price, whether the price includes tax, and which of the property's taxes apply. The line is computed with the ADR-0007 rule (each tax rounded on its own; net absorbs the rounding cent). The tax names and rates are copied onto the line, so later tax changes do not alter it.
- **Credit notes** belong to one issued invoice, need a reason, and credit chosen lines by a gross amount up to what remains uncredited on each line. The tax split of a partial credit uses the line's own rates and the same rounding rule; crediting the whole remainder of a line takes the remaining net and taxes exactly, so a fully credited line nets to zero in every component.
- **Seller details:** properties gain an optional legal name and tax registration number, printed on invoices. No country-specific wording is hard-coded; "Tax invoice" is shown when the property has a tax number, otherwise "Invoice".
- **Permissions:** `invoices.view`, `invoices.manage` (create, edit drafts, issue) and `invoices.credit` (credit notes), all property-scoped. Front desk can invoice; only owners, managers and accountants can credit.

## Consequences
- Totals on an invoice are always the sum of its lines; every line satisfies net + Σtaxes = total.
- What is owed on an invoice is `total − credited`; payments in 3.4 reduce it further.
- Changing a booking after it is invoiced does not change the invoice. Staff credit the old lines and invoice again; the booking screen shows when invoiced rooms have changed (planned with 3.4).
