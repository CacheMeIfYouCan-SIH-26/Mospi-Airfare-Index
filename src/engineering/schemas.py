from datetime import datetime, date
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, field_validator, model_validator


IATA_PATTERN = r"^[A-Z]{3}$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _validate_iata_code(value: str, field_name: str) -> str:
    if isinstance(value, str) and len(value) == 3 and value.isalpha() and value.isupper():
        return value
    raise ValueError(f"{field_name} must be a 3-letter uppercase IATA airport code")


def _validate_date(value: str, field_name: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format")
    return value


class RawStagingPayload(BaseModel):
    """Audit record ingested from Role 1's interception output (JSONL staging)."""

    scraped_at: datetime
    route_code: str
    origin: str
    destination: str
    advance_window: Optional[str] = None
    departure_date: str
    intercepted_url: Optional[str] = None
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    _validate_origin = field_validator("origin")(_validate_iata_code)
    _validate_destination = field_validator("destination")(_validate_iata_code)
    _validate_departure = field_validator("departure_date")(_validate_date)

    @field_validator("route_code")
    @classmethod
    def _validate_route_code(cls, value: str) -> str:
        if not isinstance(value, str) or "-" not in value:
            raise ValueError("route_code must follow the pattern ORIGIN-DESTINATION")
        return value


class UnbundledFare(BaseModel):
    """Decomposed fare quote unbundled into its constituent components."""

    base_fare: float = Field(ge=0, description="Base ticket fare")
    tax_udf: Optional[float] = Field(default=None, ge=0, description="Tax / user development fee")
    convenience_fee: Optional[float] = Field(default=None, ge=0)
    total_quote: float = Field(ge=0, description="Final quoted total including all charges")


class CleanAirfareRecord(BaseModel):
    """Fully transformed output record emitted downstream for analytics."""

    route_code: str
    origin: str
    destination: str
    departure_date: str
    advance_window: Optional[str] = None
    unbundled: UnbundledFare
    captured_at: Optional[datetime] = None

    _validate_origin = field_validator("origin")(_validate_iata_code)
    _validate_destination = field_validator("destination")(_validate_iata_code)
    _validate_departure = field_validator("departure_date")(_validate_date)

    @field_validator("route_code")
    @classmethod
    def _validate_route_code(cls, value: str) -> str:
        if not isinstance(value, str) or "-" not in value:
            raise ValueError("route_code must follow the pattern ORIGIN-DESTINATION")
        return value

    @model_validator(mode="after")
    def _ensure_total_quote_covers_base_fare(self) -> "CleanAirfareRecord":
        if self.unbundled.total_quote < self.unbundled.base_fare:
            raise ValueError("total_quote must be >= base_fare")
        return self
