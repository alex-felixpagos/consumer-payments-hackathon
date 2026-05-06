********
## Remittance Concierge Hackathon Plan

### One-liner
An AI-first WhatsApp concierge for Felix Pago that helps users send money to Latin America with more confidence by recommending the best Felix transfer flow, delivery method, and timing based on the user's situation.

### Core idea
Users should be able to text naturally, like:

> "I want to send $300 to my mom in Colombia."

The concierge understands the intent, asks only the missing questions, and returns a Felix-only recommendation:

> "Got it. Does your mom prefer receiving it in her bank account, mobile wallet, or cash pickup?"

Once it has enough information, it gives a clear answer:

> "Felix bank deposit looks like the right fit. She would receive about COP 1,170,000 after estimated fees. Since she can wait 1-2 days and the USD/COP rate has been slightly improving, waiting until tomorrow may help, but the expected difference is small."

### Important constraints
- This is fixed for Felix Pago, so the concierge should not compare against Wise, Remitly, Western Union, or any other company.
- The experience should feel conversational and WhatsApp-native, not like a form or dashboard.
- The target region is Latin America, not only Guatemala.
- The hackathon version should be buildable in about 2.5 hours.
- The product is a decision layer before the transfer, not a real money movement system.

### MVP scope
Build a simulated WhatsApp chat where the user can ask to send money to a LatAm country. The assistant should collect enough information to recommend the best Felix transfer flow.

Must have:
- WhatsApp-style chat interface
- Natural language transfer intent, for example amount and country extraction
- Felix-only recommendation
- Support for 3-5 LatAm corridors with mock data
- Delivery method guidance: cash pickup, bank deposit, or mobile wallet where available
- Urgency handling: today, 1-2 days, flexible
- FX trend advice: send now vs wait
- Final transfer summary with estimated received amount, fee, speed, and next step

Do not build:
- Real WhatsApp/Twilio integration
- Real Felix transaction creation
- Authentication or KYC
- Payment processing
- Competitor comparisons
- Complex FX forecasting
- Full compliance workflow

### Suggested tech stack
Fastest path:
- Streamlit chat UI using `st.chat_message` and `st.chat_input`
- Python recommendation logic
- Mock Felix corridor data in a dictionary or JSON file
- Optional OpenAI call for conversational polish
- Rule-based extraction as a fallback if the LLM is too slow to wire up

The key technical principle: use deterministic code for calculations and recommendations, and use the LLM for conversation, extraction, and explanation.

### Mock data
Create mock Felix corridor data for Mexico, Guatemala, Colombia, El Salvador, and Honduras.

Each country should include:
- Local currency
- Estimated Felix FX rate
- Estimated Felix fee
- Available delivery methods
- Typical speed by delivery method
- 5-day FX rate history

Example structure:

```python
felix_corridors = {
    "Mexico": {
        "currency": "MXN",
        "fx_rate": 16.9,
        "fee_usd": 2.99,
        "methods": ["cash_pickup", "bank_deposit"],
        "typical_speed": {
            "cash_pickup": "minutes",
            "bank_deposit": "same day"
        },
        "fx_history": [16.75, 16.8, 16.82, 16.88, 16.9]
    },
    "Colombia": {
        "currency": "COP",
        "fx_rate": 3900,
        "fee_usd": 4.99,
        "methods": ["bank_deposit", "mobile_wallet"],
        "typical_speed": {
            "bank_deposit": "same day",
            "mobile_wallet": "minutes"
        },
        "fx_history": [3840, 3865, 3880, 3890, 3900]
    }
}
```

### Conversation state
Maintain a simple state object:

```python
conversation_state = {
    "amount_usd": None,
    "destination_country": None,
    "delivery_method": None,
    "urgency": None,
    "recipient": None
}
```

The assistant should:
1. Extract known information from each user message.
2. Identify the next missing field.
3. Ask one question at a time.
4. Once the required fields are present, generate the recommendation.

Required fields:
- Amount in USD
- Destination country
- Delivery method preference
- Urgency

### Recommendation logic
The recommendation should choose the best Felix flow, not the best provider.

