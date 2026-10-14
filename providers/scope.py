from datetime import datetime, timezone
from .base_provider import BaseProvider
from schemas.ingestion import IngestionPayload
import requests, json

class ScopeProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "SCOPE"

    url = "https://www.scopecinemas.com/movies/coming-soon"

    payload = [{
        "status": "2",
        "filters": [],
        "page": 0,
        "limit": 0
    }]

    headers = {
        "Accept": "text/x-component",
        "Content-Type": "text/plain;charset=UTF-8",
        "Next-Action": "7fb04f39ec6786cd2c906f62e70dd9ae64cd276463",
        "Origin": "https://www.scopecinemas.com",
        "Referer": "https://www.scopecinemas.com/movies/coming-soon"
    }

    def get_data(self):
        response = requests.post(self.url, headers=self.headers, json=self.payload)
        response.encoding = "utf-8"
        raw_movies = self.parse_response(response)['data']

        movies = [
            {
                "externalId": str(movie["id"]),
                "title": movie["name"].strip(),
                "slug": movie.get("slug"),
                "imageUrl": movie.get("image"),
                "availability": (
                    "AVAILABLE"
                    if movie.get("hasSessions") is True
                    else "UNAVAILABLE"
                    if movie.get("hasSessions") is False
                    else "UNKNOWN"
                ),
            }
            for movie in raw_movies
        ]

        return IngestionPayload(
            provider=self.name,
            observedAt=datetime.now(timezone.utc),
            movies=movies,
        )

    def parse_response(self, response):
        text =  response.text
        json_text = text.split("1:", 1)[1]
        return json.loads(json_text)