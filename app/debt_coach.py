"""
Debt payment coach — in-memory session + command router (PRD §10–§11).

Foundations: per-phone UserSession, command parsing, and reply building.
Extend handlers here; keep ``handle_inbound`` in ``app/bot.py`` thin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

# Keyed by Kapso/WA ``from`` number (string).
_sessions: dict[str, "UserSession"] = {}

# Interactive welcome: id must stay ``begin`` so we don't treat a tap as typed ``start`` (reset).
_BTN_BEGIN_ID: Final = "begin"


@dataclass(frozen=True)
class CoachOutbound:
    """Plain text, reply buttons (max 3), or WhatsApp *list* (rows with descriptions)."""

    text: str
    buttons: tuple[dict[str, str], ...] = ()
    header: str | None = None
    footer: str | None = None
    #: Opens the list (WhatsApp label, max 20 chars).
    list_button: str | None = None
    #: One section dict per Meta API: ``{"title": str, "rows": tuple[dict, ...]}`` — each row ``id``, ``title``, ``description``.
    list_sections: tuple[dict[str, Any], ...] = ()

    @property
    def has_buttons(self) -> bool:
        return bool(self.buttons)

    @property
    def has_list(self) -> bool:
        return bool(self.list_sections)


class CoachStep(str, Enum):
    IDLE = "idle"
    WAITING_DEBT_NAME = "waiting_debt_name"
    WAITING_AMOUNT = "waiting_amount"
    WAITING_DUE_DATE = "waiting_due_date"
    WAITING_BUDGET_INCOME = "waiting_budget_income"
    WAITING_BUDGET_ESSENTIALS = "waiting_budget_essentials"
    WAITING_BUDGET_FLEXIBLE = "waiting_budget_flexible"
    READY = "ready"


@dataclass
class UserSession:
    step: CoachStep = CoachStep.IDLE
    debt_label: str | None = None
    payment_amount: float | None = None
    due_date: str | None = None
    income: float | None = None
    essentials: float | None = None
    flexible: float | None = None
    """If set, shortfall/help uses this instead of income - essentials - flexible."""
    available_for_payment_override: float | None = None

    def reset(self) -> None:
        self.step = CoachStep.IDLE
        self.debt_label = None
        self.payment_amount = None
        self.due_date = None
        self.income = None
        self.essentials = None
        self.flexible = None
        self.available_for_payment_override = None

    def available_after_buckets(self) -> float | None:
        if (
            self.income is None
            or self.essentials is None
            or self.flexible is None
        ):
            return None
        return float(self.income - self.essentials - self.flexible)

    def effective_available_for_payment(self) -> float | None:
        if self.available_for_payment_override is not None:
            return float(self.available_for_payment_override)
        return self.available_after_buckets()


@dataclass(frozen=True)
class ReplyButton:
    id: str
    title: str


@dataclass(frozen=True)
class CoachReply:
    body: str
    buttons: tuple[ReplyButton, ...] = field(default_factory=tuple)
    list_button: str | None = None
    list_sections: tuple[dict[str, Any], ...] = ()


def get_session(phone: str) -> UserSession:
    if phone not in _sessions:
        _sessions[phone] = UserSession()
    return _sessions[phone]


def clear_all_sessions_for_tests() -> None:
    """Test hook only."""
    _sessions.clear()


_CMD_HELP_PRINCIPAL: Final = "help principal"
_CMD_DEMO_SHORTFALL: Final = "demo shortfall"
# List row ids from ``menu`` interactive list → same names as ``parse_command`` returns.
_MENU_LIST_ROW_TO_CMD: Final[dict[str, str]] = {
    "m_start": "start",
    "m_hello": "hello",
    "m_menu": "menu",
    "m_goal": "goal",
    "m_budget": "budget",
    "m_envelope": "envelope",
    "m_reminder": "reminder",
    "m_help_principal": _CMD_HELP_PRINCIPAL,
    "m_demo_shortfall": _CMD_DEMO_SHORTFALL,
}
_SHORTFALL_PHRASES: Final = (
    "can't cover principal",
    "cant cover principal",
    "cannot cover principal",
    "can't afford principal",
    "cant afford principal",
    "cannot afford principal",
    "principal help",
    "help with principal",
)


def parse_command(text: str) -> str | None:
    """Return normalized command name if ``text`` is a command line, else None."""
    t = text.strip().lower()
    if not t:
        return None
    if t in _MENU_LIST_ROW_TO_CMD:
        return _MENU_LIST_ROW_TO_CMD[t]
    if t == _CMD_HELP_PRINCIPAL or t.startswith(_CMD_HELP_PRINCIPAL + " "):
        return _CMD_HELP_PRINCIPAL
    if any(phrase in t for phrase in _SHORTFALL_PHRASES):
        return _CMD_HELP_PRINCIPAL
    if t == _CMD_DEMO_SHORTFALL or t.startswith(_CMD_DEMO_SHORTFALL + " "):
        return _CMD_DEMO_SHORTFALL
    if t in {"show reminder", "show the reminder", "show_reminder"}:
        return "reminder"
    if t == "help_principal" or t.startswith("help_principal "):
        return _CMD_HELP_PRINCIPAL
    token = t.split()[0]
    if token in {"start", "hello", "menu", "goal", "budget", "envelope", "reminder"} and t == token:
        return token
    return None


def map_intent_label_to_command(intent: str) -> str | None:
    """
    Map :func:`app.services.claude_client.get_intent` labels to ``parse_command`` names.

    Returns ``None`` for ``unknown`` or unrecognized labels (let conversation handle text).
    """
    label = intent.strip().lower().strip(".\"' ")
    if not label or label == "unknown":
        return None
    if label == "help_principal":
        return _CMD_HELP_PRINCIPAL
    if label == "demo_shortfall":
        return _CMD_DEMO_SHORTFALL
    if label in {"start", "menu", "goal", "budget", "envelope", "reminder"}:
        return label
    # Router groups greetings with ``start``; treat like ``start`` for welcome.
    if label == "hello":
        return "hello"
    return None


def should_run_intent_fallback(session: UserSession) -> bool:
    """When ``False``, skip LLM intent — user is likely sending amount/budget answers."""
    return session.step not in (
        CoachStep.WAITING_AMOUNT,
        CoachStep.WAITING_DUE_DATE,
        CoachStep.WAITING_BUDGET_INCOME,
        CoachStep.WAITING_BUDGET_ESSENTIALS,
        CoachStep.WAITING_BUDGET_FLEXIBLE,
    )


def _parse_money_and_rest(text: str) -> tuple[float | None, str | None]:
    """
    Parse a line like ``$450 due May 15`` → (450.0, "May 15").
    """
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", text)
    if not m:
        return None, None
    raw = m.group(1).replace(",", "")
    try:
        amount = float(raw)
    except ValueError:
        return None, None
    rest = text[m.end() :].strip()
    due = rest.removeprefix("due ").strip() if rest else None
    if not due:
        due = rest or None
    return amount, due


def parse_first_amount(text: str) -> float | None:
    """First money-like number in ``text`` (e.g. ``3000``, ``$3,000.50``)."""
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", text.strip())
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    try:
        v = float(raw)
    except ValueError:
        return None
    if v < 0:
        return None
    return v


def parse_budget_triple(text: str) -> tuple[float, float, float] | None:
    """
    Parse ``income 3000 essentials 1800 flexible 500`` (case-insensitive, flexible order).
    """
    lower = text.lower()
    income_m = re.search(r"income\s*([\d,]+(?:\.\d+)?)", lower)
    ess_m = re.search(r"essentials\s*([\d,]+(?:\.\d+)?)", lower)
    flex_m = re.search(r"flexible\s*([\d,]+(?:\.\d+)?)", lower)
    if not (income_m and ess_m and flex_m):
        return None

    def _f(m: re.Match[str]) -> float:
        return float(m.group(1).replace(",", ""))

    return _f(income_m), _f(ess_m), _f(flex_m)


def _needs_setup(session: UserSession) -> bool:
    return session.payment_amount is None or session.due_date is None


def _has_goal(session: UserSession) -> bool:
    return session.payment_amount is not None and session.due_date is not None


def _has_budget(session: UserSession) -> bool:
    return (
        session.income is not None
        and session.essentials is not None
        and session.flexible is not None
    )


def _menu_list_sections(session: UserSession) -> tuple[dict[str, Any], ...]:
    """WhatsApp list rows, filtered by session progress.

    Titles carry an emoji + plain words (no descriptions) so the row is
    self-explanatory and the chat echo stays clean.
    """
    rows: list[dict[str, str]] = []

    rows.append({"id": "m_start", "title": "🚀 Start over"})

    if not _has_goal(session):
        rows.append({"id": "m_goal", "title": "🎯 Set payment goal"})

    if _has_goal(session):
        rows.append({"id": "m_budget", "title": "💰 Set budget"})
        rows.append({"id": "m_envelope", "title": "📦 Envelope"})
        rows.append({"id": "m_reminder", "title": "🔔 Reminder"})
        rows.append({"id": "m_help_principal", "title": "🆘 Help with payment"})

    rows.append({"id": "m_demo_shortfall", "title": "🧪 Demo shortfall"})

    return ({"title": "What's next?", "rows": tuple(rows)},)


def _welcome_outbound(session: UserSession) -> CoachOutbound:
    session.reset()
    session.step = CoachStep.WAITING_DEBT_NAME
    body = (
        "Hey 👋 — glad you're here.\n\n"
        "I'm a tiny coach for one debt payment.\n"
        "We pick a goal, do a quick budget, and (optional) set a reminder.\n\n"
        "No real money moves — just clarity. 💛\n\n"
        "Tell me which debt we're planning for (e.g. credit card, car loan), or tap *Start*."
    )
    return CoachOutbound(
        text=body,
        buttons=(
            {"id": _BTN_BEGIN_ID, "title": "Start"},
            {"id": "menu", "title": "Menu"},
        ),
        header="Hi there 👋",
        footer="Simulated demo — not financial advice.",
    )


def _cmd_menu(session: UserSession) -> CoachOutbound:
    return CoachOutbound(
        text="Pick what you'd like to do next.",
        list_button="See options",
        list_sections=_menu_list_sections(session),
        footer="Or type a command (e.g. start, budget).",
    )


def _cmd_goal(session: UserSession) -> str:
    if not session.debt_label:
        session.step = CoachStep.WAITING_DEBT_NAME
        return "What debt are we planning for? (e.g. Credit card)"
    session.step = CoachStep.WAITING_AMOUNT
    return (
        f"Got it — {session.debt_label}.\n\n"
        f"{_prompt_amount()}"
    )


def _prompt_amount() -> str:
    return (
        "How much do you need to pay? "
        "Reply with one number (e.g. *450* or *$450*)."
    )


def _prompt_due_date() -> str:
    return (
        "When is it due? "
        "Reply with a date (e.g. *May 15* or *the 15th*)."
    )


def _prompt_budget_income() -> str:
    return (
        "What's your *monthly income* (take-home)? "
        "Reply with one number (e.g. *3000* or *$3,000*)."
    )


def _prompt_budget_essentials() -> str:
    return (
        "How much goes to *essentials* each month? "
        "(Rent, utilities, groceries, transport — one total number.)"
    )


def _prompt_budget_flexible() -> str:
    return (
        "How much is *flexible spending*? "
        "(Dining out, subscriptions, fun — rough total is fine.)"
    )


def _begin_budget_flow(session: UserSession) -> str:
    session.income = None
    session.essentials = None
    session.flexible = None
    session.step = CoachStep.WAITING_BUDGET_INCOME
    return (
        "Let's do your budget — one number at a time.\n\n"
        f"{_prompt_budget_income()}"
    )


def _finalize_budget_coach_reply(session: UserSession) -> CoachReply:
    """Summary after income, essentials, and flexible are set."""
    avail = session.available_after_buckets()
    assert avail is not None
    goal = session.payment_amount or 0.0
    income = session.income or 0.0
    essentials = session.essentials or 0.0
    flexible = session.flexible or 0.0
    fits = avail >= goal
    session.step = CoachStep.READY
    fit_line = (
        f"Your ${goal:,.2f} goal looks feasible with ${avail:,.2f} available."
        if fits
        else (
            f"You have ${avail:,.2f} available toward a ${goal:,.2f} goal. "
            "That is tight; consider adjusting buckets or the goal."
        )
    )
    debt = session.debt_label or "Debt"
    illustrative = round(goal * 0.001, 2)
    return CoachReply(
        body=(
            "Great, your payment plan is ready.\n\n"
            f"Debt: {debt}\n"
            f"Due: {session.due_date}\n"
            f"Payment goal: ${goal:,.2f}\n\n"
            "Monthly plan:\n"
            f"Income: ${income:,.2f}\n"
            f"Essentials: ${essentials:,.2f}\n"
            f"Flexible spending: ${flexible:,.2f}\n"
            f"Available for payment: ${avail:,.2f}\n\n"
            f"{fit_line}\n\n"
            "Simulated envelope:\n"
            f"${goal:,.2f} set aside for this payment.\n"
            f"Estimated illustrative yield this month: ~${illustrative:,.2f}.\n"
            "This is simulated only, not a real account or guaranteed return.\n\n"
            "Tap a button for the next step, or type *envelope*, *reminder*, or *help principal*."
        ),
        buttons=(
            ReplyButton(id="envelope", title="Envelope"),
            ReplyButton(id="reminder", title="Reminder"),
            ReplyButton(id="help_principal", title="Principal help"),
        ),
    )


def _cmd_budget(session: UserSession) -> str:
    if _needs_setup(session):
        return 'Set your payment first (say start, then name the debt and amount like "$450 due May 15").'
    return _begin_budget_flow(session)


def _cmd_envelope(session: UserSession) -> str:
    if session.payment_amount is None:
        return "Complete your payment goal first (start → debt name → amount & date)."
    label = session.debt_label or "your debt"
    amt = session.payment_amount
    # Illustrative only (PRD demo assumptions).
    illustrative = round(amt * 0.001, 2)
    return (
        f"Simulated payment envelope for {label}: *${amt:,.2f}* set aside (not a real account).\n"
        f"Illustrative simulated yield this month: ~${illustrative:,.2f} (not guaranteed)."
    )


def _cmd_reminder(session: UserSession) -> str:
    if session.payment_amount is None or not session.due_date:
        return "Add amount and due date first (start flow or goal)."
    label = session.debt_label or "your payment"
    amt = session.payment_amount
    return (
        f"Reminder (simulated): your {label} payment is due tomorrow ({session.due_date}). "
        f"Move *${amt:,.2f}* from your simulated envelope to your bank today so you’re ready to pay."
    )


def _cmd_help_principal(session: UserSession) -> str:
    goal = session.payment_amount
    if goal is None:
        return "Set a payment goal first (start flow)."
    avail = session.effective_available_for_payment()
    if avail is None:
        return "Add your budget numbers first, or use demo shortfall."
    gap = goal - avail
    if gap <= 0:
        return (
            f"Your payment goal is *${goal:,.2f}* and your budget leaves *${avail:,.2f}* available — "
            "no shortfall for this goal. If something changed, say budget again or use "
            f"{_CMD_DEMO_SHORTFALL} for the pitch scenario."
        )
    flex_half = round(max(session.flexible or 0, 0) / 2, 2) if session.flexible else 60.0
    return (
        f"Your payment goal is *${goal:,.2f}*, but your budget leaves *${avail:,.2f}* available. "
        f"You're short *${gap:,.2f}*.\n\n"
        "Here are *three general options to consider*:\n"
        f"1) Reduce flexible spending (e.g. by ~${flex_half:,.2f}) if that’s realistic for you.\n"
        "2) See whether splitting extra principal is allowed under *your lender terms*.\n"
        "3) Prioritize the *minimum payment* to reduce late-fee risk if you’re unsure.\n\n"
        "*Check your lender terms before changing payments.* This isn’t financial advice."
    )


def _cmd_demo_shortfall(session: UserSession) -> str:
    session.available_for_payment_override = 330.0
    return (
        "Demo mode: treating *$330* as available for this payment (override). "
        f"Now text: {_CMD_HELP_PRINCIPAL}"
    )


def _route_command(cmd: str, session: UserSession) -> str | CoachReply | CoachOutbound:
    if cmd in ("start", "hello"):
        return _welcome_outbound(session)
    if cmd == "menu":
        return _cmd_menu(session)
    if cmd == "goal":
        return _cmd_goal(session)
    if cmd == "budget":
        return _cmd_budget(session)
    if cmd == "envelope":
        return _cmd_envelope(session)
    if cmd == "reminder":
        return _cmd_reminder(session)
    if cmd == _CMD_HELP_PRINCIPAL:
        return _cmd_help_principal(session)
    if cmd == _CMD_DEMO_SHORTFALL:
        return _cmd_demo_shortfall(session)
    return _cmd_menu(session)


def _route_conversation(text: str, session: UserSession) -> str | CoachReply:
    raw = text.strip()
    if session.step == CoachStep.IDLE:
        return "Type *start* or *hello* for the welcome message, or *menu* for commands."

    if session.step == CoachStep.WAITING_DEBT_NAME:
        session.debt_label = raw
        session.step = CoachStep.WAITING_AMOUNT
        return (
            f"Thanks — {session.debt_label}.\n\n"
            f"{_prompt_amount()}"
        )

    if session.step == CoachStep.WAITING_AMOUNT:
        amt, due = _parse_money_and_rest(raw)
        if amt is not None and due:
            session.payment_amount = amt
            session.due_date = due
            session.income = None
            session.essentials = None
            session.flexible = None
            session.step = CoachStep.WAITING_BUDGET_INCOME
            return (
                "Nice — got your payment details.\n\n"
                f"{_prompt_budget_income()}"
            )
        if amt is None:
            return (
                "I didn’t catch a number. Try something like *450* or *$450*.\n\n"
                f"{_prompt_amount()}"
            )
        session.payment_amount = amt
        session.step = CoachStep.WAITING_DUE_DATE
        return _prompt_due_date()

    if session.step == CoachStep.WAITING_DUE_DATE:
        due = raw.removeprefix("due ").strip() or raw
        if not due:
            return (
                "Please send a date (e.g. *May 15* or *the 15th*).\n\n"
                f"{_prompt_due_date()}"
            )
        session.due_date = due
        session.income = None
        session.essentials = None
        session.flexible = None
        session.step = CoachStep.WAITING_BUDGET_INCOME
        return (
            "Nice — got your payment details.\n\n"
            f"{_prompt_budget_income()}"
        )

    if session.step == CoachStep.WAITING_BUDGET_INCOME:
        triple = parse_budget_triple(raw)
        if triple:
            session.income, session.essentials, session.flexible = triple
            return _finalize_budget_coach_reply(session)
        val = parse_first_amount(raw)
        if val is None:
            return (
                "I didn’t catch a number. Try something like *3000* or *$3,000*.\n\n"
                f"{_prompt_budget_income()}"
            )
        session.income = val
        session.step = CoachStep.WAITING_BUDGET_ESSENTIALS
        return _prompt_budget_essentials()

    if session.step == CoachStep.WAITING_BUDGET_ESSENTIALS:
        val = parse_first_amount(raw)
        if val is None:
            return (
                "Please send one number for essentials (e.g. *1800*).\n\n"
                f"{_prompt_budget_essentials()}"
            )
        session.essentials = val
        session.step = CoachStep.WAITING_BUDGET_FLEXIBLE
        return _prompt_budget_flexible()

    if session.step == CoachStep.WAITING_BUDGET_FLEXIBLE:
        val = parse_first_amount(raw)
        if val is None:
            return (
                "Please send one number for flexible spending (e.g. *500*).\n\n"
                f"{_prompt_budget_flexible()}"
            )
        session.flexible = val
        return _finalize_budget_coach_reply(session)

    # READY / IDLE: gentle recovery
    return (
        "You’re set for this demo session. Try: envelope · reminder · "
        f"{_CMD_HELP_PRINCIPAL} · menu · start (reset)\n"
        f"Tip: {_CMD_DEMO_SHORTFALL} then {_CMD_HELP_PRINCIPAL} for the pitch shortfall copy."
    )


def _reply_begin_tap(session: UserSession) -> CoachOutbound | None:
    """Handle the welcome ``Start`` button (id ``begin``) without resetting the session."""
    if session.step != CoachStep.WAITING_DEBT_NAME or session.debt_label:
        return None
    return CoachOutbound(
        text=(
            "Love that energy. ✨\n\n"
            "*Which debt are we focusing on first?*\n"
            "Reply with a short name (for example: Credit card or Car loan)."
        )
    )


def _to_outbound(routed: str | CoachReply | CoachOutbound) -> CoachOutbound:
    if isinstance(routed, CoachOutbound):
        return routed
    if isinstance(routed, CoachReply):
        return CoachOutbound(
            text=routed.body,
            buttons=tuple({"id": button.id, "title": button.title} for button in routed.buttons),
            list_button=routed.list_button,
            list_sections=routed.list_sections,
        )
    return CoachOutbound(text=routed)


def _to_reply(routed: str | CoachReply | CoachOutbound) -> CoachReply:
    if isinstance(routed, CoachReply):
        return routed
    if isinstance(routed, CoachOutbound):
        return CoachReply(
            body=routed.text,
            buttons=tuple(ReplyButton(id=button["id"], title=button["title"]) for button in routed.buttons),
            list_button=routed.list_button,
            list_sections=routed.list_sections,
        )
    return CoachReply(body=routed)


def build_outbound(
    phone: str,
    text: str | None,
    *,
    resolved_command: str | None = None,
) -> CoachOutbound:
    """
    Latest inbound ``text`` for ``phone`` → outbound payload (text and optional buttons).

    ``resolved_command``: when ``parse_command`` returned ``None``, the caller may pass
    a command from :func:`map_intent_label_to_command` / :func:`get_intent` as a second check.
    """
    if text is None or not text.strip():
        return CoachOutbound(
            text="Send a message when you're ready — type *start*, *hello*, or *menu*, or tap a button if you see one."
        )

    raw = text.strip()
    session = get_session(phone)

    if raw.lower() == _BTN_BEGIN_ID:
        begin_out = _reply_begin_tap(session)
        if begin_out:
            return begin_out

    cmd = parse_command(raw)
    if cmd is None and resolved_command:
        cmd = resolved_command
    if cmd in ("start", "hello"):
        return _welcome_outbound(session)
    if cmd:
        return _to_outbound(_route_command(cmd, session))
    return _to_outbound(_route_conversation(raw, session))


def build_response(phone: str, text: str | None) -> CoachReply:
    """
    Main entry: latest inbound text for ``phone`` → outbound response.
    """
    if text is None or not text.strip():
        return CoachReply("Send text to continue — try: start or menu")

    raw = text.strip()
    session = get_session(phone)

    if raw.lower() == _BTN_BEGIN_ID:
        begin_out = _reply_begin_tap(session)
        if begin_out:
            return _to_reply(begin_out)

    cmd = parse_command(raw)
    if cmd:
        routed = _route_command(cmd, session)
    else:
        routed = _route_conversation(raw, session)
    return _to_reply(routed)


def build_reply(phone: str, text: str | None) -> str:
    """
    Compatibility helper for tests and callers that only need text.
    """
    return build_response(phone, text).body
