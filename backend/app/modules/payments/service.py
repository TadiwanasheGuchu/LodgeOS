"""Payment rules (ADR-0010). Callers hold the transaction.

Lock order is always payment, then invoice, so concurrent allocations cannot deadlock or
over-allocate.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.invoicing.models import Invoice, InvoiceStatus
from app.modules.invoicing.service import credited_total
from app.modules.payments.models import Payment, PaymentAllocation, Refund

ZERO = Decimal("0.00")


class PaymentError(ValueError):
    """A rule was broken; the message is shown to staff."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class PaymentState:
    allocated: Decimal
    refunded: Decimal

    def unallocated(self, payment: Payment) -> Decimal:
        if payment.reversed_at is not None:
            return ZERO
        return payment.amount - self.allocated - self.refunded


async def state(db: AsyncSession, payment_id: uuid.UUID) -> PaymentState:
    allocated = await db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), ZERO)).where(
            PaymentAllocation.payment_id == payment_id
        )
    )
    refunded = await db.scalar(
        select(func.coalesce(func.sum(Refund.amount), ZERO)).where(Refund.payment_id == payment_id)
    )
    return PaymentState(allocated or ZERO, refunded or ZERO)


async def paid_total(db: AsyncSession, invoice_id: uuid.UUID) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), ZERO)).where(
            PaymentAllocation.invoice_id == invoice_id
        )
    )
    return value or ZERO


async def balance(db: AsyncSession, invoice: Invoice) -> Decimal:
    """What the invoice still owes; negative when it has been overpaid."""
    if invoice.status != InvoiceStatus.ISSUED:
        return ZERO
    return invoice.total - await credited_total(db, invoice.id) - await paid_total(db, invoice.id)


async def _pair_total(db: AsyncSession, payment_id: uuid.UUID, invoice_id: uuid.UUID) -> Decimal:
    value = await db.scalar(
        select(func.coalesce(func.sum(PaymentAllocation.amount), ZERO)).where(
            PaymentAllocation.payment_id == payment_id, PaymentAllocation.invoice_id == invoice_id
        )
    )
    return value or ZERO


async def _lock_payment(db: AsyncSession, payment: Payment) -> None:
    await db.execute(select(Payment.id).where(Payment.id == payment.id).with_for_update())
    await db.refresh(payment)


async def _lock_invoice(db: AsyncSession, invoice: Invoice) -> None:
    await db.execute(select(Invoice.id).where(Invoice.id == invoice.id).with_for_update())


async def record(db: AsyncSession, values: dict[str, object]) -> tuple[Payment, bool]:
    """Insert a payment, or return the one already recorded under the same idempotency key.
    The boolean is True when this call created it."""
    now = datetime.now(UTC)
    new_id = await db.scalar(
        insert(Payment)
        .values(id=uuid.uuid4(), recorded_at=now, **values)
        .on_conflict_do_nothing(constraint="uq_payments_idempotency")
        .returning(Payment.id)
    )
    created = new_id is not None
    payment = await db.scalar(
        select(Payment).where(
            Payment.organisation_id == values["organisation_id"],
            Payment.idempotency_key == values["idempotency_key"],
        )
    )
    assert payment is not None
    if not created and (
        payment.amount != values["amount"] or payment.property_id != values["property_id"]
    ):
        raise PaymentError("This payment was already recorded with different details.")
    return payment, created


