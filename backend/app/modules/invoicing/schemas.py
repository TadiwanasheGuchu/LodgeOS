import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Amount = Annotated[Decimal, Field(max_digits=12, decimal_places=2)]


class InvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reservation_id: uuid.UUID | None = None
    # Defaults to the booking's guest when invoicing a booking.
    bill_to_name: str | None = Field(default=None, min_length=2, max_length=200)
    bill_to_details: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)


class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    bill_to_name: str | None = Field(default=None, min_length=2, max_length=200)
    bill_to_details: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    due_date: dt.date | None = None


class ExtraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(min_length=2, max_length=300)
    quantity: Annotated[Decimal, Field(gt=0, le=10_000, max_digits=10, decimal_places=2)]
    unit_amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    prices_include_tax: bool = True
    tax_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    service_date: dt.date | None = None


class CreditLine(BaseModel):
    invoice_item_id: uuid.UUID
    # Gross amount to credit; omit to credit what remains on the line.
    amount: Amount | None = Field(default=None, gt=0)


class CreditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=1000)
    lines: list[CreditLine] = Field(min_length=1, max_length=200)


class TaxLine(BaseModel):
    name: str
    rate_percent: Decimal
    amount: Decimal


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    kind: str
    description: str
    quantity: Decimal
    unit_amount: Decimal
    prices_include_tax: bool
    net_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    taxes: list[TaxLine]
    reservation_room_id: uuid.UUID | None
    service_from: dt.date | None
    service_to: dt.date | None
    credited_amount: Decimal = Decimal("0.00")


class CreditNoteItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_item_id: uuid.UUID
    description: str
    net_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    taxes: list[TaxLine]


class CreditNoteOut(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    number: str
    reason: str
    issue_date: dt.date
    currency: str
    net_total: Decimal
    tax_total: Decimal
    total: Decimal
    issued_by_name: str
    items: list[CreditNoteItemOut]


class Seller(BaseModel):
    name: str
    legal_name: str | None
    tax_number: str | None
    address: list[str]
    phone: str | None
    email: str | None


class InvoiceSummary(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    number: str | None
    status: str
    bill_to_name: str
    reservation_id: uuid.UUID | None
    reservation_reference: str | None
    currency: str
    issue_date: dt.date | None
    due_date: dt.date | None
    total: Decimal
    credited: Decimal
    created_at: dt.datetime


class InvoiceOut(InvoiceSummary):
    bill_to_details: str | None
    notes: str | None
    net_total: Decimal
    tax_total: Decimal
    tax_summary: list[TaxLine]
    issued_by_name: str | None
    seller: Seller
    items: list[ItemOut]
    credit_notes: list[CreditNoteOut]