Simple calculation:

```text
estimated_received = (amount_usd - fee_usd) * fx_rate
```

Decision rules:
- If the user needs money today and cash pickup is available, recommend cash pickup.
- If the recipient has a bank account and urgency is not immediate, recommend bank deposit.
- If mobile wallet is available and the user wants convenience/speed, recommend mobile wallet.
- If the preferred method is unavailable in the selected country, recommend the closest available Felix method.
- If the user is flexible and FX is improving, suggest waiting 24-48 hours.
- If the user is urgent or FX is weakening, suggest sending now.

### FX advisor
Keep the FX intelligence simple but useful.

The assistant should explain:
- Whether the dollar is stronger, weaker, or stable versus the destination currency
- The percent change over the last few days
- The estimated impact on the user's transfer amount
- Whether the user should send now or wait

Example:

> "The dollar has strengthened about 0.6% against MXN over the last few days. On a $300 transfer, waiting could change the payout by roughly MXN 25-35. Since your recipient needs the money today, I would send now."

### AI system prompt

```text
You are Felix Remittance Concierge, a WhatsApp-native assistant helping US users send money to Latin America through Felix Pago.

Your job is to have a short, natural conversation. Ask one question at a time. Do not compare Felix to competitors. Recommend only Felix-supported delivery methods.

Collect:
- amount in USD
- destination country
- recipient delivery preference
- urgency

Once enough information is available, provide:
- recommended Felix delivery method
- estimated recipient amount
- estimated speed
- FX timing advice
- simple next step

Use warm, concise WhatsApp-style language. Avoid financial jargon. Always say estimates should be verified before sending.
```

### Demo flow

User:

> "I need to send 200 bucks to my sister in Mexico."

Bot:

> "Got it, $200 to Mexico. How would your sister like to receive it: cash pickup or bank deposit?"

User:

> "Cash, she needs it today."

Bot:

> "Felix cash pickup looks like the right fit. She can typically pick it up within minutes. After Felix's estimated fee and today's exchange rate, she would receive about MXN 3,330."
>
> "FX-wise, USD/MXN has been mostly stable this week. Since she needs it today, I would send now instead of waiting. The expected benefit of waiting is probably small."
>
> "Want me to prepare this Felix transfer summary?"

### 2.5 hour build plan

#### 0:00-0:20 - Define demo dataset and golden path
- Create mock Felix data for Mexico, Guatemala, Colombia, El Salvador, and Honduras.
- Pick one strong demo path: "Send $200 to sister in Mexico, cash pickup, today."
- Write 2-3 backup scenarios in case judges ask for variety.

#### 0:20-0:55 - Build WhatsApp-style chat UI
- Use Streamlit chat components.
- Add message history.
- Keep the layout narrow and mobile-like.
- Add Felix/WhatsApp-inspired styling if time allows.

#### 0:55-1:35 - Build conversation state and extraction
- Extract amount from text.
- Extract destination country from text.
- Extract urgency from words like "today", "now", "tomorrow", "not urgent", "can wait".
- Extract delivery method from words like "cash", "pickup", "bank", "deposit", "wallet".
- Ask one follow-up question for the next missing field.

#### 1:35-2:00 - Add recommendation and FX advisor
- Calculate estimated received amount.
- Recommend delivery method.
- Analyze FX trend from mock 5-day history.
- Generate send now vs wait message.

#### 2:00-2:20 - Polish the assistant
- Make messages short, warm, and WhatsApp-like.
- Add final transfer summary.
- Add disclaimer: "Estimates only. Please verify the final rate and fee before sending."
- Add one optional "prepare transfer" call to action.

#### 2:20-2:30 - Rehearse pitch
Pitch:

> "Felix is already built around WhatsApp. This turns remittance decision-making into a conversational AI flow: the user texts naturally, the assistant understands intent, asks only what is missing, and recommends the best Felix transfer path with FX confidence."

### Judging angle
The strongest part is not the calculator. It is the AI-native WhatsApp experience.

Position it as:

> "A conversational decision layer for Felix Pago that reduces uncertainty before the transfer."
	