async def allocate(
    db: AsyncSession, payment: Payment, invoice: Invoice, amount: Decimal, *, user_id: uuid.UUID
) -> PaymentAllocation:
    await _lock_payment(db, payment)
    await _lock_invoice(db, invoice)
    if payment.reversed_at is not None:
        raise PaymentError("This payment was reversed.")
    if invoice.status != InvoiceStatus.ISSUED:
        raise PaymentError("Payments can only be set against issued invoices.")
    if invoice.property_id != payment.property_id:
        raise PaymentError("The invoice belongs to another property.", 422)
    if invoice.currency != payment.currency:
        raise PaymentError("The payment and the invoice are in different currencies.", 422)
    if amount <= ZERO:
        raise PaymentError("Enter an amount above zero.", 422)
    free = (await state(db, payment.id)).unallocated(payment)
    owed = await balance(db, invoice)
    if amount > free:
        raise PaymentError(f"Only {free} of this payment is not yet allocated.")
    if amount > owed:
        raise PaymentError(f"The invoice only owes {max(owed, ZERO)}.")
    row = PaymentAllocation(
        organisation_id=payment.organisation_id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        amount=amount,
        created_by=user_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def release(
    db: AsyncSession, payment: Payment, invoice: Invoice, amount: Decimal, *, user_id: uuid.UUID
) -> PaymentAllocation:
    await _lock_payment(db, payment)
    await _lock_invoice(db, invoice)
    current = await _pair_total(db, payment.id, invoice.id)
    if amount <= ZERO or amount > current:
        raise PaymentError(f"Release between 0.01 and {current}.", 422)
    row = PaymentAllocation(
        organisation_id=payment.organisation_id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        amount=-amount,
        created_by=user_id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row


async def refund(
    db: AsyncSession,
    payment: Payment,
    *,
    amount: Decimal,
    method: str,
    reason: str,
    reference: str | None,
    refunded_on: date,
    idempotency_key: str,
    user_id: uuid.UUID,
) -> tuple[Refund, bool]:
    await _lock_payment(db, payment)
    existing = await db.scalar(
        select(Refund).where(
            Refund.organisation_id == payment.organisation_id,
            Refund.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.payment_id != payment.id or existing.amount != amount:
            raise PaymentError("This refund was already recorded with different details.")
        return existing, False
    if payment.reversed_at is not None:
        raise PaymentError("This payment was reversed.")
    free = (await state(db, payment.id)).unallocated(payment)
    if amount <= ZERO:
        raise PaymentError("Enter an amount above zero.", 422)
    if amount > free:
        raise PaymentError(
            f"Only {free} of this payment is free to refund. Release it from invoices first."
        )
    row = Refund(
        organisation_id=payment.organisation_id,
        property_id=payment.property_id,
        payment_id=payment.id,
        method=method,
        currency=payment.currency,
        amount=amount,
        refunded_on=refunded_on,
        reason=reason,
        reference=reference,
        idempotency_key=idempotency_key,
        recorded_by=user_id,
        recorded_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return row, True


async def reverse(db: AsyncSession, payment: Payment, *, reason: str, user_id: uuid.UUID) -> int:
    """Undo a payment recorded in error. Returns how many invoices were released."""
    await _lock_payment(db, payment)
    if payment.reversed_at is not None:
        raise PaymentError("This payment is already reversed.")
    st = await state(db, payment.id)
    if st.refunded > ZERO:
        raise PaymentError("A payment with refunds cannot be reversed.")
    pairs = (
        await db.execute(
            select(PaymentAllocation.invoice_id, func.sum(PaymentAllocation.amount))
            .where(PaymentAllocation.payment_id == payment.id)
            .group_by(PaymentAllocation.invoice_id)
            .order_by(PaymentAllocation.invoice_id)
        )
    ).all()
    now = datetime.now(UTC)
    released = 0
    for invoice_id, net in pairs:
        if net > ZERO:
            await db.execute(select(Invoice.id).where(Invoice.id == invoice_id).with_for_update())
            db.add(
                PaymentAllocation(
                    organisation_id=payment.organisation_id,
                    payment_id=payment.id,
                    invoice_id=invoice_id,
                    amount=-net,
                    created_by=user_id,
                    created_at=now,
                )
            )
            released += 1
    payment.reversed_at = now
    payment.reversed_by = user_id
    payment.reversal_reason = reason
    await db.flush()
    return released
