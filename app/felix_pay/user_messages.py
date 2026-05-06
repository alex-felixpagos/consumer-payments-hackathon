"""WhatsApp copy constants for Felix Pay (Colombia / Bre-B demo)."""

COLD_START_HINT = (
    "Welcome to Felix Pay. Send a photo of the merchant’s Bre-B QR, or reply *pagar* to start a demo payment."
)

VENDOR_AMOUNT_PROMPT = "How much would you like to send? Reply with an amount, e.g. *10*."

INVALID_AMOUNT_HINT = "I couldn't read that amount. Try typing a number, e.g. *10*."

CURRENCY_PROMPT = "Which currency are you sending?"

TIP_PROMPT = "Add a tip for the merchant?"

TIP_LIST_BUTTON = "Choose tip"

TIP_INVALID_HINT = "Pick one of the tip options below to continue."

#: Rich receipt chat message rendered after a successful confirm.
RECEIPT_CHAT_MESSAGE = (
    "✓ *Payment confirmed*\n"
    "\n"
    "*{vendor_name}*\n"
    "Total: *${total_usd:,.2f} USD* ({total_cop:,} COP)\n"
    "{breakdown}"
    "Rail: {payment_rail} · Settled in seconds\n"
    "New Felix Wallet balance: *${new_balance_usd:,.2f} USD*\n"
    "\n"
    "View full receipt: {receipt_url}"
)

#: Optional sub-tile used inside RECEIPT_CHAT_MESSAGE when a tip was added.
RECEIPT_BREAKDOWN_WITH_TIP = (
    "• Subtotal: ${amount_usd:,.2f} USD ({amount_cop:,} COP)\n"
    "• Tip ({tip_label}): ${tip_usd:,.2f} USD\n"
)

#: One-line vendor location + rail string (single-vendor stub for the hackathon).
STUB_VENDOR_LOCATION = "Bogotá, Colombia · Bre-B via Bancolombia"

WALLET_BALANCE_CARD = (
    "✦ *Felix Wallet*\n"
    "*${balance_usd:,.2f} USD*\n"
    "_Available to spend_"
)

VENDOR_FOUND_CARD = (
    "📍 *Vendor found*\n"
    "*{vendor_name}*\n"
    "_{vendor_location}_\n"
    "\n"
    "{amount_prompt}"
)

PAYMENT_SENT = (
    "Payment confirmed. Your mock receipt is below—no real money moved in this sandbox."
)

PROCESSING_PAYMENT = "Processing payment via Bre-B…"

PAYMENT_CANCELLED = "Payment cancelled."

QR_UNREADABLE = (
    "We could not read a Bre-B payload from that image. Try again with the QR in focus, flat, and well lit."
)

VENDOR_NOTIFY_ES = (
    "Felix Pay (demo): pago simulado por {amount_cop} COP a favor de {vendor_name}."
)
