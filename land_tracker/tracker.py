"""Land tracker — orchestrate search, diff against history, email, persist."""
import csv
import html as html_module
import os
import sys
import tempfile
from datetime import date

from land_tracker.config import get_config
from land_tracker.email_report import build_html, build_subject, send_email
from land_tracker.search import search_land
from land_tracker.select import filter_and_score

_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "history.csv")

_CSV_FIELDS = [
    "listing_id", "first_seen", "last_seen",
    "address", "current_price", "min_price_seen",
    "acres", "url", "source",
    "wetland_risk", "road_access", "status",
]


def _load_history(path: str) -> dict:
    """Returns dict of listing_id -> row dict. Only active rows tracked."""
    if not os.path.exists(path):
        return {}
    with open(path, newline="") as f:
        return {r["listing_id"]: r for r in csv.DictReader(f) if r.get("listing_id")}


def _diff(current: list, history: dict) -> tuple:
    """Returns (new_listings, price_drops, gone_ids).

    price_drops is list of (listing, old_price_int).
    """
    current_by_id = {l.listing_id: l for l in current}

    new = [l for l in current if l.listing_id not in history]

    price_drops = []
    for l in current:
        if l.listing_id in history:
            try:
                old = int(history[l.listing_id].get("current_price") or 0)
            except (ValueError, TypeError):
                old = 0
            if old > 0 and l.price < old:
                price_drops.append((l, old))

    gone_ids = [
        lid for lid, row in history.items()
        if row.get("status") == "active" and lid not in current_by_id
    ]

    return new, price_drops, gone_ids


def _update_history(today: str, current: list, history: dict, path: str) -> None:
    current_by_id = {l.listing_id: l for l in current}
    gone_ids = {
        lid for lid, row in history.items()
        if row.get("status") == "active" and lid not in current_by_id
    }

    rows = []

    # Update existing rows
    for lid, row in history.items():
        if lid in current_by_id:
            l = current_by_id[lid]
            old_min = int(row.get("min_price_seen") or l.price)
            row = dict(row)
            row["last_seen"] = today
            row["current_price"] = str(l.price)
            row["min_price_seen"] = str(min(old_min, l.price))
            row["wetland_risk"] = l.wetland_risk
            row["road_access"] = l.road_access
            row["status"] = "active"
        elif lid in gone_ids:
            row = dict(row)
            row["last_seen"] = today
            row["status"] = "gone"
        rows.append(row)

    # Add new listings
    existing_ids = {r["listing_id"] for r in rows}
    for l in current:
        if l.listing_id not in existing_ids:
            rows.append({
                "listing_id": l.listing_id,
                "first_seen": today,
                "last_seen": today,
                "address": l.address,
                "current_price": str(l.price),
                "min_price_seen": str(l.price),
                "acres": str(l.acres),
                "url": l.url,
                "source": l.source,
                "wetland_risk": l.wetland_risk,
                "road_access": l.road_access,
                "status": "active",
            })

    dir_ = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False, newline="") as tmp:
        tmp_path = tmp.name
        writer = csv.DictWriter(tmp, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp_path, path)


def _safe_search(locations: list, api_key: str, provider: str) -> tuple:
    try:
        listings = search_land(locations, api_key, provider=provider)
        return listings, None
    except Exception as exc:
        err_str = str(exc)
        _QUOTA_SIGNALS = ("429", "quota", "credit", "exceeded", "run out", "limit")
        if any(s in err_str.lower() for s in _QUOTA_SIGNALS):
            return [], f"[QUOTA EXCEEDED] {err_str}"
        return [], err_str


def main():
    today = date.today().isoformat()
    try:
        cfg = get_config()
    except KeyError as exc:
        missing_key = str(exc).strip("'")
        print(f"Missing required environment variable: {missing_key}")
        gmail_user = os.environ.get("GMAIL_USER")
        gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
        alert_email = os.environ.get("ALERT_EMAIL")
        if gmail_user and gmail_pass and alert_email:
            try:
                send_email(
                    f"<p>Missing required environment variable: <b>{html_module.escape(missing_key)}</b></p>",
                    f"[CONFIG ERROR] Land Tracker: missing {missing_key}",
                    {"gmail_user": gmail_user, "gmail_app_password": gmail_pass, "alert_email": alert_email},
                )
            except Exception:
                pass
        sys.exit(0)

    raw_listings, search_err = _safe_search(cfg["search_locations"], cfg["serpapi_key"], cfg["provider"])
    current = filter_and_score(raw_listings, cfg["max_price"], cfg["min_acres"])

    history = _load_history(_HISTORY_PATH)
    new_listings, price_drops, gone_ids = _diff(current, history)
    _update_history(today, current, history, _HISTORY_PATH)

    subject = build_subject(len(new_listings), len(price_drops), len(current),
                            cfg["location"], today)
    if search_err:
        subject = f"[ERROR] {subject}"

    html = build_html(new_listings, price_drops, len(gone_ids), current,
                      cfg["location"], today)
    if search_err:
        html = f"<p style='color:red'><b>Search error:</b> {html_module.escape(str(search_err))}</p>" + html

    try:
        send_email(html, subject, cfg)
    except Exception as exc:
        print(f"SMTP failure: {exc}")
    sys.exit(0)


if __name__ == "__main__":
    main()
