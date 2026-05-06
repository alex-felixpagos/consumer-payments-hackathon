"""WhatsApp copy constants for Felix Pay (Colombia / Bre-B demo)."""

COLD_START_HINT = (
    "Welcome to Felix Pay. Send a photo of the merchant’s Bre-B QR, or reply *pagar* to start a demo payment."
)

VENDOR_AMOUNT_PROMPT = (
    "How much COP do you want to send to *{vendor_name}*? Tap a quick amount below or type a number."
)

FX_PREVIEW = (
    "FX preview (indicative):\n"
    "• You send: ~{debit_fx} {from_currency}\n"
    "• They receive: ~{amount_cop} COP\n"
    "• Rate: 1 {from_currency} ≈ {rate_cop} COP"
)

PAYMENT_SENT = (
    "Payment confirmed. Your mock receipt is below—no real money moved in this sandbox."
)

PAYMENT_CANCELLED = (
    "Okay, we cancelled that payment. Send *pagar* or a Bre-B QR photo whenever you want to try again."
)

QR_UNREADABLE = (
    "We could not read a Bre-B payload from that image. Try again with the QR in focus, flat, and well lit."
)

VENDOR_NOTIFY_ES = (
    "Felix Pay (demo): pago simulado por {amount_cop} COP a favor de {vendor_name}."
)
