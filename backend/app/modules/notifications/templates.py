"""Guest email templates (ADR-0011).

Plain Python so every value passes through ``html.escape``. Inline styles only, Forest &
Teal palette, no remote images or tracking. Each template returns subject, text and HTML.
"""

from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from html import escape

FOREST = "#123C35"
TEAL = "#24796D"
MIST = "#E5F2EF"
CLOUD = "#F7F9F8"
CHARCOAL = "#263A36"
LINE = "#D3E0DC"
FONT = "'DM Sans', Arial, Helvetica, sans-serif"
MONO = "'IBM Plex Mono', Menlo, Consolas, monospace"


@dataclass(frozen=True)
class Rendered:
    subject: str
    text: str
    html: str


@dataclass(frozen=True)
class Venue:
    name: str
    address: list[str]
    phone: str | None
    email: str | None
    legal_name: str | None = None
    tax_number: str | None = None


@dataclass(frozen=True)
class Row:
    label: str
    value: str
    mono: bool = False
    strong: bool = False


@dataclass(frozen=True)
class Block:
    heading: str | None
    rows: list[Row] = field(default_factory=list)


def money(amount: Decimal, currency: str) -> str:
    sign = "-" if amount < 0 else ""
    whole, _, frac = f"{abs(amount):.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return f"{currency} {sign}{grouped}.{frac}"


def long_date(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B %Y}"


def _rows_html(rows: list[Row]) -> str:
    out = []
    for r in rows:
        value_style = f"font-family:{MONO};" if r.mono else ""
        weight = "font-weight:600;color:" + FOREST + ";" if r.strong else ""
        out.append(
            f'<tr><td style="padding:6px 12px 6px 0;color:#5B6E6A;vertical-align:top">'
            f"{escape(r.label)}</td>"
            f'<td style="padding:6px 0;text-align:right;{value_style}{weight}">'
            f"{escape(r.value)}</td></tr>"
        )
    return "".join(out)


def _layout(
    venue: Venue,
    title: str,
    intro: list[str],
    blocks: list[Block],
    link: tuple[str, str] | None = None,
) -> tuple[str, str]:
    """Text and HTML bodies with the venue's details as the footer."""
    footer_lines = [venue.legal_name or venue.name, *venue.address]
    if venue.phone:
        footer_lines.append(venue.phone)
    if venue.email:
        footer_lines.append(venue.email)
    if venue.tax_number:
        footer_lines.append(f"Tax number {venue.tax_number}")

    text_parts = [title, "", *intro, ""]
    for b in blocks:
        if b.heading:
            text_parts.append(b.heading.upper())
        text_parts += [f"{r.label}: {r.value}" for r in b.rows]
        text_parts.append("")
    if link:
        text_parts += [f"{link[0]}: {link[1]}", ""]
    text_parts += ["--", *footer_lines]

    blocks_html = "".join(
        (
            f'<h2 style="margin:24px 0 4px;font-size:14px;color:{FOREST}">{escape(b.heading)}</h2>'
            if b.heading
            else ""
        )
        + f'<table role="presentation" style="width:100%;border-collapse:collapse;'
        f'border-top:1px solid {LINE};font-size:14px">{_rows_html(b.rows)}</table>'
        for b in blocks
    )
    intro_html = "".join(f'<p style="margin:0 0 12px">{escape(p)}</p>' for p in intro)
    footer_html = "<br>".join(escape(line) for line in footer_lines)
    link_html = (
        f'<p style="margin:24px 0 0"><a href="{escape(link[1], quote=True)}" '
        f'style="display:inline-block;background:{FOREST};color:#ffffff;text-decoration:none;'
        f'padding:10px 16px;border-radius:6px;font-weight:600">{escape(link[0])}</a></p>'
        if link
        else ""
    )
    html = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title></head>"
        f'<body style="margin:0;background:{CLOUD};font-family:{FONT};color:{CHARCOAL}">'
        f'<div style="max-width:560px;margin:0 auto;padding:24px 16px">'
        f'<p style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:{FOREST}">'
        f"{escape(venue.name)}</p>"
        f'<div style="background:#ffffff;border:1px solid {LINE};border-radius:8px;padding:24px">'
        f'<h1 style="margin:0 0 16px;font-size:18px;color:{FOREST}">{escape(title)}</h1>'
        f"{intro_html}{blocks_html}{link_html}</div>"
        f'<p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:#5B6E6A">'
        f"{footer_html}</p></div></body></html>"
    )
    return "\n".join(text_parts).strip() + "\n", html


@dataclass(frozen=True)
class StayLine:
    room_type: str
    rate_plan: str
    adults: int
    children: int
    total: Decimal


