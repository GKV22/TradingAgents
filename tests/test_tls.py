"""System trust store injection (antivirus HTTPS scanning)."""

import sys
import types

import tradingagents.tls as tls


def _reset(monkeypatch):
    monkeypatch.setattr(tls, "_applied", False)


def test_injects_truststore(monkeypatch):
    _reset(monkeypatch)
    calls = []
    monkeypatch.setitem(sys.modules, "truststore",
                        types.SimpleNamespace(inject_into_ssl=lambda: calls.append(1)))
    monkeypatch.delenv("TRADINGAGENTS_SYSTEM_CERTS", raising=False)
    assert tls.use_system_trust_store() is True
    assert tls.use_system_trust_store() is True  # idempotent
    assert calls == [1]


def test_opt_out(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.setenv("TRADINGAGENTS_SYSTEM_CERTS", "0")
    assert tls.use_system_trust_store() is False


def test_missing_package_is_not_fatal(monkeypatch):
    _reset(monkeypatch)
    monkeypatch.delenv("TRADINGAGENTS_SYSTEM_CERTS", raising=False)
    monkeypatch.setitem(sys.modules, "truststore", None)  # forces ImportError
    assert tls.use_system_trust_store() is False
