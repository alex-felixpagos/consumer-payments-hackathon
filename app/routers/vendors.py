"""Public vendor landing pages (Track C1).

Renders a Spanish-language, mobile-first landing page at ``/v/{slug}`` that
mirrors the design prototype (see ``felix-pay-prototype.html``).
"""

from __future__ import annotations

import html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.vendors import VendorProfile, get_vendor

router = APIRouter()


# Pixel-identical QR SVG copied verbatim from the design prototype's
# ``.vendor-qr-section`` block. Not a real scannable QR — visual only.
_QR_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21">
  <rect width="21" height="21" fill="#fff"/>
  <rect x="0" y="0" width="7" height="7" fill="#1a1a1a"/>
  <rect x="1" y="1" width="5" height="5" fill="#fff"/>
  <rect x="2" y="2" width="3" height="3" fill="#1a1a1a"/>
  <rect x="14" y="0" width="7" height="7" fill="#1a1a1a"/>
  <rect x="15" y="1" width="5" height="5" fill="#fff"/>
  <rect x="16" y="2" width="3" height="3" fill="#1a1a1a"/>
  <rect x="0" y="14" width="7" height="7" fill="#1a1a1a"/>
  <rect x="1" y="15" width="5" height="5" fill="#fff"/>
  <rect x="2" y="16" width="3" height="3" fill="#1a1a1a"/>
  <rect x="8" y="0" width="1" height="1" fill="#1a1a1a"/>
  <rect x="10" y="0" width="1" height="1" fill="#1a1a1a"/>
  <rect x="12" y="0" width="1" height="1" fill="#1a1a1a"/>
  <rect x="8" y="2" width="2" height="1" fill="#1a1a1a"/>
  <rect x="11" y="2" width="1" height="1" fill="#1a1a1a"/>
  <rect x="8" y="4" width="1" height="1" fill="#1a1a1a"/>
  <rect x="10" y="4" width="2" height="1" fill="#1a1a1a"/>
  <rect x="8" y="6" width="1" height="1" fill="#1a1a1a"/>
  <rect x="11" y="6" width="1" height="1" fill="#1a1a1a"/>
  <rect x="0" y="8" width="1" height="1" fill="#1a1a1a"/>
  <rect x="2" y="8" width="3" height="1" fill="#1a1a1a"/>
  <rect x="7" y="8" width="1" height="1" fill="#1a1a1a"/>
  <rect x="9" y="8" width="1" height="1" fill="#1a1a1a"/>
  <rect x="12" y="8" width="1" height="1" fill="#1a1a1a"/>
  <rect x="14" y="8" width="2" height="1" fill="#1a1a1a"/>
  <rect x="17" y="8" width="1" height="1" fill="#1a1a1a"/>
  <rect x="19" y="8" width="2" height="1" fill="#1a1a1a"/>
  <rect x="0" y="10" width="2" height="1" fill="#1a1a1a"/>
  <rect x="4" y="10" width="1" height="1" fill="#1a1a1a"/>
  <rect x="6" y="10" width="1" height="1" fill="#1a1a1a"/>
  <rect x="9" y="10" width="2" height="1" fill="#1a1a1a"/>
  <rect x="13" y="10" width="1" height="1" fill="#1a1a1a"/>
  <rect x="15" y="10" width="3" height="1" fill="#1a1a1a"/>
  <rect x="20" y="10" width="1" height="1" fill="#1a1a1a"/>
  <rect x="1" y="12" width="1" height="1" fill="#1a1a1a"/>
  <rect x="3" y="12" width="2" height="1" fill="#1a1a1a"/>
  <rect x="7" y="12" width="2" height="1" fill="#1a1a1a"/>
  <rect x="11" y="12" width="1" height="1" fill="#1a1a1a"/>
  <rect x="14" y="12" width="1" height="1" fill="#1a1a1a"/>
  <rect x="17" y="12" width="2" height="1" fill="#1a1a1a"/>
  <rect x="8" y="14" width="1" height="1" fill="#1a1a1a"/>
  <rect x="10" y="14" width="2" height="1" fill="#1a1a1a"/>
  <rect x="13" y="14" width="1" height="1" fill="#1a1a1a"/>
  <rect x="8" y="16" width="1" height="1" fill="#1a1a1a"/>
  <rect x="11" y="16" width="1" height="1" fill="#1a1a1a"/>
  <rect x="13" y="16" width="1" height="1" fill="#1a1a1a"/>
  <rect x="8" y="18" width="2" height="1" fill="#1a1a1a"/>
  <rect x="12" y="18" width="1" height="1" fill="#1a1a1a"/>
  <rect x="8" y="20" width="1" height="1" fill="#1a1a1a"/>
  <rect x="11" y="20" width="2" height="1" fill="#1a1a1a"/>
  <rect x="6" y="8" width="1" height="1" fill="#1a1a1a"/>
