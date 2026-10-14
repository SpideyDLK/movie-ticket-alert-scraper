
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class MoviePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    externalId: str = Field(min_length=1)
    title: str = Field(min_length=1)
    slug: str | None = None
    imageUrl: HttpUrl | None = None
    availability: Literal[
        "UNKNOWN", "UNAVAILABLE", "AVAILABLE"
    ] = "UNKNOWN"


class IngestionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["SCOPE", "BMS"]
    observedAt: datetime
    movies: list[MoviePayload]
