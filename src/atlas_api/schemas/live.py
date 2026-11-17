"""spec 034 (CR-015 proposal): "acontecendo agora", recent earthquakes (USGS) and natural events (NASA EONET)."""
from typing import Literal

from pydantic import BaseModel

from atlas_api.schemas.common import Source

LiveEventType = Literal["earthquake", "wildfire", "severe_storm", "volcano", "flood", "landslide", "dust_haze",
                        "temp_extreme", "drought", "snow"]


class LiveEventOut(BaseModel):
    id: str  # "usgs:<id>" | "eonet:<id>"
    type: LiveEventType
    lat: float
    lng: float
    magnitude: float | None  # earthquake: magnitude; EONET: its own measure (see magnitude_unit)
    magnitude_unit: str | None  # USGS magType ("mww", "mb"...) or EONET unit ("kts", "acres"...)
    title: str  # verbatim from the source (English)
    url: str | None  # the event page at the source
    time: str  # ISO 8601 UTC; EONET: date of its latest position
    source: Literal["usgs", "eonet"]


class LiveEventList(BaseModel):
    items: list[LiveEventOut]  # newest first
    fetched_at: str | None  # last successful job run
    sources: list[Source]
