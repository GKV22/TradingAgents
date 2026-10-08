"""Save each analysis as a PDF named "TradingAgents — <TICKER> <YYYY-MM-DD>.pdf".

The folder is TRADINGAGENTS_REPORTS_DIR (set it in .env), else ~/.tradingagents/reports.
The PDF is printed from HTML by headless Microsoft Edge; without Edge the .html is saved.
A partial report is still saved if a run fails or is stopped, marked "Incomplete".
"""

from __future__ import annotations

import html
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from markdown_it import MarkdownIt

DEFAULT_REPORTS_DIR = Path.home() / ".tradingagents" / "reports"
_EDGE_PATHS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)
_md = MarkdownIt("commonmark", {"html": False}).enable("table")

_CSS = """
body { font-family: Segoe UI, Arial, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem;
       color: #1f2937; line-height: 1.55; }
h1 { margin-bottom: .25rem; } .meta { color: #6b7280; margin-top: 0; }
.status { display: inline-block; padding: .1rem .5rem; border-radius: 4px; font-weight: 600; }
.complete { background: #dcfce7; color: #166534; } .incomplete { background: #fee2e2; color: #991b1b; }
section { border-top: 1px solid #e5e7eb; margin-top: 2rem; padding-top: .5rem; }
table { border-collapse: collapse; margin: 1rem 0; } th, td { border: 1px solid #d1d5db; padding: .3rem .6rem; }
th { background: #f3f4f6; } code { background: #f3f4f6; padding: 0 .2rem; border-radius: 3px; }
@media print { section { break-inside: auto; } }
"""


def reports_dir() -> Path:
    return Path(os.getenv("TRADINGAGENTS_REPORTS_DIR") or DEFAULT_REPORTS_DIR)


def _unique(path: Path) -> Path:
    """Don't overwrite an earlier run of the same ticker and date: add (2), (3), ..."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def save_report(
    ticker: str,
    date: str,
    sections: list[tuple[str, str]],
    decision: str | None,
    duration_s: float,
) -> Path:
    """Write sections (title, markdown) to a PDF (or HTML fallback) and return its path."""
    title = f"TradingAgents — {ticker} {date}"
    complete = decision is not None
    status = (
        f'<span class="status complete">Complete — decision: {html.escape(str(decision))}</span>'
        if complete
        else '<span class="status incomplete">Incomplete — the run stopped before the final decision</span>'
    )
    minutes, seconds = divmod(int(duration_s), 60)
    body = "\n".join(
        f"<section><h2>{html.escape(t)}</h2>\n{_md.render(c or '')}</section>" for t, c in sections
    )
    page = (
        f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(title)}</title><style>{_CSS}</style></head><body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f"<p class=\"meta\">Generated {datetime.now():%Y-%m-%d %H:%M} · Duration {minutes}:{seconds:02d}</p>\n"
        f"<p>{status}</p>\n{body}\n</body></html>\n"
    )
    folder = reports_dir()
    folder.mkdir(parents=True, exist_ok=True)
    pdf_path = _unique(folder / f"{title}.pdf")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "report.html"
        src.write_text(page, encoding="utf-8")
        if _html_to_pdf(src, pdf_path):
            return pdf_path
    # No PDF (Edge missing or failed): keep the HTML so the report isn't lost
    html_path = _unique(folder / f"{title}.html")
    html_path.write_text(page, encoding="utf-8")
    return html_path


def _html_to_pdf(src: Path, dest: Path) -> bool:
    """Print src to dest with headless Microsoft Edge (built into Windows)."""
    edge = next((p for p in _EDGE_PATHS if Path(p).exists()), None)
    if not edge:
        return False
    try:
        subprocess.run(
            [edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
             f"--user-data-dir={src.parent / 'edge-profile'}",  # don't hand off to an open Edge
             f"--print-to-pdf={dest}", src.as_uri()],
            capture_output=True, timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return dest.exists() and dest.stat().st_size > 0
