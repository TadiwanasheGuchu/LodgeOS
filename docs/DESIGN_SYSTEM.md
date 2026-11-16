# LodgeOS Design System

Status: **tokens defined; not yet implemented in the frontend** (Phase 0, milestone 0.3).

The non-negotiable rules live in `CLAUDE.md` §10. This document turns them into usable tokens and records how each one may be used.

## Colour

| Token | Hex | Role |
|---|---|---|
| `forest` | `#123C35` | Primary text on light surfaces, primary buttons, navigation background |
| `teal` | `#24796D` | Interactive accents: links, focus rings, selected states, secondary buttons |
| `sage` | `#75A99D` | Decoration only on light surfaces (see restrictions) |
| `mist` | `#E5F2EF` | Subtle fills: selected rows, info panels, hover backgrounds |
| `cloud` | `#F7F9F8` | App background |
| `white` | `#FFFFFF` | Cards, tables, inputs |
| `charcoal` | `#263A36` | Body text |

### Measured contrast (WCAG 2.x)

| Foreground → Background | White | Cloud | Mist | Forest |
|---|---|---|---|---|
| Forest | 12.18 | 11.52 | 10.61 | — |
| Charcoal | 12.06 | 11.41 | 10.50 | 1.01 |
| Teal | 5.21 | 4.93 | 4.53 | 2.34 |
| Sage | **2.65** | **2.51** | **2.31** | 4.59 |
| White | — | 1.06 | 1.15 | 12.18 |

### Usage rules derived from the measurements

- **Body text:** `charcoal` or `forest` on `white` / `cloud` / `mist`. All pass AA and AAA.
- **Teal text:** passes AA for normal text on `white`, `cloud` and `mist` (just: 4.53 on mist). Do not use teal text on any tint darker than `mist`.
- **Sage must not be used for text, icons that carry meaning, input borders or focus indicators on light surfaces.** It fails both the 4.5:1 text and the 3:1 non-text contrast requirements there. Allowed: decorative rules, chart gridlines, illustration fills, and text on `forest` (4.59).
- **Text on forest:** `white` or `sage`. Never `teal` (2.34) or `charcoal` (1.01).
- **Focus ring:** 2px `teal` outline with 2px offset. It meets 3:1 against `white`, `cloud` and `mist`.

### Status colours

Hospitality screens need states (confirmed, checked-in, dirty, out of order, overdue). These states must not rely on brown, orange-brown, amber-brown or any earth tone (`CLAUDE.md` §10). The status palette is to be defined with milestone 0.3. Proposed constraints:
- Every status pairs a colour with an icon or text label; colour alone never carries meaning.
- Error/danger: a clear red. Warning: a clean yellow, checked to not read as brown or amber-brown. Success: from the teal/forest family.
- Each status colour gets measured contrast values in this document before use.

## Typography

| Family | Use |
|---|---|
| Fraunces | Selected display headings only: marketing pages, booking engine property names, empty-state titles. Not for operational screen headings. |
| DM Sans | All interface text |
| IBM Plex Mono | Reservation references, invoice numbers, amounts in tables, IDs |

Operational screens keep headings small (a receptionist needs the arrivals list, not a hero banner). Amounts use tabular figures so columns line up.

## Icons

Lucide only. No emoji in navigation or controls.

## Prohibited

No brown of any kind, and none of the generic patterns listed in `CLAUDE.md` §10 (gradients, glassmorphism, blobs, fake charts, oversized operational headings, decorative animation).

## Per-role information architecture (to be designed)

| Role | Primary device | Home screen focus |
|---|---|---|
| Receptionist | Tablet / desktop | Today's arrivals, departures, in-house, room status |
| Housekeeping | Phone | Assigned rooms, one-tap status changes |
| Manager | Desktop | Occupancy, revenue, exceptions needing attention |
| Owner | Desktop / phone | Performance across properties |
| Accountant | Desktop | Invoices, payments, reconciliation |
| Guest | Phone | Booking details, check-in, requests |
