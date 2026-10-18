from datetime import datetime, timezone
from .base_provider import BaseProvider
from schemas.ingestion import IngestionPayload
import requests, json
from playwright.sync_api import sync_playwright
from config.scope_config import (
    get_next_action_id,
    update_next_action_id,
)

class ScopeProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "SCOPE"

    URL = "https://www.scopecinemas.com/movies/coming-soon"
    API_PATH = "/movies/coming-soon"

    payload = [{
        "status": "2",
        "filters": [],
        "page": 0,
        "limit": 0
    }]

    def get_data(self):

        try:
            raw_movies = self.fetch_from_scope()

        except requests.exceptions.RequestException as first_error:
            print(f"Scope request failed: {first_error}")
            print("Refreshing Next-Action ID using Playwright...")

            self.get_next_action()

            print("Retrying Scope request...")
            # If this fails, the exception propagates and the scraper fails.
            raw_movies = self.fetch_from_scope()

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
    
    def fetch_from_scope(self):
        response = requests.post(self.URL, headers=self.get_headers(), json=self.payload)
        response.encoding = "utf-8"
        response.raise_for_status()
        return self.parse_response(response)['data']
    
    def get_headers(self):
        return {
            "Accept": "text/x-component",
            "Content-Type": "text/plain;charset=UTF-8",
            "Next-Action": get_next_action_id(),
            "Origin": "https://www.scopecinemas.com",
            "Referer": self.URL,
        }
        

    def get_next_action(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                with page.expect_request(
                    lambda request: (
                        request.method == "POST"
                        and self.API_PATH in request.url
                    ),
                    timeout=30_000,
                ) as request_info:
                    page.goto(self.URL)

                request = request_info.value
                action_id = request.headers.get("next-action")

                if not action_id:
                    raise RuntimeError("Next-Action header not found")

                update_next_action_id(action_id)

            finally:
                browser.close()

    def parse_response(self, response):
        for line in response.text.splitlines():
            if line.startswith("1:"):
                try:
                    payload = json.loads(line[2:])
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "Scope returned an invalid movie-data JSON record"
                    ) from exc

                if not payload.get("success"):
                    raise ValueError("Scope reported an unsuccessful request")

                if not isinstance(payload.get("data"), list):
                    raise ValueError("Scope response has no valid movie list")

                return payload

        raise ValueError(
            f"Scope response did not contain the expected movie-data record. "
            f"Status: {response.status_code}, "
            f"Content-Type: {response.headers.get('Content-Type')}"
        )