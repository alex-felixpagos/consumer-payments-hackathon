"""Unit tests for the Felix Pay in-memory wallet store."""

import pytest

from app.felix_pay.wallet import DEFAULT_WALLET_BALANCE_USD, WalletStore


def test_unknown_phone_returns_default_balance() -> None:
    w = WalletStore()
    assert w.get_balance("+15555550001") == DEFAULT_WALLET_BALANCE_USD


def test_debit_decrements_balance() -> None:
    w = WalletStore()
    phone = "+15555550002"
    new_balance = w.debit(phone, 10.0)
    assert new_balance == pytest.approx(DEFAULT_WALLET_BALANCE_USD - 10.0)
    assert w.get_balance(phone) == pytest.approx(DEFAULT_WALLET_BALANCE_USD - 10.0)


def test_consecutive_debits_apply() -> None:
    w = WalletStore()
    phone = "+15555550003"
    w.debit(phone, 10.0)
    w.debit(phone, 5.0)
    assert w.get_balance(phone) == pytest.approx(DEFAULT_WALLET_BALANCE_USD - 15.0)


def test_negative_debit_rejected() -> None:
    w = WalletStore()
    with pytest.raises(ValueError, match="negative"):
        w.debit("+15555550004", -1.0)


def test_reset_returns_to_default() -> None:
    w = WalletStore()
    phone = "+15555550005"
    w.debit(phone, 50.0)
    assert w.get_balance(phone) != DEFAULT_WALLET_BALANCE_USD
    w.reset(phone)
    assert w.get_balance(phone) == DEFAULT_WALLET_BALANCE_USD


def test_clear_drops_all_balances() -> None:
    w = WalletStore()
    w.debit("+15555550006", 5.0)
    w.debit("+15555550007", 5.0)
    w.clear()
    assert w.get_balance("+15555550006") == DEFAULT_WALLET_BALANCE_USD
    assert w.get_balance("+15555550007") == DEFAULT_WALLET_BALANCE_USD
