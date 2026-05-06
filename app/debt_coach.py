"""
Debt payment coach — in-memory session + command router (PRD §10–§11).

Foundations: per-phone UserSession, command parsing, and reply building.
Extend handlers here; keep ``handle_inbound`` in ``app/bot.py`` thin.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Final

# Keyed by Kapso/WA ``from`` number (string).
_sessions: dict[str, "UserSession"] = {}


class CoachStep(str, Enum):
    IDLE = "idle"
    WAITING_DEBT_NAME = "waiting_debt_name"
    WAITING_AMOUNT_DUE = "waiting_amount_due"
    WAITING_BUDGET = "waiting_budget"
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


def get_session(phone: str) -> UserSession:
    if phone not in _sessions:
        _sessions[phone] = UserSession()
    return _sessions[phone]


def clear_all_sessions_for_tests() -> None:
    """Test hook only."""
    _sessions.clear()


_CMD_HELP_PRINCIPAL: Final = "help principal"
_CMD_DEMO_SHORTFALL: Final = "demo shortfall"


def parse_command(text: str) -> str | None:
    """Return normalized command name if ``text`` is a command line, else None."""
    t = text.strip().lower()
    if not t:
        return None
    if t == _CMD_HELP_PRINCIPAL or t.startswith(_CMD_HELP_PRINCIPAL + " "):
        return _CMD_HELP_PRINCIPAL
    if t == _CMD_DEMO_SHORTFALL or t.startswith(_CMD_DEMO_SHORTFALL + " "):
        return _CMD_DEMO_SHORTFALL
    token = t.split()[0]
    if token in {"start", "menu", "goal", "budget", "envelope", "reminder"} and t == token:
        return token
    return None


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


def _menu_text() -> str:
    return (
        "Commands:\n"
        "• start — begin / reset\n"
        "• menu — this list\n"
        "• goal — jump to amount & due date (after debt name)\n"
        "• budget — enter income & buckets\n"
        "• envelope — simulated envelope + illustrative yield\n"
        "• reminder — simulated day-before nudge\n"
        f"• {_CMD_HELP_PRINCIPAL} — shortfall ideas (general, not advice)\n"
        f"• {_CMD_DEMO_SHORTFALL} — demo gap ($330 vs $450 goal)"
    )


def _cmd_start(session: UserSession) -> str:
    session.reset()
    session.step = CoachStep.WAITING_DEBT_NAME
    return "I can help you plan a debt payment. What debt are we planning for?"


def _cmd_menu(_session: UserSession) -> str:
    return _menu_text()


def _cmd_goal(session: UserSession) -> str:
    if not session.debt_label:
        session.step = CoachStep.WAITING_DEBT_NAME
        return "What debt are we planning for? (e.g. Credit card)"
    session.step = CoachStep.WAITING_AMOUNT_DUE
    return (
        f"Got it — {session.debt_label}. "
        "How much do you need to pay and when is it due? "
        'Reply like: "$450 due May 15"'
    )


def _cmd_budget(session: UserSession) -> str:
    if _needs_setup(session):
        return 'Set your payment first (say start, then name the debt and amount like "$450 due May 15").'
    session.step = CoachStep.WAITING_BUDGET
    return (
        "What’s your monthly income, essentials, and flexible spending?\n"
        "Example: Income 3000, essentials 1800, flexible 500"
    )


def _cmd_envelope(session: UserSession) -> str:
    if session.payment_amount is None:
        return "Complete your payment goal first (start → debt name → amount & date)."
    label = session.debt_label or "your debt"
    amt = session.payment_amount
    # Illustrative only (PRD demo assumptions).
    illustrative = round(amt * 0.001, 2)
    return (
        f"Simulated payment envelope for {label}: **${amt:,.2f}** set aside (not a real account).\n"
        f"Illustrative simulated yield this month: ~${illustrative:,.2f} (not guaranteed)."
    )


def _cmd_reminder(session: UserSession) -> str:
    if session.payment_amount is None or not session.due_date:
        return "Add amount and due date first (start flow or goal)."
    label = session.debt_label or "your payment"
    amt = session.payment_amount
    return (
        f"Reminder (simulated): your {label} payment is due tomorrow ({session.due_date}). "
        f"Move **${amt:,.2f}** from your simulated envelope to your bank today so you’re ready to pay."
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
            f"Your payment goal is **${goal:,.2f}** and your budget leaves **${avail:,.2f}** available — "
            "no shortfall for this goal. If something changed, say budget again or use "
            f"{_CMD_DEMO_SHORTFALL} for the pitch scenario."
        )
    flex_half = round(max(session.flexible or 0, 0) / 2, 2) if session.flexible else 60.0
    return (
        f"Your payment goal is **${goal:,.2f}**, but your budget leaves **${avail:,.2f}** available. "
        f"You're short **${gap:,.2f}**.\n\n"
        "Here are **three general options to consider**:\n"
        f"1) Reduce flexible spending (e.g. by ~${flex_half:,.2f}) if that’s realistic for you.\n"
        "2) See whether splitting extra principal is allowed under **your lender terms**.\n"
        "3) Prioritize the **minimum payment** to reduce late-fee risk if you’re unsure.\n\n"
        "**Check your lender terms before changing payments.** This isn’t financial advice."
    )


def _cmd_demo_shortfall(session: UserSession) -> str:
    session.available_for_payment_override = 330.0
    return (
        "Demo mode: treating **$330** as available for this payment (override). "
        f"Now text: {_CMD_HELP_PRINCIPAL}"
    )


def _route_command(cmd: str, session: UserSession) -> str:
    if cmd == "start":
        return _cmd_start(session)
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
    return _menu_text()


def _route_conversation(text: str, session: UserSession) -> str:
    raw = text.strip()
    if session.step == CoachStep.IDLE:
        return "Type **start** to plan a payment, or **menu** for commands."

    if session.step == CoachStep.WAITING_DEBT_NAME:
        session.debt_label = raw
        session.step = CoachStep.WAITING_AMOUNT_DUE
        return (
            f"Thanks — {session.debt_label}. "
            'How much is the payment and when is it due? Example: "$450 due May 15"'
        )

    if session.step == CoachStep.WAITING_AMOUNT_DUE:
        amt, due = _parse_money_and_rest(raw)
        if amt is None or not due:
            return 'I need an amount and a due date. Try: "$450 due May 15"'
        session.payment_amount = amt
        session.due_date = due
        session.step = CoachStep.WAITING_BUDGET
        return (
            "What’s your monthly income, essentials, and flexible spending?\n"
            "Example: Income 3000, essentials 1800, flexible 500"
        )

    if session.step == CoachStep.WAITING_BUDGET:
        triple = parse_budget_triple(raw)
        if not triple:
            return (
                "Please use: Income 3000, essentials 1800, flexible 500 "
                "(you can tweak the numbers)."
            )
        income, essentials, flexible = triple
        session.income = income
        session.essentials = essentials
        session.flexible = flexible
        avail = session.available_after_buckets()
        assert avail is not None
        goal = session.payment_amount or 0.0
        fits = avail >= goal
        session.step = CoachStep.READY
        fit_line = (
            f"That leaves **${avail:,.2f}** for this payment vs your **${goal:,.2f}** goal — looks feasible."
            if fits
            else (
                f"That leaves **${avail:,.2f}** for this payment vs your **${goal:,.2f}** goal — "
                "that’s tight; consider adjusting buckets or the goal."
            )
        )
        debt = session.debt_label or "Debt"
        return (
            f"Saved: {debt}, **${goal:,.2f}** due {session.due_date}. "
            f"Income **${income:,.2f}**, essentials **${essentials:,.2f}**, flexible **${flexible:,.2f}**.\n"
            f"{fit_line}\n\n"
            "Simulated payment envelope is ready (copy only — not a real account). "
            f"Next: type **envelope**, then **reminder**, then **{_CMD_HELP_PRINCIPAL}** if you want the shortfall ideas."
        )

    # READY / IDLE: gentle recovery
    return (
        "You’re set for this demo session. Try: envelope · reminder · "
        f"{_CMD_HELP_PRINCIPAL} · menu · start (reset)\n"
        f"Tip: {_CMD_DEMO_SHORTFALL} then {_CMD_HELP_PRINCIPAL} for the pitch shortfall copy."
    )


def build_reply(phone: str, text: str | None) -> str:
    """
    Main entry: latest inbound text for ``phone`` → outbound body string.
    """
    if text is None or not text.strip():
        return "Send text to continue — try: start or menu"

    session = get_session(phone)
    cmd = parse_command(text)
    if cmd:
        return _route_command(cmd, session)
    return _route_conversation(text, session)
