"""spec 032 (CR-013 proposal): international organizations and their members, with join/leave dates."""
from pydantic import BaseModel

from atlas_api.schemas.common import Source


class OrganizationMember(BaseModel):
    iso2: str
    joined: str  # ISO 8601 with the source's precision: "YYYY", "YYYY-MM" or "YYYY-MM-DD"
    left: str | None  # null = still a member
    suspended: bool  # still a member, rights suspended
    note: str | None


class Organization(BaseModel):
    id: str  # = glossary term id (kind "membership")
    label: str
    short: str
    icon: str | None
    wikidata_qid: str | None
    note: str | None
    members: list[OrganizationMember]  # every period, current and former, by joined then iso2
    sources: list[Source]


class OrganizationList(BaseModel):
    items: list[Organization]


class CountryMembership(BaseModel):
    id: str
    label: str
    joined: str
    left: str | None
    suspended: bool
    note: str | None


class CountryOrganizations(BaseModel):
    items: list[CountryMembership]  # current first (by label), then former (latest left first)
    sources: list[Source]