def booking_confirmation(
    *,
    venue: Venue,
    guest_name: str,
    reference: str,
    provisional: bool,
    check_in: date,
    check_out: date,
    check_in_time: time,
    check_out_time: time,
    rooms: list[StayLine],
    currency: str,
    total: Decimal,
    notes: str | None = None,
    manage_url: str | None = None,
) -> Rendered:
    nights = (check_out - check_in).days
    title = (
        f"Booking request {reference}: not yet confirmed"
        if provisional
        else f"Your booking {reference} is confirmed"
    )
    intro = [f"Dear {guest_name},"]
    intro.append(
        f"Thank you for choosing {venue.name}. We are holding the booking below and will "
        "confirm it shortly."
        if provisional
        else f"Thank you for choosing {venue.name}. Your booking is confirmed."
    )
    stay = Block(
        "Your stay",
        [
            Row("Reference", reference, mono=True),
            Row("Arrival", f"{long_date(check_in)}, from {check_in_time:%H:%M}"),
            Row("Departure", f"{long_date(check_out)}, by {check_out_time:%H:%M}"),
            Row("Nights", str(nights)),
        ],
    )
    room_rows = []
    for r in rooms:
        people = f"{r.adults} adult{'s' if r.adults != 1 else ''}"
        if r.children:
            people += f", {r.children} child{'ren' if r.children != 1 else ''}"
        room_rows.append(Row(f"{r.room_type} · {r.rate_plan} · {people}", money(r.total, currency)))
    room_rows.append(Row("Total, taxes included", money(total, currency), strong=True))
    blocks = [stay, Block("Rooms", room_rows)]
    if notes:
        blocks.append(Block("Notes", [Row("", notes)]))
    outro = Block(
        None,
        [Row("Questions or changes", "Reply to this email or call us.")],
    )
    link = ("View or update your booking", manage_url) if manage_url else None
    text, html = _layout(venue, title, intro, [*blocks, outro], link)
    return Rendered(f"{title} · {venue.name}", text, html)


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    total: Decimal


def invoice(
    *,
    venue: Venue,
    number: str,
    tax_invoice: bool,
    issue_date: date,
    due_date: date | None,
    bill_to: str,
    lines: list[InvoiceLine],
    net: Decimal,
    taxes: list[tuple[str, Decimal, Decimal]],
    total: Decimal,
    credited: Decimal,
    paid: Decimal,
    balance: Decimal,
    currency: str,
    reference: str | None,
) -> Rendered:
    kind = "Tax invoice" if tax_invoice else "Invoice"
    title = f"{kind} {number}"
    head = [Row("Number", number, mono=True), Row("Date", long_date(issue_date))]
    if due_date:
        head.append(Row("Due", long_date(due_date)))
    if reference:
        head.append(Row("Booking", reference, mono=True))
    head.append(Row("Bill to", bill_to))
    amounts = [Row(line.description, money(line.total, currency)) for line in lines]
    summary = [Row("Net", money(net, currency))]
    summary += [
        Row(f"{name} {rate.normalize()}%", money(amount, currency)) for name, rate, amount in taxes
    ]
    summary.append(Row("Total", money(total, currency), strong=True))
    if credited:
        summary.append(Row("Credited", money(-credited, currency)))
    if paid:
        summary.append(Row("Paid", money(-paid, currency)))
    summary.append(Row("Balance due", money(max(balance, Decimal("0.00")), currency), strong=True))
    intro = [f"Dear {bill_to},", f"Please find {kind.lower()} {number} from {venue.name} below."]
    text, html = _layout(
        venue, title, intro, [Block(None, head), Block("Details", amounts), Block(None, summary)]
    )
    return Rendered(f"{title} from {venue.name}", text, html)


def receipt(
    *,
    venue: Venue,
    payer: str,
    amount: Decimal,
    currency: str,
    method: str,
    received_on: date,
    reference: str | None,
    applied_to: list[tuple[str, Decimal]],
    booking_reference: str | None,
) -> Rendered:
    title = f"Receipt: {money(amount, currency)} received"
    rows = [
        Row("Amount", money(amount, currency), strong=True),
        Row("Received", long_date(received_on)),
        Row("Method", method),
    ]
    if reference:
        rows.append(Row("Reference", reference, mono=True))
    if booking_reference:
        rows.append(Row("Booking", booking_reference, mono=True))
    applied = [Row(f"Invoice {number}", money(value, currency)) for number, value in applied_to]
    blocks = [Block(None, rows)]
    if applied:
        blocks.append(Block("Applied to", applied))
    intro = [f"Dear {payer},", f"Thank you. {venue.name} has received your payment."]
    text, html = _layout(venue, title, intro, blocks)
    return Rendered(f"{title} · {venue.name}", text, html)
