import csv
import os
import sys
import tempfile
from datetime import date

import html as html_module

from flight_tracker.config import get_config
from flight_tracker.email_report import build_html, build_subject, send_email
from flight_tracker.search import search_flights
from flight_tracker.select import select_picks

_HISTORY_PATH = os.path.join(os.path.dirname(__file__), "history.csv")

_CSV_FIELDS = [
    "schema_version", "date",
    "outbound_fewest_stops_price", "outbound_fewest_stops_airline",
    "outbound_fewest_stops_stops", "outbound_fewest_stops_duration",
    "outbound_cheapest_price", "outbound_cheapest_airline",
    "outbound_cheapest_stops", "outbound_cheapest_duration",
    "return_fewest_stops_price", "return_fewest_stops_airline",
    "return_fewest_stops_stops", "return_fewest_stops_duration",
    "return_cheapest_price", "return_cheapest_airline",
    "return_cheapest_stops", "return_cheapest_duration",
    "outbound_pe_fewest_stops_price", "outbound_pe_fewest_stops_airline",
    "outbound_pe_fewest_stops_stops", "outbound_pe_fewest_stops_duration",
    "outbound_pe_cheapest_price", "outbound_pe_cheapest_airline",
    "outbound_pe_cheapest_stops", "outbound_pe_cheapest_duration",
    "return_pe_fewest_stops_price", "return_pe_fewest_stops_airline",
    "return_pe_fewest_stops_stops", "return_pe_fewest_stops_duration",
    "return_pe_cheapest_price", "return_pe_cheapest_airline",
    "return_pe_cheapest_stops", "return_pe_cheapest_duration",
]


def _pick_val(flight, field):
    if flight is None:
        return ""
    return str(getattr(flight, field))


def _build_row(today: str, outbound_picks: tuple, return_picks: tuple,
               outbound_pe_picks: tuple = (None, None), return_pe_picks: tuple = (None, None)) -> dict:
    ob_fewest, ob_cheapest = outbound_picks
    ret_fewest, ret_cheapest = return_picks
    ob_pe_fewest, ob_pe_cheapest = outbound_pe_picks
    ret_pe_fewest, ret_pe_cheapest = return_pe_picks
    return {
        "schema_version": "2",
        "date": today,
        "outbound_fewest_stops_price": _pick_val(ob_fewest, "price"),
        "outbound_fewest_stops_airline": _pick_val(ob_fewest, "airline"),
        "outbound_fewest_stops_stops": _pick_val(ob_fewest, "stops"),
        "outbound_fewest_stops_duration": _pick_val(ob_fewest, "duration_min"),
        "outbound_cheapest_price": _pick_val(ob_cheapest, "price"),
        "outbound_cheapest_airline": _pick_val(ob_cheapest, "airline"),
        "outbound_cheapest_stops": _pick_val(ob_cheapest, "stops"),
        "outbound_cheapest_duration": _pick_val(ob_cheapest, "duration_min"),
        "return_fewest_stops_price": _pick_val(ret_fewest, "price"),
        "return_fewest_stops_airline": _pick_val(ret_fewest, "airline"),
        "return_fewest_stops_stops": _pick_val(ret_fewest, "stops"),
        "return_fewest_stops_duration": _pick_val(ret_fewest, "duration_min"),
        "return_cheapest_price": _pick_val(ret_cheapest, "price"),
        "return_cheapest_airline": _pick_val(ret_cheapest, "airline"),
        "return_cheapest_stops": _pick_val(ret_cheapest, "stops"),
        "return_cheapest_duration": _pick_val(ret_cheapest, "duration_min"),
        "outbound_pe_fewest_stops_price": _pick_val(ob_pe_fewest, "price"),
        "outbound_pe_fewest_stops_airline": _pick_val(ob_pe_fewest, "airline"),
        "outbound_pe_fewest_stops_stops": _pick_val(ob_pe_fewest, "stops"),
        "outbound_pe_fewest_stops_duration": _pick_val(ob_pe_fewest, "duration_min"),
        "outbound_pe_cheapest_price": _pick_val(ob_pe_cheapest, "price"),
        "outbound_pe_cheapest_airline": _pick_val(ob_pe_cheapest, "airline"),
        "outbound_pe_cheapest_stops": _pick_val(ob_pe_cheapest, "stops"),
        "outbound_pe_cheapest_duration": _pick_val(ob_pe_cheapest, "duration_min"),
        "return_pe_fewest_stops_price": _pick_val(ret_pe_fewest, "price"),
        "return_pe_fewest_stops_airline": _pick_val(ret_pe_fewest, "airline"),
        "return_pe_fewest_stops_stops": _pick_val(ret_pe_fewest, "stops"),
        "return_pe_fewest_stops_duration": _pick_val(ret_pe_fewest, "duration_min"),
        "return_pe_cheapest_price": _pick_val(ret_pe_cheapest, "price"),
        "return_pe_cheapest_airline": _pick_val(ret_pe_cheapest, "airline"),
        "return_pe_cheapest_stops": _pick_val(ret_pe_cheapest, "stops"),
        "return_pe_cheapest_duration": _pick_val(ret_pe_cheapest, "duration_min"),
    }


