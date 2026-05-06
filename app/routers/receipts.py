"""Public HTML receipt pages for Felix Pay (iOS-style mock)."""

from __future__ import annotations

import html
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.receipts_memory import ReceiptRecord, get_receipt

router = APIRouter()


def _format_date(iso_str: str) -> str:
    """Render an ISO-8601 timestamp as ``Mar 4, 2026, 12:30 PM`` (best effort)."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return iso_str
    return dt.strftime("%b %-d, %Y, %-I:%M %p")


def _format_money(amount: float, decimals: int = 2) -> str:
    return f"{amount:,.{decimals}f}"


def _render_receipt_page(record: ReceiptRecord, request: Request) -> str:
    rid = html.escape(record.receipt_id)
    vendor = html.escape(record.vendor_name)
    rail = html.escape(record.payment_rail or "Bre-B")
    date_str = html.escape(_format_date(record.created_at))

    total_usd = record.total_usd or record.amount_usd
    total_cop = int(record.total_cop or record.amount_cop)
    rate_value = int(round(record.fx_rate)) if record.fx_rate else 0
    new_balance = record.new_balance_usd

    if record.tip_pct and record.tip_pct > 0:
        tip_label = f"{int(round(record.tip_pct * 100))}% (${_format_money(record.tip_usd)})"
        tip_row_html = f"""
            <div class="rp-row">
              <div class="rp-row-label">Tip</div>
              <div class="rp-row-value muted">{html.escape(tip_label)}</div>
            </div>"""
    else:
        tip_row_html = ""

    if new_balance > 0:
        balance_row_html = f"""
            <div class="rp-row">
              <div class="rp-row-label">New Felix Wallet balance</div>
              <div class="rp-row-value">${_format_money(new_balance)} <span class="rp-unit">USD</span></div>
            </div>"""
    else:
        balance_row_html = ""

    receipt_short = rid.split("-")[0] if rid else "—"
    full_url = str(request.url).split("?")[0]
    short_url = full_url.replace("https://", "").replace("http://", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#005c4b" />
  <title>Receipt · Felix Pay</title>
  <style>
    :root {{
      color-scheme: light;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      background: #f2f2f7;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, "Helvetica Neue", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    body {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    .page {{
      width: 100%;
      max-width: 420px;
      background: #f2f2f7;
      min-height: 100vh;
      padding-bottom: 40px;
    }}
    .rp-header {{
      background: linear-gradient(160deg, #005c4b 0%, #00796b 100%);
      padding: 36px 20px 30px;
      text-align: center;
      color: #fff;
    }}
    .rp-check {{
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: rgba(255,255,255,0.18);
      border: 2px solid rgba(255,255,255,0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      margin: 0 auto 14px;
    }}
    .rp-label {{
      font-size: 12px;
      font-weight: 700;
      color: rgba(255,255,255,0.65);
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 6px;
    }}
    .rp-amount {{
      font-size: 44px;
      font-weight: 800;
      letter-spacing: -2px;
      line-height: 1;
    }}
    .rp-amount span {{
      font-size: 18px;
      font-weight: 500;
      opacity: 0.6;
      margin-left: 4px;
      letter-spacing: 0;
    }}
    .rp-vendor {{
      font-size: 14px;
      color: rgba(255,255,255,0.75);
      margin-top: 8px;
    }}
    .rp-card {{
      background: #fff;
      border-radius: 14px;
      margin: 16px 14px 0;
      overflow: hidden;
      box-shadow: 0 1px 0 rgba(0,0,0,0.04);
    }}
    .rp-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 13px 16px;
      border-bottom: 1px solid #f0f0f5;
      gap: 16px;
    }}
    .rp-row:last-child {{ border-bottom: none; }}
    .rp-row-label {{
      font-size: 13px;
      color: #8e8e93;
    }}
    .rp-row-value {{
      font-size: 14px;
      font-weight: 500;
      color: #1c1c1e;
      text-align: right;
    }}
    .rp-row-value.green {{ color: #34c759; }}
    .rp-row-value.muted {{ color: #8e8e93; font-weight: 400; }}
    .rp-row-value .rp-unit {{
      font-weight: 400;
      color: #8e8e93;
      font-size: 12px;
      margin-left: 2px;
    }}
    .rp-footer {{
      padding: 20px 14px 24px;
      text-align: center;
      font-size: 11px;
      color: #aeaeb2;
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      letter-spacing: 0.04em;
      word-break: break-all;
    }}
    .rp-footer .rp-tx {{ display: block; margin-top: 4px; opacity: 0.7; }}
    .rp-brand {{
      text-align: center;
      font-size: 11px;
      color: #aeaeb2;
      margin-top: 6px;
      letter-spacing: 0.04em;
    }}
    .rp-brand strong {{ color: #00796b; font-weight: 700; }}
  </style>
</head>
<body>
  <div class="page">
    <div class="rp-header">
      <div class="rp-check">✓</div>
      <div class="rp-label">Payment Receipt</div>
      <div class="rp-amount">${_format_money(total_usd)}<span>USD</span></div>
      <div class="rp-vendor">{vendor} · Bogotá</div>
    </div>

    <div class="rp-card">
      <div class="rp-row">
        <div class="rp-row-label">To</div>
        <div class="rp-row-value">{vendor}</div>
      </div>
      <div class="rp-row">
        <div class="rp-row-label">Amount (COP)</div>
        <div class="rp-row-value green">{total_cop:,}</div>
      </div>
      <div class="rp-row">
        <div class="rp-row-label">Exchange rate</div>
        <div class="rp-row-value muted">1 USD ≈ {rate_value:,} COP</div>
      </div>{tip_row_html}
      <div class="rp-row">
        <div class="rp-row-label">Payment rail</div>
        <div class="rp-row-value muted">{rail} · Bancolombia</div>
      </div>
      <div class="rp-row">
        <div class="rp-row-label">Status</div>
        <div class="rp-row-value green">Confirmed ✓</div>
      </div>
      <div class="rp-row">
        <div class="rp-row-label">Date</div>
        <div class="rp-row-value muted">{date_str}</div>
      </div>{balance_row_html}
    </div>

    <div class="rp-footer">
      <span>{html.escape(short_url)}</span>
      <span class="rp-tx">tx · {html.escape(receipt_short)}</span>
    </div>
    <div class="rp-brand">Powered by <strong>Felix Pay</strong></div>
  </div>
</body>
</html>
"""


@router.get("/r/{receipt_id}", response_class=HTMLResponse)
async def receipt_html(receipt_id: str, request: Request) -> HTMLResponse:
    record = get_receipt(receipt_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return HTMLResponse(content=_render_receipt_page(record, request))
