from providers.scope import ScopeProvider
import requests, os
from dotenv import load_dotenv
from urllib.parse import urljoin

load_dotenv()

BACK_END_URL = os.getenv("BACK_END_URL")

if not BACK_END_URL:
    raise RuntimeError("BACK_END_URL environment variable is not set")

def main():
    providers = [ScopeProvider()]

    for provider in providers:
        payload = provider.get_data()
        json_payload = payload.model_dump(mode="json")
        ingest(json_payload)

def ingest(payload):
    INGESTION_PATH = "/api/v1/ingestion"
    INGESTION_URL = urljoin(BACK_END_URL.rstrip("/") + "/", INGESTION_PATH.lstrip("/"))
    response = requests.post(
        INGESTION_URL,
        json=payload,
    )
    response.raise_for_status()
    print(f"Ingestion response: {response.status_code} - {response.text}")


if __name__ == "__main__":
    main()
