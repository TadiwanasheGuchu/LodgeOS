# 0007 — Money representation and tax rounding

**Status:** Accepted, 2026-11-16

## Context
Prices, invoices and payments must reconcile to the cent. Tax rules differ by country and change over time; LodgeOS must not hard-code any of them. Lodges usually quote tax-inclusive prices to guests, while corporate rates may be quoted before tax.

## Decision
- **Representation:** money is `NUMERIC(12,2)` in PostgreSQL, `Decimal` in Python, and a decimal **string** in JSON. Every price-bearing record stores its currency. The browser formats amounts but never calculates them; totals come from the server.
- **Rounding:** `ROUND_HALF_UP` to cents, applied to the stay total and to each tax amount, nowhere else.
- **Taxes** are configured per property (name and percentage), applied to accommodation, calculated on the net amount and not compounded.
- **Each tax amount is rounded on its own** so it equals its rate applied to the net, as a tax invoice requires. When prices include tax, the net is estimated as `total / (1 + Σrates)`, taxes are computed from it, and the final net is `total − Σtaxes`: the rounding cent goes into the net, never into a tax. When prices exclude tax, the total is `net + Σtaxes`.
- **Invariant:** `net + Σtaxes == total` exactly, tested over 4,000 randomised cases.

## Consequences
- A quote's breakdown (nights, net, each tax, total) is stable and can be stored as the reservation's price snapshot in Phase 2.
- An earlier version put the rounding cent on the last tax; it produced VAT one cent off its rate. A regression test pins the corrected behaviour.
- Taxes on extras (meals, activities) and compound taxes are not modelled yet; they will need their own decision when those modules arrive.
