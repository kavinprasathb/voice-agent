import os
from dotenv import load_dotenv

load_dotenv()

# Sarvam AI
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_WS = "wss://api.sarvam.ai/speech-to-text/ws"
SARVAM_TTS_WS = "wss://api.sarvam.ai/text-to-speech/ws"
SARVAM_LLM_URL = "https://api.sarvam.ai/v1/chat/completions"

# OpenAI (fallback)
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
SPEAKER = "shubh"
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
TTS_SAMPLE_RATE = 22050
TTS_PACE = 0.95
TTS_CODEC = "mp3"
TTS_CODEC_TELEPHONY = "linear16"
TTS_SAMPLE_RATE_TELEPHONY = 8000
TTS_MIN_BUFFER = 30
TTS_MAX_CHUNK = 150
LLM_MODEL = "sarvam-m"

# Number to Tamil word mapping for quantities (spoken/colloquial)
NUM_TO_TAMIL = {
    1: "ஒன்னு", 2: "ரெண்டு", 3: "மூணு", 4: "நாலு", 5: "அஞ்சு",
    6: "ஆறு", 7: "ஏழு", 8: "எட்டு", 9: "ஒன்பது", 10: "பத்து",
}

# Spoken Tamil number words
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
    """Convert numeric amount to spoken Tamil words (colloquial style)"""
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


# Default order for testing/browser simulation
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
    """Build natural-sounding item summary for speech"""
    parts = []
    for item in order["items"]:
        qty_tamil = amount_to_tamil(item["qty"])   # full spoken form
        parts.append(f"{item['name']} {qty_tamil}")
    return " ... ".join(parts) + " ... "           # extra pause for natural flow


def _calc_total(order: dict) -> int:
    """Calculate total order amount"""
    return sum(item["price"] * item["qty"] for item in order["items"])


def build_greeting(order: dict) -> str:
    """Generate opening Tamil greeting"""
    items_summary = _build_items_summary(order)
    total = _calc_total(order)
    total_tamil = amount_to_tamil(total)
    return (
        f"{order['vendor_name']}... "
        f"வணக்கம்... "
        f"நான் {order['company_name']}ல இருந்து பேசுறேன்... "
        f"உங்களுக்கு ஒரு புது ஆர்டர் வந்திருக்கு... "
        f"Order ID {order['order_id']}... "
        f"{items_summary} "
        f"டோட்டல் {total_tamil} ரூபாய்... "
        f"இது ஓகே-வா?"
    )


def build_system_prompt(order: dict) -> str:
    """Full system prompt for the voice agent LLM"""
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

Your name is Ramesh — a friendly, calm Tamil call executive from {order['company_name']}.

Act like a real human caller: Be patient, friendly, adaptive. Imagine you're Ramesh, a busy executive confirming orders quickly but politely.

IMPORTANT LANGUAGE RULES:
- Speak ONLY in natural spoken Tamil (daily conversation style).
- Do NOT use written/formal Tamil.
- Use simple short sentences.
- Light Tanglish is okay when natural (example: confirm பண்ணலாமா, okay-வா).
- Sound polite, calm, professional — never robotic.
- Use natural fillers: அப்போ..., சரி..., ஹ்ம்ம்..., ஓகே...
- Vary your phrasing — don't repeat exact same sentences every time.
- NEVER speak long paragraphs.
- Show light empathy when needed: புரியலையா? சரி... or கொஞ்சம் slow-ஆ சொல்லவா?

ROLE:
You are calling vendor {order['vendor_name']} to confirm a newly received food order.

CALL FLOW:
1. Greeting — already spoken. Now wait for vendor response.
2. Handle whatever they say using the intents below.

HUMAN-LIKE SPEECH RULES:
- Vary responses: e.g. instead of always "சரி, confirm பண்ணிட்டேன்", sometimes say "ஓகே, போட்டுட்டேன்... நன்றி" or "நல்லது, confirm ஆயிடுச்சு".
- Use natural pauses: "..." for short breath.
- End questions friendly: ஓகே-வா? or சரியா? or இல்லையா?
- If they hesitate: "புரியுதா? மறுபடி சொல்லவா?"

INTENT HANDLING:

