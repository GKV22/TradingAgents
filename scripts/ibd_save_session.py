"""First-time IBD session setup: open browser for manual login.

Uses a nodriver persistent profile directory (ibd-profile/) so cookies
survive across runs automatically. After one successful manual login,
the automated digest runs will reuse the saved session indefinitely.

Run once. Re-run only when the session expires (~30-90 days).
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

IBD_PROFILE_DIR = ROOT / "ibd-profile"
LOGIN_URL = "https://myibd.investors.com/secure/signin.aspx"
WAIT_MINUTES = 10


async def _save_session_async() -> None:
    import nodriver as uc

    IBD_PROFILE_DIR.mkdir(exist_ok=True)

    print("Opening browser — please log in to investors.com manually.")
    print(f"Browser closes automatically when done. (timeout: {WAIT_MINUTES} min)")

    browser = await uc.start(
        user_data_dir=str(IBD_PROFILE_DIR),
        headless=False,
    )
    tab = await browser.get(LOGIN_URL)

    for _ in range(WAIT_MINUTES * 60):
        await asyncio.sleep(1)
        try:
            url = tab.url
            if "sso.accounts.dowjones.com" not in url and "investors.com" in url:
                break
        except Exception:
            pass
    else:
        await browser.stop()
        print("Timed out waiting for login. Please try again.")
        sys.exit(1)

    print("Logged in. Saving profile cookies...")
    await browser.stop()

    print(f"Profile saved to {IBD_PROFILE_DIR}/")
    print("Automated runs will now reuse this session.")
    print("Re-run this script when the session expires (typically 30-90 days).")


def save_session() -> None:
    asyncio.run(_save_session_async())


if __name__ == "__main__":
    save_session()
