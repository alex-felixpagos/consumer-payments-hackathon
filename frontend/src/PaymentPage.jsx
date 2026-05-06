import { useEffect, useMemo, useState } from 'react'
import { paymentsApi } from './api.js'

const initialForm = {
  cardholder_name: '',
  email: '',
  card_number: '',
  expiration: '',
  cvv: '',
}

function formatCurrency(amountCents, currency) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: (currency || 'usd').toUpperCase(),
  }).format((amountCents || 0) / 100)
}

function normalizeCardNumber(value) {
  return value.replace(/\D/g, '').slice(0, 19).replace(/(.{4})/g, '$1 ').trim()
}

function normalizeExpiration(value) {
  const digits = value.replace(/\D/g, '').slice(0, 4)
  if (digits.length <= 2) return digits
  return `${digits.slice(0, 2)}/${digits.slice(2)}`
}

export default function PaymentPage({ paymentId }) {
  const [payment, setPayment] = useState(null)
  const [form, setForm] = useState(initialForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        setLoading(true)
        setError('')
        const record = await paymentsApi.getPayment(paymentId)
        if (!cancelled) setPayment(record)
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [paymentId])

  const amountDisplay = useMemo(
    () => formatCurrency(payment?.amount_cents, payment?.currency),
    [payment],
  )

  const statusText = payment?.status === 'succeeded'
    ? 'Paid'
    : payment?.status === 'failed'
      ? 'Needs retry'
      : payment?.status === 'processing'
        ? 'Processing'
        : 'Secure checkout'

  const handleChange = (field) => (event) => {
    const value = event.target.value
    setForm((current) => ({
      ...current,
      [field]: field === 'card_number'
        ? normalizeCardNumber(value)
        : field === 'expiration'
          ? normalizeExpiration(value)
          : value,
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const updated = await paymentsApi.submitPayment(paymentId, form)
      setPayment(updated)
      if (updated.status === 'failed') {
        setError(updated.error_message || 'The payment failed. Please check the card and try again.')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <main className="payment-shell">
        <section className="payment-card payment-card-centered">
          <div className="spinner payment-spinner" />
          <p>Loading secure payment...</p>
        </section>
      </main>
    )
  }

  if (!payment) {
    return (
      <main className="payment-shell">
        <section className="payment-card payment-card-centered">
          <div className="payment-kicker">Payment unavailable</div>
          <h1>We could not find this payment link.</h1>
          {error && <div className="error">{error}</div>}
        </section>
      </main>
    )
  }

  const paid = payment.status === 'succeeded'

  return (
    <main className="payment-shell">
      <section className="payment-hero">
        <div>
          <div className="payment-kicker">CineBot checkout</div>
          <h1>Complete your booking securely.</h1>
          <p>
            Your seats are almost ready. Enter your card details below and Stripe
            will process the payment in test mode.
          </p>
        </div>
        <div className={`payment-status-pill status-${payment.status}`}>
          {statusText}
        </div>
      </section>

      <section className="payment-layout">
        <aside className="payment-summary">
          <div className="payment-summary-glow" />
          <div className="payment-kicker">Amount due</div>
          <div className="payment-amount">{amountDisplay}</div>
          <div className="payment-summary-line">
            <span>Payment ID</span>
            <strong>{payment.id}</strong>
          </div>
          {payment.movie_title && (
            <div className="payment-summary-line">
              <span>Movie</span>
              <strong>{payment.movie_title}</strong>
            </div>
          )}
          {payment.order_summary && (
            <div className="payment-order-summary">{payment.order_summary}</div>
          )}
          {payment.stripe_payment_intent_id && (
            <div className="payment-summary-line">
              <span>Stripe ref</span>
              <strong>{payment.stripe_payment_intent_id}</strong>
            </div>
          )}
        </aside>

        <form className="payment-card" onSubmit={handleSubmit}>
          <div>
            <div className="payment-kicker">Card details</div>
            <h2>{paid ? 'Payment complete' : 'Pay with credit card'}</h2>
            <p>
              Use Stripe test card <strong>4242 4242 4242 4242</strong>, any
              future expiry, and any CVC.
            </p>
          </div>

          {paid ? (
            <div className="payment-success">
              <h3>You're all set.</h3>
              <p>We received your payment and recorded the confirmation for the bot.</p>
            </div>
          ) : (
            <>
              <label className="payment-field">
                <span>Name on card</span>
                <input
                  value={form.cardholder_name}
                  onChange={handleChange('cardholder_name')}
                  autoComplete="cc-name"
                  placeholder="Alex Rivera"
                />
              </label>

              <label className="payment-field">
                <span>Email for receipt</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={handleChange('email')}
                  autoComplete="email"
                  placeholder="you@example.com"
                />
              </label>

              <label className="payment-field">
                <span>Card number</span>
                <input
                  value={form.card_number}
                  onChange={handleChange('card_number')}
                  inputMode="numeric"
                  autoComplete="cc-number"
                  placeholder="4242 4242 4242 4242"
                  required
                />
              </label>

              <div className="payment-field-grid">
                <label className="payment-field">
                  <span>Expiry</span>
                  <input
                    value={form.expiration}
                    onChange={handleChange('expiration')}
                    inputMode="numeric"
                    autoComplete="cc-exp"
                    placeholder="12/34"
                    required
                  />
                </label>
                <label className="payment-field">
                  <span>CVC</span>
                  <input
                    value={form.cvv}
                    onChange={handleChange('cvv')}
                    inputMode="numeric"
                    autoComplete="cc-csc"
                    placeholder="123"
                    maxLength={4}
                    required
                  />
                </label>
              </div>

              {error && <div className="error">{error}</div>}

              <button className="btn btn-primary payment-submit" type="submit" disabled={submitting}>
                {submitting ? <span className="spinner" /> : null}
                {submitting ? 'Processing...' : `Pay ${amountDisplay}`}
              </button>
            </>
          )}
        </form>
      </section>
    </main>
  )
}
