"""Public HTML receipt pages (Track C)."""

from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.receipts_memory import get_receipt

router = APIRouter()


@router.get("/r/{receipt_id}", response_class=HTMLResponse)
async def receipt_html(receipt_id: str) -> HTMLResponse:
    record = get_receipt(receipt_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Receipt not found")

    rid = html.escape(record.receipt_id)
    vendor = html.escape(record.vendor_name)
    created = html.escape(record.created_at)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Receipt {rid}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem; }}
    dl {{ display: grid; grid-template-columns: auto 1fr; gap: 0.35rem 1rem; }}
    dt {{ font-weight: 600; color: #444; }}
    dd {{ margin: 0; }}
  </style>
</head>
<body>
  <h1>Receipt</h1>
  <dl>
    <dt>Receipt ID</dt><dd>{rid}</dd>
    <dt>Amount (USD)</dt><dd>{record.amount_usd}</dd>
    <dt>Amount (COP)</dt><dd>{record.amount_cop}</dd>
    <dt>FX rate</dt><dd>{record.fx_rate}</dd>
    <dt>Vendor</dt><dd>{vendor}</dd>
    <dt>Created</dt><dd>{created}</dd>
  </dl>
</body>
</html>
"""
    return HTMLResponse(content=page)