def _update_history(today: str, outbound_picks: tuple, return_picks: tuple, path: str,
                    outbound_pe_picks: tuple = (None, None), return_pe_picks: tuple = (None, None)) -> None:
    existing = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            existing = [r for r in csv.DictReader(f) if r.get("date") != today]
    new_row = _build_row(today, outbound_picks, return_picks, outbound_pe_picks, return_pe_picks)
    dir_ = os.path.dirname(path) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False, newline="") as tmp:
        tmp_path = tmp.name
        writer = csv.DictWriter(tmp, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing)
        writer.writerow(new_row)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp_path, path)


def _safe_search(origin, destination, flight_date, api_key, travel_class=1):
    try:
        flights = search_flights(origin, destination, flight_date, api_key, travel_class=travel_class)
        return flights, None
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
        _update_history(today, (None, None), (None, None), _HISTORY_PATH)
        # Attempt alert email if SMTP credentials are available (the missing key may not be an SMTP key).
        gmail_user = os.environ.get("GMAIL_USER")
        gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
        alert_email = os.environ.get("ALERT_EMAIL")
        if gmail_user and gmail_pass and alert_email:
            try:
                smtp_cfg = {
                    "gmail_user": gmail_user,
                    "gmail_app_password": gmail_pass,
                    "alert_email": alert_email,
                }
                send_email(
                    f"<p>Missing required environment variable: <b>{html_module.escape(missing_key)}</b></p>",
                    f"[CONFIG ERROR] Flight Tracker: missing {missing_key}",
                    smtp_cfg,
                )
            except Exception:
                pass
        sys.exit(0)

    outbound_flights, outbound_err = _safe_search(
        cfg["origin"], cfg["destination"], cfg["outbound_date"], cfg["serpapi_key"]
    )
    return_flights, return_err = _safe_search(
        cfg["destination"], cfg["origin"], cfg["return_date"], cfg["serpapi_key"]
    )
    outbound_pe_flights, outbound_pe_err = _safe_search(
        cfg["origin"], cfg["destination"], cfg["outbound_date"], cfg["serpapi_key"], travel_class=2
    )
    return_pe_flights, return_pe_err = _safe_search(
        cfg["destination"], cfg["origin"], cfg["return_date"], cfg["serpapi_key"], travel_class=2
    )

    outbound_picks = select_picks(outbound_flights)
    return_picks = select_picks(return_flights)
    outbound_pe_picks = select_picks(outbound_pe_flights)
    return_pe_picks = select_picks(return_pe_flights)

    _update_history(today, outbound_picks, return_picks, _HISTORY_PATH,
                    outbound_pe_picks=outbound_pe_picks, return_pe_picks=return_pe_picks)

    errors = [e for e in (outbound_err, return_err, outbound_pe_err, return_pe_err) if e]
    subject = build_subject(outbound_picks, return_picks, today, cfg["origin"], cfg["destination"])
    if errors:
        subject = f"[ERROR] {subject}"
    html = build_html(outbound_picks, return_picks, today,
                      origin=cfg["origin"], destination=cfg["destination"],
                      outbound_date=cfg["outbound_date"], return_date=cfg["return_date"],
                      outbound_pe_picks=outbound_pe_picks, return_pe_picks=return_pe_picks)
    if errors:
        error_block = "<br>".join(f"<b>Error:</b> {html_module.escape(str(e))}" for e in errors)
        html = f"<p style='color:red'>{error_block}</p>" + html

    try:
        send_email(html, subject, cfg)
    except Exception as exc:
        print(f"SMTP failure: {exc}")  # stdout; exit 0 so commit step still runs
    sys.exit(0)


if __name__ == "__main__":
    main()
