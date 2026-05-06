"""
Locale handling — three supported locales: en-us, pt-br, es.

Detection is a small keyword heuristic: cheap, deterministic, no extra LLM call.
Per-user locale is sticky (first detected wins) until the user explicitly switches.
"""

from typing import Literal

Locale = Literal["en-us", "pt-br", "es"]
DEFAULT_LOCALE: Locale = "es"
SUPPORTED_LOCALES: tuple[Locale, ...] = ("en-us", "pt-br", "es")


_PT_HINTS = {
    "olá", "ola", "oi", "obrigado", "obrigada", "minha", "meu",
    "mãe", "mae", "irmã", "irma", "irmão", "irmao", "filho", "filha",
    "enviar", "mandar", "dinheiro", "reais", "real",
    "hoje", "amanhã", "amanha", "agora", "depois", "rápido", "rapido",
    "para", "quero", "preciso", "como",
}

_ES_HINTS = {
    "hola", "buenas", "gracias", "mi", "mamá", "mama", "papá", "papa",
    "hermano", "hermana", "hijo", "hija", "esposa", "esposo",
    "enviar", "mandar", "dinero", "plata", "pesos",
    "hoy", "mañana", "manana", "ahora", "rápido", "rapido", "urgente",
    "para", "quiero", "necesito", "cómo", "como",
}

_EXPLICIT_SWITCH = {
    "en-us": ("speak english", "habla english", "in english", "english please"),
    "pt-br": ("fala portugues", "fala português", "em portugues", "em português", "português", "portugues"),
    "es": ("habla español", "habla espanol", "en español", "en espanol", "español", "espanol"),
}


_LOCALE_BY_USER: dict[str, Locale] = {}


def detect_locale(text: str) -> Locale | None:
    """Best-effort detection from a single message. Returns None if uncertain."""
    if not text:
        return None
    lowered = text.lower()

    for locale, phrases in _EXPLICIT_SWITCH.items():
        if any(p in lowered for p in phrases):
            return locale  # type: ignore[return-value]

    tokens = {t.strip(".,!?¿¡:;\"'()") for t in lowered.split()}
    pt_score = len(tokens & _PT_HINTS)
    es_score = len(tokens & _ES_HINTS)

    if pt_score == 0 and es_score == 0:
        return None
    if pt_score > es_score:
        return "pt-br"
    if es_score > pt_score:
        return "es"
    return None  # tie — keep current


def get_locale(user_id: str) -> Locale:
    return _LOCALE_BY_USER.get(user_id, DEFAULT_LOCALE)


def set_locale(user_id: str, locale: Locale) -> None:
    _LOCALE_BY_USER[user_id] = locale


def resolve_locale(user_id: str, user_text: str) -> Locale:
    """Always return Spanish — enforced for the hackathon demo."""
    return "es"


def _is_explicit_switch(text: str) -> bool:
    lowered = text.lower()
    return any(p in lowered for phrases in _EXPLICIT_SWITCH.values() for p in phrases)


def reset_locales() -> None:
    """Test helper."""
    _LOCALE_BY_USER.clear()