</svg>"""


# Inline CSS, distilled from the prototype's ``.vendor-page`` styles. Standalone
# (no CDN) and mobile-first: the page uses a centered max-width column on
# wider screens so it still feels like a phone-sized landing page on desktop.
_CSS = """
*, *::before, *::after { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: #1a1208;
  color: #222;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.vendor-page {
  max-width: 420px;
  margin: 0 auto;
  min-height: 100vh;
  background: #faf7f2;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.vendor-hero {
  background: linear-gradient(160deg, #2d1b0e 0%, #5c3317 60%, #8b4513 100%);
  padding: 28px 22px 32px;
  position: relative;
  overflow: hidden;
}
.vendor-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 80% 20%, rgba(255,180,60,0.18) 0%, transparent 60%),
    radial-gradient(ellipse at 10% 90%, rgba(255,100,0,0.12) 0%, transparent 50%);
}
.vendor-hero-inner { position: relative; z-index: 1; }
.vendor-flag {
  font-size: 11px;
  color: rgba(255,255,255,0.55);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.vendor-avatar-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.vendor-avatar {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: linear-gradient(135deg, #c87941, #8b4513);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  border: 2px solid rgba(255,255,255,0.15);
  flex-shrink: 0;
}
.vendor-name {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.3px;
  line-height: 1.2;
}
.vendor-tagline {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  margin-top: 3px;
}
.vendor-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
.vendor-badge {
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.18);
  color: rgba(255,255,255,0.78);
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.vendor-qr-section {
  background: #fff;
  margin: 18px 16px 0;
  border-radius: 20px;
  padding: 22px 18px;
  box-shadow: 0 2px 16px rgba(0,0,0,0.07);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.qr-eyebrow {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #aaa;
  margin-bottom: 14px;
  font-weight: 600;
}
.qr-frame {
  width: 200px;
  height: 200px;
  background: #fff;
  border-radius: 18px;
  border: 2px solid #f0e8dc;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  box-shadow: 0 4px 20px rgba(139,69,19,0.1);
}
.qr-frame svg {
  width: 180px;
  height: 180px;
  display: block;
  shape-rendering: crispEdges;
}
.qr-center-badge {
  position: absolute;
  width: 38px;
  height: 38px;
  background: #fff;
  border-radius: 9px;
  border: 1.5px solid #e8ddd0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.1);
}
.qr-caption {
  margin-top: 14px;
  font-size: 13px;
  color: #888;
  text-align: center;
  line-height: 1.5;
}
.qr-caption strong { color: #333; }
.vendor-how {
  margin: 14px 16px 0;
  background: #fff;
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.05);
}
.how-title {
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #bbb;
  font-weight: 600;
  margin-bottom: 10px;
}
.how-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
}
.how-step + .how-step {
  border-top: 1px solid #f5f0ea;
}
.how-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #8b4513;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}
.how-text {
  font-size: 13px;
  color: #555;
  line-height: 1.4;
  flex: 1;
}
.how-text strong { color: #222; }
.vendor-accepts {
  margin: 14px 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.accepts-label {
  font-size: 10px;
  color: #bbb;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.accepts-pill {
  background: #fff;
  border: 1px solid #e8e0d5;
  border-radius: 10px;
  padding: 5px 10px;
  font-size: 11px;
  color: #666;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.breb-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #e8a020;
  display: inline-block;
}
.vendor-footer {
  margin: 18px 16px 28px;
  text-align: center;
}
.vendor-footer-text {
  font-size: 11px;
  color: #b8b0a4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.felix-logo-small {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: #111;
  color: #fff;
  padding: 3px 9px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
}
"""


# Maps the visual prefix shown next to each accepted-payments pill in the
# prototype to the network name. Bre-B has a custom dot, others use emoji.
_ACCEPTS_PREFIX: dict[str, str] = {
    "Bancolombia": "🏦",
    "Nequi": "💚",
    "Daviplata": "💜",
}


def _render_accepts_pill(name: str) -> str:
    safe = html.escape(name)
    if name == "Bre-B":
        return f'<span class="accepts-pill"><span class="breb-dot"></span> {safe}</span>'
    prefix = _ACCEPTS_PREFIX.get(name, "")
    inner = f"{prefix} {safe}".strip()
    return f'<span class="accepts-pill">{inner}</span>'


def _render_page(vendor: VendorProfile) -> str:
    name = html.escape(vendor.name)
    tagline = html.escape(vendor.tagline)
    flag_line = f"{html.escape(vendor.country_flag)} &nbsp;{html.escape(vendor.city)}, {html.escape(vendor.country)}"
    avatar = html.escape(vendor.avatar_emoji)
    badges_html = "\n".join(
        f'            <div class="vendor-badge">{html.escape(b)}</div>'
        for b in vendor.badges
    )
    accepts_html = "\n".join(
        f"          {_render_accepts_pill(p)}" for p in vendor.accepts
    )
    breb_label = html.escape(vendor.breb_label)
    breb_phone = html.escape(vendor.breb_phone)
    title = f"{vendor.name} · Felix Pay"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#2d1b0e" />
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <main class="vendor-page">
    <section class="vendor-hero">
      <div class="vendor-hero-inner">
        <div class="vendor-flag">{flag_line}</div>
        <div class="vendor-avatar-row">
          <div class="vendor-avatar">{avatar}</div>
          <div class="vendor-name-block">
            <div class="vendor-name">{name}</div>
            <div class="vendor-tagline">{tagline}</div>
          </div>
        </div>
        <div class="vendor-badges">
{badges_html}
        </div>
      </div>
    </section>

    <section class="vendor-qr-section">
      <div class="qr-eyebrow">Escanea para pagar</div>
      <div class="qr-frame">
        {_QR_SVG}
        <div class="qr-center-badge">{avatar}</div>
      </div>
      <div class="qr-caption">
        <strong>{breb_label}</strong><br />
        {breb_phone}
      </div>
    </section>

    <section class="vendor-how">
      <div class="how-title">Cómo pagar desde el exterior</div>
      <div class="how-step">
        <div class="how-num">1</div>
        <div class="how-text">Abre <strong>WhatsApp</strong> y busca el chat de <strong>Felix Pay</strong></div>
      </div>
      <div class="how-step">
        <div class="how-num">2</div>
        <div class="how-text">Toca el ícono de cámara y <strong>escanea este QR</strong></div>
      </div>
      <div class="how-step">
        <div class="how-num">3</div>
        <div class="how-text">Confirma el monto en dólares — Felix convierte a COP</div>
      </div>
    </section>

    <section class="vendor-accepts">
      <span class="accepts-label">Acepta</span>
{accepts_html}
    </section>

    <footer class="vendor-footer">
      <div class="vendor-footer-text">
        Pagos internacionales por
        <span class="felix-logo-small">✦ Felix</span>
      </div>
    </footer>
  </main>
</body>
</html>
"""


@router.get("/v/{slug}", response_class=HTMLResponse)
async def vendor_landing(slug: str) -> HTMLResponse:
    vendor = get_vendor(slug)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return HTMLResponse(content=_render_page(vendor))
