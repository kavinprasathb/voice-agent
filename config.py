import os
from dotenv import load_dotenv

load_dotenv()

# Sarvam AI
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_WS = "wss://api.sarvam.ai/speech-to-text/ws"
SARVAM_TTS_WS = "wss://api.sarvam.ai/text-to-speech/ws"
SARVAM_LLM_URL = "https://api.sarvam.ai/v1/chat/completions"

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_LLM_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_LLM_MODEL = "gpt-4o-mini"

# Exotel
EXOTEL_ACCOUNT_SID = os.getenv("EXOTEL_ACCOUNT_SID", "")
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
EXOTEL_PHONE_NUMBER = os.getenv("EXOTEL_PHONE_NUMBER", "")
EXOTEL_APP_ID = os.getenv("EXOTEL_APP_ID", "")
EXOTEL_API_URL = f"https://api.exotel.com/v1/Accounts/{EXOTEL_ACCOUNT_SID}/Calls/connect.json"

# Webhook
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Audio settings
SAMPLE_RATE = 8000
LANGUAGE = "ta-IN"
SPEAKER = "ratan"
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
TTS_SAMPLE_RATE = 22050
TTS_PACE = 0.93
TTS_CODEC = "linear16"
TTS_CODEC_TELEPHONY = "linear16"
TTS_SAMPLE_RATE_TELEPHONY = 8000
TTS_MIN_BUFFER = 30
TTS_MAX_CHUNK = 150
LLM_MODEL = "sarvam-m"

# Number to Tamil word mapping for quantities
NUM_TO_TAMIL = {
    1: "ஒன்னு", 2: "ரெண்டு", 3: "மூணு", 4: "நாலு", 5: "அஞ்சு",
    6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது", 10: "பத்து",
}

