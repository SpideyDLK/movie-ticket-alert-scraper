from datetime import datetime, timezone
from .base_provider import BaseProvider
from schemas.ingestion import IngestionPayload
import requests, json
import logging
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

    logger = logging.getLogger("movie_scraper.scope")

    def get_data(self):

        try:
            try:
                raw_movies = self.fetch_from_scope()

            except requests.exceptions.RequestException as first_exception:
                self.logger.warning(
                    "Initial Scope request failed (%s). "
                    "Refreshing Next-Action ID before retrying.",
                    first_exception,
                )

                self.get_next_action()

                self.logger.info("Next-Action ID refreshed. Retrying Scope request.")

                # If this fails, the exception propagates and the scraper fails.
                raw_movies = self.fetch_from_scope()

            self.logger.info("Received %d movies from Scope", len(raw_movies))
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

            self.logger.info("Scope provider completed")
            return IngestionPayload(
                provider=self.name,
                observedAt=datetime.now(timezone.utc),
                movies=movies,
            )

        except Exception:
            self.logger.exception("Scope provider failed.")
            raise
    
    def fetch_from_scope(self):
        self.logger.info("Sending request to Scope Cinemas")
        response = requests.post(
            self.URL,
            headers=self.get_headers(),
            json=self.payload,
            timeout=(10, 30),
        )

        self.logger.info(
            "Scope responded with HTTP %d",
            response.status_code
        )

        response.encoding = "utf-8"
        response.raise_for_status()

        result = self.parse_response(response)

        self.logger.info("Scope response parsed successfully")

        return result["data"]

    
    def get_headers(self):
        return {
            "Accept": "text/x-component",
            "Content-Type": "text/plain;charset=UTF-8",
            "Next-Action": get_next_action_id(),
            "Origin": "https://www.scopecinemas.com",
            "Referer": self.URL,
        }
        

    def get_next_action(self):
        self.logger.info("Refreshing Scope Next-Action ID using Playwright")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)

                try:
                    page = browser.new_page()

                    with page.expect_request(
                        lambda request: (
                            request.method == "POST"
                            and self.API_PATH in request.url
                        ),
                        timeout=30_000,
                    ) as request_info:
                        page.goto(self.URL, timeout=30_000)

                    request = request_info.value
                    action_id = request.headers.get("next-action")

                    if not action_id:
                        raise RuntimeError("Next-Action header not found")

                    update_next_action_id(action_id)

                    self.logger.info("Next-Action ID refreshed successfully")

                finally:
                    browser.close()

        except Exception:
            self.logger.exception("Failed to refresh Next-Action ID")
            raise

    def parse_response(self, response):
        for line in response.text.splitlines():
            if not line.startswith("1:"):
                continue

            try:
                payload = json.loads(line[2:])
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "Scope returned invalid movie-data JSON"
                ) from exc

            if not payload.get("success"):
                raise ValueError("Scope reported an unsuccessful request")

            if not isinstance(payload.get("data"), list):
                raise ValueError("Scope response has no valid movie list")

            return payload

        self.logger.error(
            "Unexpected Scope response: status=%d, content_type=%s",
            response.status_code,
            response.headers.get("Content-Type"),
        )

        raise ValueError(
            "Scope response did not contain the expected movie-data record"
        )