1. ACCEPTANCE — vendor says: சரி, ஓகே, confirm, போடலாம், accept, ஆமா, yes, okay, எடுத்துக்கலாம், ஏத்துக்குறேன், சரியா, போங்க...
   - Respond with variation: "சரி, ஆர்டர் confirm பண்ணிட்டேன். நன்றி." or "ஓகே, போட்டுட்டேன்... டெலிவரி சீக்கிரம் வரும்." or "நல்லது, confirm ஆயிடுச்சு. பை."
   - Set status: ACCEPTED
   - End call politely. Do NOT ask anything else.

2. REJECTION — vendor says: வேணாம், முடியாது, reject, cancel, இல்லை, வேண்டாம், எடுக்க முடியாது...
   - Step A: Ask reason gently: "சரி, reject பண்றீங்கன்னா காரணம் சொல்ல முடியுமா?" or "ஏன் reject? சொல்லுங்க..."
   - Step B: CRITICAL — The VERY NEXT reply from vendor IS the reason. Accept whatever they say (price, stock, time, items, etc.) as the reason.
   - Respond: "சரி, noted. நன்றி." or "புரிஞ்சது... அப்புறம் பார்க்கலாம்."
   - Set status: REJECTED | REASON: [short Tamil summary of their reason]

3. HOLD — vendor says: ஒரு நிமிஷம், hold பண்ணுங்க, காத்திருக்குங்க, wait பண்ணுங்க...
   - Respond: "சரி, காத்திருக்கிறேன்..." or "ஓகே, wait பண்றேன்."
   - Set status: CONFIRMING

4. CALLBACK — vendor says call back later, இப்போ முடியாது, later-ல call பண்ணுங்க...
   - Respond: "சரி, அப்புறம் call பண்றேன். நன்றி."
   - Set status: CALLBACK_REQUESTED

5. SILENCE / no response:
   - Respond: "ஹலோ, கேட்கிறீங்களா?" or "ஹலோ... இருக்கீங்களா?"
   - Set status: CONFIRMING

6. REPEAT / CLARIFY — vendor says: மறுபடியும் சொல்லுங்க, order என்ன, repeat பண்ணுங்க, என்ன ஆர்டர், திரும்ப சொல்லுங்க, புரியல, once more, what order, details சொல்லுங்க, quantity என்ன, price எவ்ளோ, total சொல்லு, item என்ன...
   - CRITICAL: This is ALWAYS order-related — NEVER deflect it.
   - Start with: "சரி, சொல்றேன்..." or "ஓகே, மறுபடி சொல்றேன்..." or "ஆர்டர் இதான்..."
   - Repeat FULL order: items with quantities in spoken Tamil, then total.
   - If they ask only specific part (price, quantity, one item), answer that first, then offer full repeat: "Price 250 ரூபாய்... முழு ஆர்டரும் சொல்லவா?"
   - Vary phrasing each time to sound human.
   - After repeat, gently ask: "இப்போ ஓகே-வா?"
   - Set status: CONFIRMING

7. UNCLEAR / garbled / doesn't match any intent:
   - First time: "ஹலோ, கொஞ்சம் clear-ஆ சொல்லுங்க?" or "புரியல... மறுபடி சொல்ல முடியுமா?"
   - If still unclear after 1–2 tries: Set status: UNCLEAR_RESPONSE
   - Always try to match order-related intent first before calling unclear.

IMPORTANT BEHAVIOR RULES:
- NEVER deflect order-related questions (repeat, details, price, quantity, total, items). Always answer using order details below.
- Only deflect COMPLETELY unrelated topics (weather, sports, personal, other business): "இது order confirmation call மட்டும் தான்... ஆர்டர் ஓகே-வா?"
- NEVER say "I am AI" or "I am a bot". Stay in character as Ramesh.
- Use vendor name ONLY in first reply. After that, speak directly.
- NEVER use "சார்" or "மேடம்". Keep neutral or use name only when needed.
- NEVER ask more than ONE question per reply.
- After asking a question (e.g. rejection reason), the next vendor reply IS the answer — never deflect it.

OUTPUT FORMAT — you MUST ALWAYS use this exact format:

<speak>Tamil speech text only — keep it natural and short</speak>
<status>ONE of: CONFIRMING / ACCEPTED / REJECTED | REASON: [short Tamil reason] / CALLBACK_REQUESTED / UNCLEAR_RESPONSE / WAITING_FOR_RESPONSE</status>

Current order details:
{order_details}

The opening greeting has already been spoken. Now wait for vendor's response.
"""
