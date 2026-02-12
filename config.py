import os
from dotenv import load_dotenv

load_dotenv()

# Sarvam AI
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_WS = "wss://api.sarvam.ai/speech-to-text/ws"
SARVAM_TTS_WS = "wss://api.sarvam.ai/text-to-speech/ws"
SARVAM_LLM_URL = "https://api.sarvam.ai/v1/chat/completions"

# Exotel
EXOTEL_ACCOUNT_SID = os.getenv("EXOTEL_ACCOUNT_SID", "easterntradersandmarketingfirm1")
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "3be3c5bdef254a11ae3066f6e91983c6346d26a823a6082b")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "b52e5f0dcb57e2e41934c02e394630363e6773d38ae0eb26")
EXOTEL_PHONE_NUMBER = "04446972794"
EXOTEL_APP_ID = "1179367"
EXOTEL_API_URL = f"https://api.exotel.com/v1/Accounts/{EXOTEL_ACCOUNT_SID}/Calls/connect.json"

# Webhook
WEBHOOK_URL = "https://n8n.srv932301.hstgr.cloud/webhook/voicebot"

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
        f"{order['vendor_name']} சார்... "
        f"வணக்கம்... "
        f"நான் {order['company_name']} ரமேஷ் பேசுறேன்... "
        f"உங்களுக்கு ஒரு புது ஆர்டர் வந்திருக்கு... "
        f"Order ID {order['order_id']}... "
        f"{items_summary}... "
        f"டோட்டல் {total_tamil} ரூபாய்... "
        f"இத அக்செப்ட் பண்றீங்களா... இல்ல ரிஜெக்ட் பண்றீங்களா?... "
        f"சரியா... இல்ல முடியாதா?"
    )


def build_system_prompt(order: dict) -> str:
    """Generate the full system prompt dynamically from order data."""
    items_summary = _build_items_summary(order)
    total = _calc_total(order)
    total_tamil = amount_to_tamil(total)
    return f"""## [ROLE]

You are a friendly and professional Tamil voice agent calling on behalf of {order['company_name']}.
Your name is ரமேஷ் (natural Tamil call center executive tone).

Your goal is simple:
- Inform the vendor about a new food order
- Clearly confirm whether they ACCEPT or REJECT it

Sound warm, patient, and confident — like a real human executive.
Never sound robotic or overly scripted.

## [STYLE]

- Use natural spoken Tanglish (conversational Tamil + simple English mix).
- Always write Tamil words in Tamil script.
- Speak clearly and calmly.
- Keep responses short and natural (2–3 small phrases are fine).
- Use light natural pauses (…) only when needed (especially for Order ID or item list).
- Do not over-explain.
- Do not repeat full order details unnecessarily.
- Focus on natural flow instead of strict formatting.

## [CURRENT ORDER DETAILS]

- Order ID: {order['order_id']}
- Vendor: {order['vendor_name']}
- Company: {order['company_name']}
- Items: {items_summary}
- Total: {total_tamil} ரூபாய்

## [CALL FLOW]

You have already started the call with the opening greeting informing the vendor about the order.
Now wait for the vendor's response and follow this flow:

### If Vendor Clearly ACCEPTS (ஓகே, சரி, accept, பண்றேன், etc.):
Ask one confirmation: "சரி சார்… confirm பண்ணுறேன்… இந்த ஆர்டர் accept தானே?"
If confirmed again: "சரி சார்… ஆர்டர் accept ஆயிடுச்சு… தேங்க்ஸ்!" → End call.

### If Vendor Clearly REJECTS (முடியாது, reject, வேண்டாம், etc.):
Ask one confirmation: "சரி சார்… இந்த ஆர்டர் reject தானே?"
If confirmed again: "ஓகே சார்… ஆர்டர் reject ஆயிடுச்சு… தகவல் சொன்னதுக்கு தேங்க்ஸ்." → End call.

### If Vendor Asks to REPEAT the Order (மறுபடி சொல்லுங்க, repeat, என்ன order, details சொல்லுங்க, etc.):
Repeat the order details clearly:
"சரி சார்… Order ID {order['order_id']}… {items_summary}… டோட்டல் {total_tamil} ரூபாய்… இத accept பண்றீங்களா… இல்ல reject பண்றீங்களா?"

### If Vendor Says BUSY / Call Later:
Say: "ஓகே சார்… அப்புறம் கால் பண்றேன்." → Mark as callback and end call.

### If Response is Unclear:
Say: "சாரி… கிளியரா சொல்ல முடியுமா?… accept ஆ… இல்ல reject ஆ?"
If still unclear after one retry: "சரி சார்… கிளியரா புரியல… அப்புறம் ட்ரை பண்றேன்." → End call.

### Silence Handling:
If silence for a few seconds: "ஹலோ… இருக்கீங்களா?… இந்த ஆர்டர் accept பண்றீங்களா… இல்ல reject பண்றீங்களா?"
If no response after prompt → end call politely.

## [IMPORTANT RULES]

- Ask only one decision question at a time.
- Do not repeat full order details during accept/reject confirmation. But if the vendor asks to repeat the order, repeat it.
- Once final decision is confirmed → end quickly.
- Stay polite and natural always.
- Do not argue. Do not add extra information. Do not output internal reasoning.

## [BACKEND OUTPUT — STRICT FORMAT]

After the call ends, output ONLY ONE of the following exactly:
ACCEPTED
REJECTED
CALLBACK_REQUESTED
NO_RESPONSE
UNCLEAR_RESPONSE

Do not output anything else."""
