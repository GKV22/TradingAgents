"""One-time setup: store IBD and Gmail credentials in Windows Credential Manager."""
import getpass
import sys

import keyring

SERVICE_NAME = "ibd-digest"

CREDENTIALS = [
    ("IBD_USERNAME", "investors.com email address", False),
    ("IBD_PASSWORD", "investors.com password", True),
    ("GMAIL_ADDRESS", "Gmail address (e.g. you@gmail.com)", False),
    ("GMAIL_APP_PASSWORD", "Gmail App Password (16-char, from Google Account → Security → App passwords)", True),
]


def main() -> None:
    print("IBD Weekly Digest — Credential Setup")
    print("Credentials will be stored encrypted in Windows Credential Manager.\n")

    for key, prompt, secret in CREDENTIALS:
        existing = keyring.get_password(SERVICE_NAME, key)
        if existing:
            overwrite = input(f"{key} already set. Overwrite? [y/N]: ").strip().lower()
            if overwrite != "y":
                print(f"  Keeping existing {key}.")
                continue

        if secret:
            value = getpass.getpass(f"{prompt}: ")
        else:
            value = input(f"{prompt}: ").strip()

        if not value:
            print(f"  Skipped {key} (empty input).")
            continue

        keyring.set_password(SERVICE_NAME, key, value)
        print(f"  Stored {key}.")

    print("\nDone. Run 'python scripts/ibd_digest.py --pdf <path>' to test.")


if __name__ == "__main__":
    main()
