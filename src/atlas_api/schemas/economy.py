"""Contract models v1.2 part A (CR-003): country profile (spec 015), economy and currencies (009)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Source

ProfileGroupId = Literal["life", "society", "income", "environment"]


class WorldStats(BaseModel):
    min: float
    median: float
    max: float


class ProfileIndicator(BaseModel):
    id: str
    label: str
    unit: str
    value: float
    year: int
    source_id: str
    rank: int | None
    rank_of: int | None
    world: WorldStats | None
    region_avg: float | None


class ProfileGroup(BaseModel):
    id: ProfileGroupId
    indicators: list[ProfileIndicator]


class Share(BaseModel):
    label: str
    share: float


class CompositionOut(BaseModel):
    religion: list[Share] | None
    ethnicity: list[Share] | None
    year: int | None
    source_id: str | None


class CountryProfile(BaseModel):
    groups: list[ProfileGroup]
    composition: CompositionOut
    sources: list[Source]


class Point(BaseModel):
    year: int
    value: float


class EconomyIndicator(BaseModel):
    id: str
    label: str
    unit: str
    value: float | None
    year: int | None
    source_id: str
    series: list[Point]


class CountryEconomy(BaseModel):
    indicators: list[EconomyIndicator]
    sources: list[Source]


class YearValue(BaseModel):
    value: float
    year: int


class CompareIndicator(BaseModel):
    id: str
    label: str
    unit: str
    values: dict[str, YearValue | None]


class EconomyCompare(BaseModel):
    countries: list[str]
    indicators: list[CompareIndicator]
    sources: list[Source]


class RateItem(BaseModel):
    code: str
    rate: float


class Rates(BaseModel):
    date: str
    base: str
    items: list[RateItem]


class CurrencyStats(BaseModel):
    change_1y: float | None
    change_5y: float | None
    volatility_1y: float | None
    max_drawdown_1y: float | None


class CurrencyDetail(BaseModel):
    code: str
    name: str
    symbol: str | None
    countries: list[str]
    rates: Rates | None
    stats: CurrencyStats | None
    sources: list[Source]


class HistoryItem(BaseModel):
    date: str
    rates: dict[str, float]


class CurrencyHistory(BaseModel):
    base: str
    vs: list[str]
    items: list[HistoryItem]
    source: Source
