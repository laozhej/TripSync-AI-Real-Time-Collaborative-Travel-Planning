"""Validation for authored JSON destination bundles (not an upload endpoint)."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Coordinates(Strict):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class Interval(Strict):
    days: list[int] = Field(min_length=1, max_length=7)
    open: time
    close: time
    closeDayOffset: Literal[0, 1]

    @model_validator(mode="after")
    def validate_interval(self):
        if len(set(self.days)) != len(self.days) or any(day < 1 or day > 7 for day in self.days):
            raise ValueError("days must be unique ISO weekdays")
        start = timedelta(hours=self.open.hour, minutes=self.open.minute, seconds=self.open.second)
        end = timedelta(days=self.closeDayOffset, hours=self.close.hour, minutes=self.close.minute, seconds=self.close.second)
        if not timedelta(0) < end - start <= timedelta(days=1):
            raise ValueError("invalid opening interval")
        return self


class Hours(Strict):
    weekly: list[Interval]
    exceptions: list[dict] = Field(default_factory=list, max_length=0)

    @model_validator(mode="after")
    def no_overlapping_intervals(self):
        week = 7 * 24 * 60
        spans = []
        for interval in self.weekly:
            if interval.open.second or interval.close.second or interval.open.microsecond or interval.close.microsecond:
                raise ValueError("hours must use minute precision")
            start_minute = interval.open.hour * 60 + interval.open.minute
            end_minute = interval.close.hour * 60 + interval.close.minute + 1440 * interval.closeDayOffset
            for day in interval.days:
                start = (day - 1) * 1440 + start_minute
                end = (day - 1) * 1440 + end_minute
                spans.append((start, min(end, week)))
                if end > week:
                    spans.append((0, end - week))
        spans.sort()
        if any(right[0] < left[1] for left, right in zip(spans, spans[1:])):
            raise ValueError("overlapping weekly opening intervals")
        return self


class Venue(Strict):
    sourceId: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    category: Literal["food", "lodging", "activity", "transit"]
    pricePerPerson: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    dietaryTags: list[Literal["vegetarian", "vegan", "halal", "gluten-free"]]
    coordinates: Coordinates
    rating: float | None = Field(default=None, ge=0, le=5)
    hours: Hours
    description: str = Field(min_length=1, max_length=20000)

    @field_validator("pricePerPerson", mode="before")
    @classmethod
    def exact_price(cls, value):
        if not isinstance(value, str):
            raise ValueError("price must be a decimal string")
        return value

    @model_validator(mode="after")
    def unique_tags(self):
        if len(set(self.dietaryTags)) != len(self.dietaryTags):
            raise ValueError("duplicate dietary tag")
        return self


class Provenance(Strict):
    kind: Literal["synthetic"]
    author: str = Field(min_length=1, max_length=200)
    authoredAt: date
    license: str = Field(min_length=1, max_length=200)
    notice: str = Field(min_length=1, max_length=500)


class Transit(Strict):
    sourceId: str = Field(min_length=1, max_length=80)
    fromVenueId: str
    toVenueId: str
    mode: str = Field(min_length=1, max_length=40)
    durationMinutes: int = Field(gt=0)
    validFrom: datetime
    validTo: datetime
    synthetic: Literal[True]

    @model_validator(mode="after")
    def dates(self):
        if self.validFrom.utcoffset() is None or self.validTo.utcoffset() is None or self.validTo <= self.validFrom:
            raise ValueError("transit validity requires ordered offset-aware times")
        return self


class Weather(Strict):
    sourceId: str = Field(min_length=1, max_length=80)
    date: date
    summary: str = Field(min_length=1, max_length=500)
    temperatureC: float
    synthetic: Literal[True]


class Dataset(Strict):
    schemaVersion: Literal[1]
    destination: str = Field(min_length=1, max_length=200)
    timezone: str
    currency: Literal["INR", "EUR"]
    provenance: Provenance
    venues: list[Venue] = Field(min_length=1, max_length=2000)
    transit: list[Transit] = Field(max_length=2000)
    weather: list[Weather] = Field(max_length=2000)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("invalid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def links(self):
        ids = [v.sourceId for v in self.venues]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate venue sourceId")
        if any(t.fromVenueId not in ids or t.toVenueId not in ids for t in self.transit):
            raise ValueError("dangling transit reference")
        for entries in (self.transit, self.weather):
            if len({entry.sourceId for entry in entries}) != len(entries):
                raise ValueError("duplicate sourceId")
        if len({entry.date for entry in self.weather}) != len(self.weather):
            raise ValueError("duplicate weather date")
        return self
