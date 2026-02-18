# Voice Agent - Vendor Order Confirmation

Automated Tamil voice agent that calls vendors to confirm food orders. Built with FastAPI, Exotel (telephony), and Sarvam AI (STT/LLM/TTS).

## How It Works

1. Your system sends a POST request with order details
2. Agent calls the vendor via Exotel
3. Speaks order details in Tamil (items, quantity, total)
4. Gets vendor's accept/reject decision
5. Sends result to webhook

## Quick Start

### Prerequisites

- Python 3.11+
- Sarvam AI API key
- Exotel account with Voicebot app

### Setup

```bash
git clone https://github.com/kavinprasathb/voice-agent.git
cd voice-agent
pip install -r requirements.txt
cp .env.example .env
# Add your SARVAM_API_KEY to .env
```

### Run Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Deploy to Cloud Run

```bash
gcloud run deploy voice-agent \
  --source . \
  --region asia-south1 \
  --project your-project-id \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --concurrency 1 \
  --max-instances 10 \
  --no-session-affinity
```

## API

### Trigger a Call

```bash
curl -X POST https://your-service-url/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "91+phone number",
    "vendor_name": "Kavin",
    "company_name": "Keeggi",
    "order_id": "ORD-2024-7891",
    "items": [
      {"name": "Chicken Biryani", "qty": 2, "price": 250},
      {"name": "Paneer Butter Masala", "qty": 1, "price": 220}
    ]
  }'
```

**Response:**
```json
{
  "status": "ok",
  "message": "Call initiated to 91+your number",
  "call_sid": "abc123...",
  "order_id": "ORD-2024-7891"
}
```

Total is auto-calculated server-side. Item names can be English or Tamil.

### Webhook Callback

After the call ends, a POST is sent to the configured webhook:

```json
{
  "order_id": "ORD-2024-7891",
  "vendor_name": "Kavin",
  "company": "Keeggi",
  "total_amount": 720,
  "status": "ACCEPTED",
  "call_sid": "abc123..."
}
```

**Possible statuses:** `ACCEPTED`, `REJECTED`, `CALLBACK_REQUESTED`, `NO_RESPONSE`, `UNCLEAR_RESPONSE`

## Architecture

```
POST /call ──> Exotel API ──> Vendor's Phone
                                   │
                              WebSocket /ws
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               Sarvam STT    Sarvam LLM    Sarvam TTS
              (saaras:v3)    (sarvam-m)    (bulbul:v3)
                    │              │              │
                 Vendor's      Decision      Tamil Speech
                  Speech       Making        Generation
```

### Key Components

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server, API endpoints, WebSocket handler |
| `agent.py` | VoiceAgent orchestrator (STT + LLM + TTS coordination) |
| `config.py` | Configuration, greeting/prompt builders, Tamil number conversion |
| `sarvam_stt.py` | Speech-to-Text client (Saaras v3 with VAD) |
| `sarvam_tts.py` | Text-to-Speech client (Bulbul v3, streaming) |
| `sarvam_llm.py` | LLM chat client (streaming + non-streaming) |

### Key Features

- **Dynamic orders** — accepts any order via POST API
- **Tamil number pronunciation** — converts amounts to spoken Tamil (e.g., 720 -> "எழுநூற்று இருபது")
- **Echo suppression** — 3-layer system (TTS guard + time buffer + transcript matching)
- **Playback-aware silence timeout** — tracks audio bytes to estimate real playback duration before re-prompting
- **Auto hangup** — ends call after 2 unanswered re-prompts
- **Webhook integration** — sends order status to n8n/any webhook

## Configuration

See [PROJECT_CONFIG.md](PROJECT_CONFIG.md) for detailed configuration reference.

## Tech Stack

- **FastAPI** — async web framework
- **Exotel** — telephony (outbound calls, WebSocket audio streaming)
- **Sarvam AI** — Tamil STT, LLM, and TTS
- **Google Cloud Run** — serverless deployment
