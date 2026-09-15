"""
MLS data quality — response schemas.

Ordered the way the dashboard reads: is anything wrong, how big is the gap,
where is it, what is wrong, and finally which listings.
"""

from datetime import datetime

from pydantic import BaseModel, Field


# -- Status --------------------------------------------------------------------


class DQStatusResponse(BaseModel):
    """One glance: is the data in step with the MLS, and is this page current."""

    has_gap: bool = Field(
        description="True when the totals differ or any check is failing."
    )
    gap: int | None = Field(
        default=None,
        description="Homes at the MLS minus homes held here.",
    )
    checks_failing: int
    checks_run: int

    last_checked: datetime | None = Field(
        default=None, description="When the checks last ran (UTC)."
    )
    hours_since_check: float | None = None
    ran_today: bool = Field(
        description="Whether the checks have run in the last 26 hours."
    )
    data_age_days: float | None = Field(
        default=None,
        description=(
            "How old the newest listing record is. Separate from ran_today: "
            "the checks running and the data being fresh are different things."
        ),
    )


# -- Source against target -----------------------------------------------------


class SourceTargetResponse(BaseModel):
    """The MLS figure comes from live calls to the feed, ours from this
    database, so the difference is a genuine source-to-target gap."""

    mls_has: int | None = None
    we_have: int | None = None
    difference: int | None = None
    checked_at: datetime | None = None


# -- Status breakdown ----------------------------------------------------------


class StatusRow(BaseModel):
    status: str
    mls_has: int | None = None
    we_have: int | None = None
    difference: int | None = None
    error: str | None = Field(
        default=None,
        description="Set when the feed returned an incomplete list for this status.",
    )


class StatusBreakdownResponse(BaseModel):
    checked_at: datetime | None = None
    total: int
    items: list[StatusRow]


# -- Checks --------------------------------------------------------------------


class DQCheck(BaseModel):
    check_name: str
    label: str
    severity_level: str | None = None
    fix_window: str | None = None
    value: float
    threshold: float | None = None
    passed: bool
    listings_recorded: int = Field(
        description="How many listing keys this check recorded for drill-down."
    )
    value_a_week_ago: float | None = None
    direction: str = Field(
        description="rising, falling, flat, or 'no history yet'."
    )


class DQChecksResponse(BaseModel):
    checked_at: datetime | None = None
    total: int
    failing: int
    items: list[DQCheck]


# -- Listings behind a check ---------------------------------------------------


class AffectedListing(BaseModel):
    listing_key: str | None = None
    listing_id: str | None = None
    address: str | None = None
    zip: str | None = None
    our_status: str | None = None
    mls_status: str | None = None
    our_price: str | None = None
    mls_close_price: str | None = None
    mls_close_date: str | None = None


class CheckListingsResponse(BaseModel):
    check_name: str
    label: str | None = None
    total: int
    items: list[AffectedListing]