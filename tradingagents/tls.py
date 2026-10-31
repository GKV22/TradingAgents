"""Use the operating system's certificate store for HTTPS verification.

Antivirus HTTPS scanning (e.g. Norton/Avast "Web/Mail Shield") re-signs every
TLS connection with a root certificate that the vendor installs in the Windows
store. Browsers trust it; Python's bundled ``certifi`` list does not, so every
LLM and data-provider call fails with CERTIFICATE_VERIFY_FAILED.

``truststore`` makes Python's ``ssl`` module (and therefore requests, httpx and
the OpenAI/Anthropic/Google SDKs) verify against the OS store instead, exactly
as the browser does. Certificate verification stays fully on.

Set ``TRADINGAGENTS_SYSTEM_CERTS=0`` to keep Python's default behaviour.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_applied = False


def use_system_trust_store() -> bool:
    """Inject the OS trust store into ``ssl``. Returns True if active."""
    global _applied
    if _applied:
        return True
    if os.getenv("TRADINGAGENTS_SYSTEM_CERTS", "1").strip().lower() in ("0", "false", "no"):
        return False
    try:
        import truststore
    except ImportError:
        logger.warning("truststore not installed; using Python's default CA bundle")
        return False
    truststore.inject_into_ssl()
    _applied = True
    return True
