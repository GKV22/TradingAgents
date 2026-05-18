"""Land tracker email — HTML report builder and SMTP sender."""
import html as html_module
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote_plus


_RISK_COLORS = {"HIGH": "#ffcccc", "MEDIUM": "#fff3cc", "UNKNOWN": "#ffffff"}
_ROAD_ICONS = {"YES": "✅", "NO": "🚫", "UNKNOWN": "❓"}


def _fmt_price(price: int) -> str:
    return f"${price:,}"


def _fmt_acres(acres: float) -> str:
    return f"{acres:g} acres"


def _listing_row(listing) -> str:
    bg = _RISK_COLORS.get(listing.wetland_risk, "#ffffff")
    road_icon = _ROAD_ICONS.get(listing.road_access, "❓")
    price = html_module.escape(_fmt_price(listing.price))
    acres = html_module.escape(_fmt_acres(listing.acres))
    address = html_module.escape(listing.address or "—")
    wetland = html_module.escape(listing.wetland_risk)
    url = html_module.escape(listing.url or "")
    desc = html_module.escape((listing.description or "")[:200])
    link = f'<a href="{url}">{address}</a>' if url else address
    return (
        f'<tr style="background:{bg}">'
        f"<td>{link}</td>"
        f"<td>{price}</td>"
        f"<td>{acres}</td>"
        f"<td>{wetland}</td>"
        f"<td>{road_icon} {html_module.escape(listing.road_access)}</td>"
        f"<td><small>{desc}{'…' if len(listing.description or '') > 200 else ''}</small></td>"
        f"</tr>"
    )


def _table(listings: list) -> str:
    if not listings:
        return "<p><em>None</em></p>"
    rows = "\n".join(_listing_row(l) for l in listings)
    return f"""<table border="1" cellpadding="6" cellspacing="0">
  <tr>
    <th>Address</th><th>Price</th><th>Acres</th>
    <th>Wetland Risk</th><th>Road Access</th><th>Description</th>
  </tr>
  {rows}
</table>"""


def build_html(new_listings: list, price_drops: list, gone_count: int,
               all_active: list, location: str, today: str) -> str:
    search_url = html_module.escape(
        f"https://www.google.com/search?q={quote_plus('land for sale ' + location + ' SC acres farmland')}"
    )

    drops_html = ""
    if price_drops:
        drop_rows = []
        for listing, old_price in price_drops:
            bg = _RISK_COLORS.get(listing.wetland_risk, "#ffffff")
            saving = old_price - listing.price
            address = html_module.escape(listing.address or "—")
            url = html_module.escape(listing.url or "")
            link = f'<a href="{url}">{address}</a>' if url else address
            drop_rows.append(
                f'<tr style="background:{bg}">'
                f"<td>{link}</td>"
                f"<td>{html_module.escape(_fmt_price(listing.price))}</td>"
                f"<td><s>{html_module.escape(_fmt_price(old_price))}</s></td>"
                f"<td>-{html_module.escape(_fmt_price(saving))}</td>"
                f"<td>{html_module.escape(_fmt_acres(listing.acres))}</td>"
                f"</tr>"
            )
        drops_html = f"""
<h2>💰 Price Drops ({len(price_drops)})</h2>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><th>Address</th><th>New Price</th><th>Old Price</th><th>Saving</th><th>Acres</th></tr>
  {''.join(drop_rows)}
</table>"""

    gone_html = f"<p><small>{gone_count} listing(s) removed since last run (sold/withdrawn).</small></p>" if gone_count else ""

    return f"""<html><body>
<h1>🌾 Land Tracker — {html_module.escape(location)} area — {html_module.escape(today)}</h1>
<p>Criteria: ≥10 acres · ≤$250,000 · within 60 miles of {html_module.escape(location)}</p>
<p><small>Wetland risk: <span style="background:#ffcccc">HIGH</span> &nbsp;
<span style="background:#fff3cc">MEDIUM</span> &nbsp; UNKNOWN = not mentioned in listing</small></p>

<h2>🆕 New Listings ({len(new_listings)})</h2>
{_table(new_listings)}

{drops_html}

{gone_html}

<h2>All Active Matches ({len(all_active)})</h2>
{_table(all_active)}

<p><a href="{search_url}">Search Google for more listings</a></p>
<p><small>Searched via SerpAPI · History tracked in land_tracker/history.csv</small></p>
</body></html>"""


def build_subject(new_count: int, drop_count: int, active_count: int,
                  location: str, today: str) -> str:
    parts = []
    if new_count:
        parts.append(f"{new_count} new")
    if drop_count:
        parts.append(f"{drop_count} price drops")
    summary = ", ".join(parts) if parts else "no changes"
    return f"🌾 Land {location} | {summary} | {active_count} active | {today}"


def send_email(html: str, subject: str, config: dict) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["gmail_user"]
    msg["To"] = config["alert_email"]
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(config["gmail_user"], config["gmail_app_password"])
        server.sendmail(config["gmail_user"], config["alert_email"], msg.as_string())
