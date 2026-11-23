import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import PaymentMethod

Amount = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Key = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    method: PaymentMethod
    amount: Amount
    # Defaults to today in the property's timezone.
    received_on: dt.date | None = None
    payer_name: str | None = Field(default=None, min_length=2, max_length=200)
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=1000)
    reservation_id: uuid.UUID | None = None
    # Allocate straight away, up to what the invoice owes.
    invoice_id: uuid.UUID | None = None
    idempotency_key: Key


class AllocationChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: uuid.UUID
    amount: Amount


class RefundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    amount: Amount
    method: PaymentMethod
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, max_length=100)
    # Release this invoice's overpayment first, in the same transaction.
    release_from_invoice_id: uuid.UUID | None = None
    idempotency_key: Key


class ReverseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=1000)


class AllocationOut(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str | None
    amount: Decimal
    created_at: dt.datetime
    created_by_name: str


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payment_id: uuid.UUID
    method: str
    currency: str
    amount: Decimal
    refunded_on: dt.date
    reason: str
    reference: str | None
    recorded_at: dt.datetime


class PaymentOut(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    reservation_id: uuid.UUID | None
    reservation_reference: str | None
    method: str
    currency: str
    amount: Decimal
    received_on: dt.date
    payer_name: str
    reference: str | None
    note: str | None
    recorded_by_name: str
    recorded_at: dt.datetime
    reversed_at: dt.datetime | None
    reversal_reason: str | None
    allocated: Decimal
    refunded: Decimal
    unallocated: Decimal
    allocations: list[AllocationOut]
    refunds: list[RefundOut]


class InvoicePayments(BaseModel):
    """Money against one invoice."""

    invoice_id: uuid.UUID
    currency: str
    total: Decimal
    credited: Decimal
    paid: Decimal
    balance: Decimal
    payments: list[PaymentOut]


class MethodTotal(BaseModel):
    method: str
    currency: str
    received: Decimal
    refunded: Decimal
    net: Decimal
    count: int


class CashUpDay(BaseModel):
    date: dt.date
    totals: list[MethodTotal]


class CashUp(BaseModel):
    property_id: uuid.UUID
    date_from: dt.date
    date_to: dt.date
    days: list[CashUpDay]
    totals: list[MethodTotal]
    payments: list[PaymentOut]
    refunds: list[RefundOut]
