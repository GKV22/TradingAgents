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
        "min_acres": float(os.environ.get("LAND_MIN_ACRES", "5")),
        "provider": os.environ.get("LAND_SEARCH_PROVIDER", "serpapi"),
        # Comma-separated ZIPs/towns — one SerpAPI call each.
        # Default: key ZIPs within ~60mi of 29588 (Myrtle Beach area).
        "search_locations": [
            loc.strip()
            for loc in os.environ.get(
                "LAND_SEARCH_LOCATIONS",
                "29588,29526,29554,29440,29556,29569",
            ).split(",")
            if loc.strip()
        ],
    }
    return cfg