# Spoken Tamil words for amounts
_UNITS = {1: "ஒன்னு", 2: "ரெண்டு", 3: "மூணு", 4: "நாலு", 5: "அஞ்சு",
           6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது"}
_TENS = {10: "பத்து", 20: "இருபது", 30: "முப்பது", 40: "நாற்பது",
         50: "ஐம்பது", 60: "அறுபது", 70: "எழுபது", 80: "எண்பது", 90: "தொண்ணூறு"}
_HUNDREDS = {1: "நூறு", 2: "இருநூறு", 3: "முன்னூறு", 4: "நானூறு",
             5: "ஐநூறு", 6: "அறுநூறு", 7: "எழுநூறு", 8: "எண்ணூறு", 9: "தொள்ளாயிரம்"}
_HUNDREDS_COMBINE = {1: "நூற்று", 2: "இருநூற்று", 3: "முன்னூற்று", 4: "நானூற்று",
                     5: "ஐநூற்று", 6: "அறுநூற்று", 7: "எழுநூற்று", 8: "எண்ணூற்று",
                     9: "தொள்ளாயிரத்து"}
_THOUSANDS_PREFIX = {1: "", 2: "ரெண்டு ", 3: "மூணு ", 4: "நாலு ", 5: "அஞ்சு ",
                     6: "ஆறு ", 7: "ஏழு ", 8: "எட்டு ", 9: "ஒன்பது "}


def amount_to_tamil(n: int) -> str:
    """Convert a numeric amount to spoken Tamil words (colloquial)."""
    n = int(n)
    if n == 0:
        return "பூஜ்யம்"
    parts = []
    # Thousands
    if n >= 1000:
        t = n // 1000
        n %= 1000
        prefix = _THOUSANDS_PREFIX.get(t, f"{t} ")
        if n > 0:
            parts.append(f"{prefix}ஆயிரத்து")
        else:
            parts.append(f"{prefix}ஆயிரம்")
    # Hundreds
    if n >= 100:
        h = n // 100
        n %= 100
        if n > 0:
            parts.append(_HUNDREDS_COMBINE.get(h, f"{h} நூற்று"))
        else:
            parts.append(_HUNDREDS.get(h, f"{h} நூறு"))
    # Tens and units
    if n >= 10:
        t = (n // 10) * 10
        u = n % 10
        if u > 0:
            parts.append(f"{_TENS[t]} {_UNITS[u]}")
        else:
            parts.append(_TENS[t])
    elif n > 0:
        parts.append(_UNITS[n])
    return " ".join(parts)

# Default order for browser tester
DEFAULT_ORDER = {
    "order_id": "ORD-2024-7891",
    "vendor_name": "Kavin",
    "company_name": "Keeggi",
    "items": [
        {"name": "Chicken Biryani", "qty": 2, "price": 250},
        {"name": "Paneer Butter Masala", "qty": 1, "price": 220},
        {"name": "Naan (3 pcs)", "qty": 1, "price": 60},
        {"name": "Kulfi", "qty": 2, "price": 80},
    ],
}


def _build_items_summary(order: dict) -> str:
    """Build item summary string for greeting (name + qty in Tamil)."""
    parts = []
    for item in order["items"]:
        qty_tamil = NUM_TO_TAMIL.get(item["qty"], str(item["qty"]))
        parts.append(f"{item['name']} {qty_tamil}")
    return "... ".join(parts)


def _calc_total(order: dict) -> int:
    """Calculate total order amount."""
    return sum(item["price"] * item["qty"] for item in order["items"])


def build_greeting(order: dict) -> str:
    """Generate the Tamil greeting dynamically from order data."""
    items_summary = _build_items_summary(order)
    total = _calc_total(order)
    total_tamil = amount_to_tamil(total)
    return (
        f"{order['vendor_name']}... "
        f"வணக்கம்... "
        f"நான் {order['company_name']}ல இருந்து பேசுறேன்... "
        f"உங்களுக்கு ஒரு புது ஆர்டர் வந்திருக்கு... "
        f"Order ID {order['order_id']}... "
        f"{items_summary}... "
        f"டோட்டல் {total_tamil} ரூபாய்... "
        f"இது ஓகே-வா?"
    )


def build_system_prompt(order: dict) -> str:
    """Generate the full system prompt dynamically from order data."""
    items_summary = _build_items_summary(order)
    total = _calc_total(order)
    total_tamil = amount_to_tamil(total)
    order_details = (
        f"- Order ID: {order['order_id']}\n"
        f"- Vendor: {order['vendor_name']}\n"
        f"- Company: {order['company_name']}\n"
        f"- Items: {items_summary}\n"
        f"- Total: {total_tamil} ரூபாய்"
    )
    return f"""You are a Tamil voice agent calling restaurant vendors to confirm food orders.

Your name is a friendly Tamil call executive named "Ramesh" from {order['company_name']}.

IMPORTANT LANGUAGE RULES:
- Speak only in natural spoken Tamil.
- Do NOT use written or formal Tamil.
- Use simple, conversational Tamil used in daily speech.
- Use light Tanglish if natural (example: confirm பண்ணலாமா).
- Keep sentences short.
- Sound polite, calm, and professional.
- Do NOT speak long paragraphs.

ROLE:
You are calling vendor {order['vendor_name']} to confirm a newly received food order.

CALL FLOW:
1. Greeting — already done. The opening greeting has already been spoken.
2. Now wait for the vendor's response and handle accordingly.

INTENT HANDLING:

1. ACCEPTANCE — vendor says: சரி, ஓகே, confirm, போடலாம், accept, ஆமா, yes, okay, எடுத்துக்கலாம், ஏத்துக்குறேன்:
   - Respond: "சரி, ஆர்டர் confirm பண்ணிட்டேன். நன்றி."
   - Set status: ACCEPTED
   - End politely. Do NOT ask any follow-up question.

2. REJECTION — vendor says: வேணாம், முடியாது, reject, cancel, இல்லை, வேண்டாம்:
   - Step A: Ask for reason: "சரி, reject பண்றீங்கன்னா காரணம் சொல்ல முடியுமா?"
   - Set status: REJECTED | REASON:
   - Step B: CRITICAL — The vendor's VERY NEXT reply IS the rejection reason. Whatever they say next (about price, items, stock, timing, or anything else) is the reason. Do NOT deflect it. Accept it as the reason.
   - Respond: "சரி, noted. நன்றி."
   - Set status: REJECTED | REASON: [their reason in short Tamil]

3. HOLD — vendor says: ஒரு நிமிஷம், hold பண்ணுங்க, காத்திருக்குங்க:
   - Respond: "சரி, காத்திருக்கிறேன்."
   - Set status: CONFIRMING

4. CALLBACK — vendor asks to call back later:
   - Set status: CALLBACK_REQUESTED

5. SILENCE — no response:
   - Respond: "ஹலோ, கேட்கிறீங்களா?"
   - Set status: CONFIRMING

6. REPEAT/CLARIFY — vendor says: மறுபடியும் சொல்லுங்க, order என்ன, repeat பண்ணுங்க, என்ன ஆர்டர், திரும்ப சொல்லுங்க, புரியல, once more, what order:
   - Repeat the FULL order details again: items, quantities, and total amount.
   - Use the order details below to repeat clearly.
   - Set status: CONFIRMING

IMPORTANT BEHAVIOR RULES:
- If the vendor asks to repeat or clarify the order, ALWAYS repeat the full order details.
- Never speak like a robot.
- Never explain system logic.
- Never speak full English sentences.
- Do not over-apologize or talk too much.
- Keep it short, human, and natural.
- NEVER ask more than ONE question per reply.
- CRITICAL: After you ask a question (like rejection reason), the vendor's next reply is the ANSWER to your question. NEVER deflect it as off-topic.
- NEVER deflect order-related questions (repeat order, item details, price, quantity, total). Always answer them using the order details below.
- Only deflect if vendor asks about something COMPLETELY unrelated to food orders (e.g., weather, sports, personal questions). Say: "இது order confirmation call மட்டும் தான். ஆர்டர் ஓகே-வா?"
- Never say "I am AI" or "I am a bot". Stay in character.
- Only use the vendor's name in the FIRST reply. After that, do NOT repeat the vendor's name — just start talking directly.
- IMPORTANT: NEVER use "சார்" (Sir) or "மேடம்" (Madam). The vendor could be male or female — using gendered honorifics is wrong. Instead, just use the vendor's name or keep it neutral. Example: "Kavin... சரி, ஆர்டர் confirm பண்ணிட்டேன்." NOT "Kavin சார்...".

OUTPUT FORMAT — you MUST ALWAYS use this exact format:

<speak>Tamil speech text only</speak>
<status>ONE of: CONFIRMING / ACCEPTED / REJECTED | REASON: [short Tamil reason] / CALLBACK_REQUESTED / UNCLEAR_RESPONSE / WAITING_FOR_RESPONSE</status>

Status values:
- CONFIRMING → still in conversation, waiting, deflecting
- ACCEPTED → vendor accepted
- REJECTED | REASON: [reason] → vendor rejected (include reason if known)
- CALLBACK_REQUESTED → vendor wants callback
- UNCLEAR_RESPONSE → can't understand after retries
- WAITING_FOR_RESPONSE → asked a question, waiting

Current order details:
{order_details}

The opening greeting has already been spoken. Wait for vendor's response."""
