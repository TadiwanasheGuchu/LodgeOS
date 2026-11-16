import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.properties.models import RecordStatus
from app.modules.rates.models import MealPlan, RatePlanKind

# Money arrives and leaves as a decimal string with at most 2 decimals; never a float.
Amount = Annotated[Decimal, Field(ge=0, le=Decimal("9999999999.99"), decimal_places=2)]
Percent = Annotated[Decimal, Field(gt=0, lt=100, decimal_places=4)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaxCreate(_In):
    name: str = Field(min_length=2, max_length=100)
    rate_percent: Percent
    sort_order: int = Field(default=0, ge=0, le=10_000)


class TaxUpdate(_In):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    rate_percent: Percent | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    status: RecordStatus | None = None


class TaxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    rate_percent: Decimal
    sort_order: int
    status: str


class _PlanFields(_In):
    description: str | None = Field(default=None, max_length=2000)
    stay_from: date | None = None
    stay_to: date | None = None
    max_stay_nights: int | None = Field(default=None, ge=1, le=365)

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.stay_from and self.stay_to and self.stay_to < self.stay_from:
            raise ValueError("The last night must be on or after the first night.")
        return self


class RatePlanCreate(_PlanFields):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{0,15}$")
    kind: RatePlanKind = RatePlanKind.STANDARD
    meal_plan: MealPlan = MealPlan.ROOM_ONLY
    prices_include_tax: bool = True
    min_stay_nights: int = Field(default=1, ge=1, le=365)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class RatePlanUpdate(_PlanFields):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    code: str | None = Field(default=None, pattern=r"^[A-Z0-9][A-Z0-9-]{0,15}$")
    kind: RatePlanKind | None = None
    meal_plan: MealPlan | None = None
    prices_include_tax: bool | None = None
    min_stay_nights: int | None = Field(default=None, ge=1, le=365)
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    status: RecordStatus | None = None


class PriceFields(_In):
    base_price: Amount
    weekend_price: Amount | None = None
    extra_adult_price: Amount = Decimal("0.00")
    extra_child_price: Amount = Decimal("0.00")


class PriceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    room_type_id: uuid.UUID
    base_price: Decimal
    weekend_price: Decimal | None
    extra_adult_price: Decimal
    extra_child_price: Decimal


class SeasonCreate(PriceFields):
    room_type_id: uuid.UUID
    name: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("The last night must be on or after the first night.")
        return self


class SeasonUpdate(_In):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    base_price: Amount | None = None
    weekend_price: Amount | None = None
    extra_adult_price: Amount | None = None
    extra_child_price: Amount | None = None


class SeasonOut(PriceOut):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date


class RatePlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    code: str
    description: str | None
    kind: str
    meal_plan: str
    currency: str
    prices_include_tax: bool
    min_stay_nights: int
    max_stay_nights: int | None
    stay_from: date | None
    stay_to: date | None
    sort_order: int
    status: str


class RatePlanDetail(RatePlanOut):
    prices: list[PriceOut]
    seasons: list[SeasonOut]


class QuoteRequest(_In):
    rate_plan_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in: date
    check_out: date
    adults: int = Field(ge=1, le=50)
    children: int = Field(default=0, ge=0, le=50)


class NightOut(BaseModel):
    date: date
    season: str | None
    weekend: bool
    room_price: Decimal
    extra_adults: int
    extra_adult_amount: Decimal
    extra_children: int
    extra_child_amount: Decimal
    amount: Decimal


class TaxAmountOut(BaseModel):
    name: str
    rate_percent: Decimal
    amount: Decimal


class QuoteOut(BaseModel):
    currency: str
    prices_include_tax: bool
    rate_plan_id: uuid.UUID
    rate_plan_name: str
    room_type_id: uuid.UUID
    room_type_name: str
    nights: list[NightOut]
    accommodation_total: Decimal
    net_total: Decimal
    taxes: list[TaxAmountOut]
    tax_total: Decimal
    total: Decimal
