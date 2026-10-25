
import json
import logging
from datetime import datetime, timezone

from js import Object, fetch, Request
from pyodide.ffi import to_js

from .base_provider import BaseProvider
from schemas.ingestion import IngestionPayload


class ScopeProvider(BaseProvider):
    logger = logging.getLogger("movie_scraper.scope")

    URL = "https://www.scopecinemas.com/movies/coming-soon"
    API_PATH = "/movies/coming-soon"

    PAYLOAD = [{
        "status": "2",
        "filters": [],
        "page": 0,
        "limit": 0,
    }]

    @property
    def name(self) -> str:
        return "SCOPE"

    @staticmethod
    def _to_js(value):
        return to_js(value, dict_converter=Object.fromEntries)

    async def get_data(self, env) -> IngestionPayload:
        try:
            action_id = await env.SCOPE_NEXT_ACTION.get("last_run")

            if action_id:
                try:
                    raw_movies = await self.fetch_from_scope(action_id)
                except Exception:
                    self.logger.warning(
                        "Scope request failed using the stored Next-Action ID; "
                        "refreshing it and retrying.",
                        exc_info=True,
                    )
                    action_id = await self.refresh_next_action(env)
                    raw_movies = await self.fetch_from_scope(action_id)
            else:
                self.logger.info(
                    "No stored Next-Action ID; obtaining one from Browser Run."
                )
                action_id = await self.refresh_next_action(env)
                raw_movies = await self.fetch_from_scope(action_id)

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

            result = IngestionPayload(
                provider=self.name,
                observedAt=datetime.now(timezone.utc),
                movies=movies,
            )

            self.logger.info("Scope provider completed successfully")
            return result

        except Exception:
            self.logger.exception("Scope provider failed")
            raise

    async def fetch_from_scope(self, action_id: str) -> list:
        self.logger.info("Sending request to Scope Cinemas")

        options = self._to_js({
            "method": "POST",
            "headers": {
                "Accept": "text/x-component",
                "Content-Type": "text/plain;charset=UTF-8",
                "Next-Action": action_id,
                "Origin": "https://www.scopecinemas.com",
                "Referer": self.URL,
            },
            "body": json.dumps(self.PAYLOAD),
        })

        response = await fetch(self.URL, options)
        response_text = await response.text()

        self.logger.info(
            "Scope responded with HTTP %d",
            response.status,
        )

        if not response.ok:
            raise RuntimeError(
                f"Scope returned HTTP {response.status}: "
                f"{response_text[:500]}"
            )

        result = self.parse_response(
            response.status,
            response_text,
            response.headers.get("content-type") or "",
        )

        self.logger.info("Scope response parsed successfully")
        return result["data"]

    async def refresh_next_action(self, env) -> str:
        self.logger.info("Refreshing Next-Action ID through Browser Run")

        helper = env.SCOPE_BROWSER_HELPER
        helper_key = env.BROWSER_HELPER_API_KEY

        if not helper or not helper_key:
            raise RuntimeError(
                "SCOPE_BROWSER_HELPER or BROWSER_HELPER_API_KEY is not configured"
            )

        options = self._to_js({
            "method": "POST",
            "headers": {
                "Authorization": f"Bearer {helper_key}",
            },
        })

        request = Request.new(
            "https://browser-helper.internal/",
            options,
        )

        response = await helper.fetch(request)
        response_text = await response.text()

        if not response.ok:
            raise RuntimeError(
                f"Browser helper returned HTTP {response.status}: "
                f"{response_text[:500]}"
            )

        try:
            result = json.loads(response_text)
            action_id = result.get("nextActionId")
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RuntimeError(
                "Browser helper returned invalid JSON"
            ) from exc

        if not isinstance(action_id, str) or not action_id:
            raise RuntimeError(
                "Browser helper response has no valid nextActionId"
            )

        await env.SCOPE_NEXT_ACTION.put("last_run", action_id)

        self.logger.info("Next-Action ID refreshed and stored in KV")
        return action_id

    def parse_response(
        self,
        status_code: int,
        response_text: str,
        content_type: str,
    ) -> dict:
        for line in response_text.splitlines():
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
            status_code,
            content_type,
        )

        raise ValueError(
            "Scope response did not contain the expected movie-data record"
        )
