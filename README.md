# Voice Agent - Vendor Order Confirmation

Automated Tamil voice agent that calls food vendors to confirm orders. Built with FastAPI, Exotel (telephony), Sarvam AI (STT/TTS), and OpenAI GPT-4o-mini (LLM).

## How It Works

1. Your system sends a POST request with order details
2. Order is stored in Firestore, agent calls the vendor via Exotel
3. Speaks order details in Tamil (items, quantity, variation)
4. Handles accept / reject / modify decisions with confirmation gate
5. Sends result to webhook (n8n or any endpoint)

## Quick Start

### Prerequisites

- Python 3.11+
- Sarvam AI API key (for STT + TTS)
- OpenAI API key (for LLM)
- Exotel account with Voicebot app
- Google Cloud project with Firestore enabled

### Setup

```bash
git clone https://github.com/kavinprasathb/voice-agent.git
cd voice-agent
pip install -r requirements.txt
cp .env.example .env
# Fill in all API keys in .env
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SARVAM_API_KEY` | Sarvam AI API key (STT + TTS) |
| `SARVAM_API_KEYS` | Multiple keys for concurrent calls (comma-separated) |
| `OPENAI_API_KEY` | OpenAI API key (GPT-4o-mini) |
| `EXOTEL_ACCOUNT_SID` | Exotel account SID |
| `EXOTEL_API_KEY` | Exotel API key |
| `EXOTEL_API_TOKEN` | Exotel API token |
| `EXOTEL_PHONE_NUMBER` | Exotel phone number |
| `EXOTEL_APP_ID` | Exotel voicebot app ID |
| `WEBHOOK_URL` | Webhook endpoint for call results |

### Run Locally

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

### Browser Tester

A React app that simulates Exotel WebSocket from the browser for manual testing:

```bash
cd browser-tester && npm install && npm run dev
# Opens at localhost:5173, proxies /ws to :8080
```

### Deploy to Google Cloud Run

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

### Docker

```bash
docker build -t voice-agent .
docker run -p 8080:8080 --env-file .env voice-agent
```

## API

### Trigger a Call

```bash
curl -X POST https://your-service-url/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "91XXXXXXXXXX",
    "vendor_name": "Kavin",
    "company_name": "Keeggi",
    "order_id": "ORD-2024-7891",
    "items": [
      {"name": "Chicken Biryani", "qty": 2, "price": 250, "variation": null},
      {"name": "Paneer Butter Masala", "qty": 1, "price": 220, "variation": null},
      {"name": "Murthaba", "qty": 1, "price": 100, "variation": "small"}
    ]
  }'
```

### Webhook Callback

After the call ends, a POST is sent to the configured webhook:

```json
{
  "order_id": "ORD-2024-7891",
  "vendor_name": "Kavin",
  "company": "Keeggi",
  "total_amount": 720,
  "status": "ACCEPTED",
  "rejection_reason": "",
  "modification_reason": "",
  "call_sid": "abc123..."
}
```

**Possible statuses:** `ACCEPTED`, `REJECTED`, `MODIFIED`, `CALLBACK_REQUESTED`, `NO_RESPONSE`, `UNCLEAR_RESPONSE`

For `REJECTED` and `MODIFIED` statuses, the reason fields contain clear spoken Tamil describing what the vendor said.

## Architecture

```
POST /call ──> Firestore (store order) ──> Exotel API ──> Vendor's Phone
                                                              │
                                                         WebSocket /ws
                                                              │
                                               ┌──────────────┼──────────────┐
                                               │              │              │
                                          Sarvam STT    OpenAI GPT-4o   Sarvam TTS
                                         (saaras:v3)      (mini)       (bulbul:v3)
                                               │              │              │
                                            Vendor's      Decision      Tamil Speech
                                             Speech       Making        Generation
```

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server, REST + WebSocket endpoints, Firestore integration |
| `agent.py` | VoiceAgent orchestrator — STT + LLM + TTS coordination, echo suppression, confirmation gate, noise filtering |
| `config.py` | Configuration, Tamil system prompt, greeting builders, number-to-Tamil conversion |
| `sarvam_stt.py` | Speech-to-Text WebSocket client (Saaras v3 with VAD signals) |
| `sarvam_tts.py` | Text-to-Speech WebSocket client (Bulbul v3, streaming) |
| `sarvam_llm.py` | LLM client — calls OpenAI GPT-4o-mini (legacy filename) |

### Key Features

- **Three call outcomes** — Accept, Reject (with reason), Modify (with reason)
- **Confirmation gate** — Agent always asks vendor to confirm before ending the call
- **Noise filtering** — VAD-based speech duration check (ignores < 200ms noise)
- **Echo suppression** — 3-layer system: TTS playback guard + time buffer + transcript word-overlap detection
- **Two-phase greeting** — Intro first, waits for vendor acknowledgment, then reads order items
- **Playback-aware silence timeout** — Tracks audio duration to avoid re-prompting during playback
- **Tamil number pronunciation** — Converts amounts to spoken Tamil
- **Item variations** — Supports small/medium/large variants per item
- **Multi-key support** — Multiple Sarvam API keys for concurrent calls
- **Firestore state** — Shares order data across Cloud Run containers

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | FastAPI (async) |
| Telephony | Exotel (outbound calls, WebSocket audio) |
| Speech-to-Text | Sarvam AI Saaras v3 (Tamil, 8kHz, VAD-enabled) |
| Text-to-Speech | Sarvam AI Bulbul v3 (Tamil, streaming) |
| LLM | OpenAI GPT-4o-mini |
| State Storage | Google Cloud Firestore |
| Deployment | Google Cloud Run |
| Language | Python 3.11+ |
