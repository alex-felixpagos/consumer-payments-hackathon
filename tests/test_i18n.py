"""Locale detection + per-user persistence + localized strings."""

import pytest

from app.concierge import i18n
from app.concierge.prompts import system_message, system_prompt


@pytest.fixture(autouse=True)
def _clean_locales():
    i18n.reset_locales()
    yield
    i18n.reset_locales()


def test_default_locale_is_en_us() -> None:
    assert i18n.get_locale("u1") == "en-us"


def test_detects_portuguese_from_message() -> None:
    locale = i18n.resolve_locale("u1", "Quero enviar dinheiro para minha mãe hoje")
    assert locale == "pt-br"
    assert i18n.get_locale("u1") == "pt-br"


def test_detects_spanish_from_message() -> None:
    locale = i18n.resolve_locale("u2", "Hola, necesito enviar dinero a mi mamá hoy")
    assert locale == "es"
    assert i18n.get_locale("u2") == "es"


def test_keeps_english_when_no_hints() -> None:
    locale = i18n.resolve_locale("u3", "Send 200 to my sister in Mexico, cash, today")
    assert locale == "en-us"


def test_first_detection_is_sticky() -> None:
    i18n.resolve_locale("u4", "Quero enviar dinheiro hoje")
    locale = i18n.resolve_locale("u4", "200 to Mexico")  # English follow-up
    assert locale == "pt-br"


def test_explicit_switch_overrides_sticky_locale() -> None:
    i18n.set_locale("u5", "pt-br")
    locale = i18n.resolve_locale("u5", "habla español por favor")
    assert locale == "es"


def test_system_prompt_exists_for_each_locale() -> None:
    for loc in i18n.SUPPORTED_LOCALES:
        prompt = system_prompt(loc)
        assert prompt
        assert "Felix" in prompt


def test_system_messages_exist_for_each_locale() -> None:
    for loc in i18n.SUPPORTED_LOCALES:
        for key in ("non_text", "agent_error", "agent_empty"):
            assert system_message(loc, key)
