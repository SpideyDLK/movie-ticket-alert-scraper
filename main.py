
import json
import logging

from js import Object, fetch
from pyodide.ffi import to_js
from workers import Response, WorkerEntrypoint
import sys

from providers.scope import ScopeProvider

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(levelname)s:%(name)s:%(message)s",
    force=True,
)
logger = logging.getLogger("movie_scraper")


def to_js_options(value):
    return to_js(value, dict_converter=Object.fromEntries)


async def ingest(env, payload: dict) -> None:
    backend_url = env.BACK_END_URL
    backend_api_key = env.BACK_END_API_KEY

    if not backend_url or not backend_api_key:
        raise RuntimeError(
            "BACK_END_URL or BACK_END_API_KEY is not configured"
        )

    ingestion_url = (
        backend_url.rstrip("/") + "/api/v1/ingestion"
    )

    logger.info("Sending movie data to the ingestion API")

    options = to_js_options({
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "X-API-KEY": backend_api_key,
        },
        "body": json.dumps(payload),
    })

    response = await fetch(ingestion_url, options)
    response_text = await response.text()

    if not response.ok:
        raise RuntimeError(
            f"Ingestion API returned HTTP {response.status}: "
            f"{response_text[:1000]}"
        )

    logger.info(
        "Ingestion succeeded: HTTP %d",
        response.status,
    )


async def run_scraper(env) -> None:
    logger.info("Scraper run started")

    # Keep the current provider list; additional providers can be added later.
    providers = [ScopeProvider()]

    for provider in providers:
        payload = await provider.get_data(env)
        json_payload = payload.model_dump(mode="json")
        await ingest(env, json_payload)

    logger.info("Scraper run completed successfully")



import hmac

class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = request.url
        method = request.method

        # Only allow POST /api/v1/run
        if method != "POST" or not url.endswith("/api/v1/run"):
            return Response("Not found", status=404)

        expected_key = self.env.SCRAPER_TRIGGER_API_KEY
        authorization = request.headers.get("Authorization", "")

        if (
            not expected_key
            or not hmac.compare_digest(
                authorization,
                f"Bearer {expected_key}",
            )
        ):
            return Response("Unauthorized", status=401)

        try:
            await run_scraper(self.env)
            return Response(
                '{"success":true,"message":"Scraper completed successfully"}',
                status=200,
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            logger.exception("Manually triggered scraper failed")
            return Response(
                '{"success":false,"message":"Scraper run failed"}',
                status=500,
                headers={"Content-Type": "application/json"},
            )

    async def scheduled(self, controller, env, ctx):
        await run_scraper(self.env)

