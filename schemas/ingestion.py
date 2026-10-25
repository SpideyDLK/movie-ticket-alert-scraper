from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal


@dataclass
class MoviePayload:
    externalId: str
    title: str
    slug: str | None = None
    imageUrl: str | None = None
    availability: Literal[
        "UNKNOWN", "UNAVAILABLE", "AVAILABLE"
    ] = "UNKNOWN"


@dataclass
class IngestionPayload:
    provider: Literal["SCOPE", "BMS"]
    observedAt: datetime
    movies: list[MoviePayload]

    def model_dump(self, mode: str = "python") -> dict:
        result = asdict(self)
        if mode == "json":
            result["observedAt"] = self.observedAt.isoformat()
        return result