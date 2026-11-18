"""Contract models v1.2 part A (CR-003): country profile (spec 015), economy and currencies (009)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Source

ProfileGroupId = Literal["life", "society", "income", "environment", "economy"]  # economy: CR-009


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


# --- indicator ranking (spec 027, CR-006) --------------------------------------------------------
class RankedIndicator(BaseModel):
    id: str
    label: str
    unit: str
    n: int  # countries with a value
    source_id: str


class IndicatorCatalog(BaseModel):
    items: list[RankedIndicator]


class RankingItem(BaseModel):
    iso2: str
    value: float
    year: int | None
    rank: int  # 1 = highest value (ties share a rank); NOT "best"


class IndicatorRanking(BaseModel):
    id: str
    label: str
    unit: str
    items: list[RankingItem]  # every country with a value, by rank
    sources: list[Source]


class TradeProduct(BaseModel):  # v1.7 proposal (spec 029 phase 2, CR-010)
    hs: str  # HS 4 digits (HS 2022)
    label: str  # pt-BR heading, verbatim from MDIC/Secex NCM_SH (CC BY-ND 3.0: never reworded)
    value_usd: float
    share: float  # of exports_usd, 0..1


class TradePartner(BaseModel):
    iso2: str
    value_usd: float
    share: float  # of exports_usd (destinations) or imports_usd (origins), 0..1


class CountryTradeOut(BaseModel):
    year: int
    exports_usd: float
    imports_usd: float
    top_exports: list[TradeProduct]  # up to 10, by value
    top_destinations: list[TradePartner]  # up to 10, by value
    top_origins: list[TradePartner]  # up to 10, by value
    sources: list[Source]


class TechProduct(BaseModel):  # spec 041, CR-017
    hs: str  # 8542, 8471, 8802, 8803, 8541 or 8517 (HS 2022)
    label: str  # pt-BR heading, verbatim from MDIC/Secex NCM_SH
    flow: Literal["export", "import"]
    value_usd: float
    share: float  # of the country's exports (flow export) or imports (flow import), 0..1
    partners: list[TradePartner]  # up to 5 destinations (export) or origins (import); share is of THIS product flow


class CountryTechOut(BaseModel):
    year: int | None  # null when the country has no BACI data (then products and sources are empty)
    products: list[TechProduct]  # HS in the order above, export before import; only flows with trade
    sources: list[Source]
