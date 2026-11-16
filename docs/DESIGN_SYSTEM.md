# LodgeOS Design System

Status: **implemented** in `frontend/src/app/globals.css` (Tailwind v4 `@theme`), milestone 0.3.

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

### Supporting tokens (added in 0.3, measured)

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `line` | `#D3E0DC` | Dividers and table rules only | 1.36 on white (decorative) |
| `control` | `#728883` | Borders of inputs and controls | 3.77 on white, 3.57 on cloud (meets 3:1) |
| `muted` | `#4B625D` | Secondary text | 6.55 white, 6.20 cloud, 5.70 mist |
| `danger` | `#B42318` | Errors | 6.57 on white, 5.75 on `danger-tint` |
| `danger-tint` | `#FDECEA` | Error panel background | — |
| `success` | `#1D6B5F` | Confirmations, "active" | 5.52 on `success-tint` |
| `success-tint` | `#E3F3EF` | Success panel background | — |
| `warning` | `#FACC15` | Warning fills and panel borders only (clean yellow, not amber) | 1.53 on white: never text or a meaningful border; forest on it 7.96 |
| `warning-tint` | `#FEF7C3` | Warning panel background | charcoal text 11.09 |

### Status colours

Hospitality states (confirmed, checked-in, dirty, out of order, overdue) must not use brown, orange-brown, amber-brown or any earth tone (`CLAUDE.md` §10).
- Every status pairs a colour with an icon or text label; colour alone never carries meaning.
- Error, success and warning are defined above. Warning text is always charcoal; the yellow is a fill, never a text colour.

## Components (milestone 0.3)

`frontend/src/components/ui/`: `Button` (primary, secondary, ghost, danger; loading state), `Field` + `Input` + `Select` (label, hint and error wired with `aria-describedby` / `aria-invalid`), `Alert` (error, success, info, always with an icon). Native `<select>` is used deliberately: it is accessible and works best on phones.

## Typography

| Family | Use |
|---|---|
| Fraunces | Selected display headings only: marketing pages, booking engine property names, empty-state titles. Not for operational screen headings. |
| DM Sans | All interface text |
| IBM Plex Mono | Reservation references, invoice numbers, amounts in tables, IDs |

Operational screens keep headings small (a receptionist needs the arrivals list, not a hero banner). Amounts use tabular figures so columns line up.

## App icon and PWA

The app icon is a white Fraunces "L" with a sage dot on forest (`frontend/public/icon-*.png`, `src/app/icon.png`, `src/app/apple-icon.png`). The maskable variant keeps the mark inside the central safe zone. The web app manifest (`src/app/manifest.ts`) makes LodgeOS installable. There is no service worker or offline mode yet; offline housekeeping is planned with the housekeeping module.

## Icons

Lucide only. No emoji in navigation or controls.

## Prohibited

No brown of any kind, and none of the generic patterns listed in `CLAUDE.md` §10 (gradients, glassmorphism, blobs, fake charts, oversized operational headings, decorative animation).

## Per-role information architecture (home screens to be designed with Phase 2)

| Role | Primary device | Home screen focus |
|---|---|---|
| Receptionist | Tablet / desktop | Today's arrivals, departures, in-house, room status |
| Housekeeping | Phone | Assigned rooms, one-tap status changes |
| Manager | Desktop | Occupancy, revenue, exceptions needing attention |
| Owner | Desktop / phone | Performance across properties |
| Accountant | Desktop | Invoices, payments, reconciliation |
| Guest | Phone | Booking details, check-in, requests |
