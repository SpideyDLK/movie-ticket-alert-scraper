import os
import logging
import time
import requests
from providers.scope import ScopeProvider
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

BACK_END_URL = os.getenv("BACK_END_URL")
BACK_END_API_KEY = os.getenv("BACK_END_API_KEY")

if not BACK_END_URL:
    raise RuntimeError("BACK_END_URL environment variable is not set")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("movie_scraper")

def main():
    started_at = time.monotonic()
    logger.info("Scraper run started")

    ## TODO: implement independent provider failure handling.
    try:
        providers = [ScopeProvider()]

        for provider in providers:
            payload = provider.get_data()
            json_payload = payload.model_dump(mode="json")

            ingest(json_payload)

        duration = time.monotonic() - started_at
        logger.info(
            "Scraper run completed successfully in %.2f seconds",
            duration,
        )
    except Exception:
        logger.exception("Scraper run failed")
        raise

def ingest(payload):
    ingestion_path = "/api/v1/ingestion"
    ingestion_url = urljoin(BACK_END_URL.rstrip("/") + "/", ingestion_path.lstrip("/"))

    logger.info("Sending movie data to ingestion API. URL: %s", ingestion_url)
    response = requests.post(
        ingestion_url,
        headers={"X-API-KEY": BACK_END_API_KEY},
        json=payload,
    )
    response.raise_for_status()
    logger.info("Ingestion response: %s - %s", response.status_code, response.text)


if __name__ == "__main__":
    main()
