"""Land tracker configuration from environment variables."""
import os


def get_config() -> dict:
    cfg = {
        "serpapi_key": os.environ["SERPAPI_KEY"],
        "gmail_user": os.environ["GMAIL_USER"],
        "gmail_app_password": os.environ["GMAIL_APP_PASSWORD"],
        "alert_email": os.environ["ALERT_EMAIL"],
        "location": os.environ.get("LAND_LOCATION", "29588"),
        "radius_miles": int(os.environ.get("LAND_RADIUS_MILES", "60")),
        "max_price": int(os.environ.get("LAND_MAX_PRICE", "250000")),
        "min_acres": float(os.environ.get("LAND_MIN_ACRES", "10")),
        "provider": os.environ.get("LAND_SEARCH_PROVIDER", "serpapi"),
    }
    return cfg
