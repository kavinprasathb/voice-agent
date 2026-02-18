# Voice Agent - Project Configuration

## Overview

Tamil voice agent for automated vendor order confirmation calls. The agent calls vendors, reads out order details in Tamil, and gets accept/reject confirmation.

**Stack:** FastAPI + Exotel (telephony) + Sarvam AI (STT/LLM/TTS)

---

## Deployment

| Setting | Value |
|---------|-------|
| Platform | Google Cloud Run |
| Service Name | `voice-agent` |
| Project | `voice-agent-order-confirm` |
| Region | `asia-south1` |
| Service URL | https://voice-agent-838105683200.asia-south1.run.app |
| Memory | 512Mi |
| Timeout | 300s |
| Container | Python 3.11-slim |
| Port | 8080 |
| GitHub | https://github.com/kavinprasathb/voice-agent |

### Deploy Command

```bash
gcloud run deploy voice-agent \
  --source . \
  --region asia-south1 \
  --project voice-agent-order-confirm \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 300 \
  --concurrency 1 \
  --max-instances 10 \
  --no-session-affinity
```

---

## API Endpoints

### `GET /` - Health Check

Returns `{"status": "ok", "active_calls": <count>}`

### `POST /call` - Trigger Outbound Call

```json
{
  "phone_number": "918072293726",
  "vendor_name": "Kavin",
  "company_name": "Keeggi",
  "order_id": "ORD-2024-7891",
  "items": [
    {"name": "Chicken Biryani", "qty": 2, "price": 250},
    {"name": "Paneer Butter Masala", "qty": 1, "price": 220},
    {"name": "Naan (3 pcs)", "qty": 1, "price": 60}
  ]
}
```

- `phone_number`: with or without 91 prefix
- `company_name`: defaults to "Keeggi"
- Total is auto-calculated server-side (sum of qty * price)
- Item names can be in English or Tamil

**Response:**
```json
{
  "status": "ok",
  "message": "Call initiated to 918072293726",
  "call_sid": "abc123...",
  "order_id": "ORD-2024-7891"
}
```

### `WebSocket /ws` - Exotel Voicebot Stream

Exotel connects here after calling the vendor. Events: `connected`, `start`, `media`, `dtmf`, `flush`, `mark`, `stop`.

---

## Exotel Configuration

| Setting | Value |
|---------|-------|
| Account SID | `easterntradersandmarketingfirm1` |
| Caller ID | `04446972794` |
| App ID | `1179367` |
| API URL | `https://api.exotel.com/v1/Accounts/{SID}/Calls/connect.json` |
| Hangup Method | Close WebSocket (REST API returns 405 for voicebot calls) |

### Call Flow
1. POST `/call` stores order in `pending_orders` dict (keyed by normalized phone - last 10 digits)
2. Exotel API triggers outbound call to vendor
3. Exotel connects back via WebSocket `/ws`
4. "start" event contains `from_number` -> lookup pending order
5. VoiceAgent created with order data
6. Call ends by closing WebSocket -> Exotel advances to Hangup applet

---

## Sarvam AI Configuration

| Setting | Value |
|---------|-------|
| API Key | env: `SARVAM_API_KEY` |
| STT WebSocket | `wss://api.sarvam.ai/speech-to-text/ws` |
| TTS WebSocket | `wss://api.sarvam.ai/text-to-speech/ws` |
| LLM URL | `https://api.sarvam.ai/v1/chat/completions` |

### STT (Speech-to-Text)

| Setting | Value |
|---------|-------|
| Model | `saaras:v3` |
| Language | `ta-IN` (Tamil) |
| Sample Rate | 8000 Hz |
| Codec | `pcm_s16le` |
| VAD Signals | Enabled (`speech_start`, `speech_end`) |
| High VAD Sensitivity | Enabled |
| Flush Signal | Enabled |
| Auto-Reconnect | Up to 3 attempts |

### TTS (Text-to-Speech)

| Setting | Value |
|---------|-------|
| Model | `bulbul:v3` |
| Speaker | `ratan` |
| Language | `ta-IN` |
| Pace | 0.93 |
| Enable Preprocessing | true |
| Min Buffer Size | 30 |
| Max Chunk Length | 150 |

**Telephony mode (real calls):**
| Setting | Value |
|---------|-------|
| Codec | `linear16` |
| Sample Rate | 8000 Hz |

**Browser tester mode:**
| Setting | Value |
|---------|-------|
| Codec | `linear16` |
| Sample Rate | 22050 Hz |

### LLM (Chat Completions)

| Setting | Value |
|---------|-------|
| Model | `sarvam-m` |
| Temperature | 0.3 |
| Max Tokens | 100 |
| Streaming | Supported (with fallback to non-streaming) |
| Think Tag Stripping | `<think>...</think>` tags removed from output |

---

## Agent Timing Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Echo Buffer | 2500 ms | Suppresses mic audio after TTS finishes to prevent echo |
| STT Flush Delay | 2000 ms | Server-side flush if no audio for this duration |
| Silence Timeout | 10 seconds | Wait after audio finishes playing before re-prompting |
| Max Silence Prompts | 2 | Re-prompt attempts before ending call with NO_RESPONSE |
| Call Start Delay | 2 seconds | Wait before saying "ஹலோ" |
| Hello-to-Greeting Gap | 1 second | Pause between "ஹலோ" and full greeting |
| End Call Delay | 5 seconds | Wait after goodbye message before hanging up |

### Playback-Aware Silence Timeout

TTS generates audio **much faster than real-time** (~2s to generate 10s of audio). The silence timeout accounts for this:

1. Track total audio bytes per utterance (`_tts_audio_bytes`)
2. When TTS finishes generating, calculate: `playback_sec = audio_bytes / (sample_rate * 2)`
3. Subtract generation time: `remaining_playback = playback_sec - generation_sec`
4. Wait for remaining playback, THEN start 10s silence timeout
5. Each new TTS completion immediately cancels any previous timeout before sleeping

---

## Echo Suppression

Three layers:

1. **TTS Speaking Guard**: Don't send audio to STT while `tts.is_speaking` is True
2. **Time Buffer**: Don't send audio for 2500ms after TTS finishes (accounts for telephony round-trip)
3. **Transcript Matching**: Reject STT transcripts that match the agent's last spoken text (words > 4 chars)

Additionally:
- Transcripts shorter than 3 characters are ignored (noise artifacts)
- VAD `speech_start` cancels silence timeout (user is responding)

---

## Call Flow & System Prompt

### Greeting Template
```
{vendor_name} சார்... வணக்கம்... நான் {company_name} ரமேஷ் பேசுறேன்...
உங்களுக்கு ஒரு புது ஆர்டர் வந்திருக்கு... Order ID {order_id}...
{items_summary}... டோட்டல் {total_tamil} ரூபாய்...
இத அக்செப்ட் பண்றீங்களா... இல்ல ரிஜெக்ட் பண்றீங்களா?...
சரியா... இல்ல முடியாதா?
```

### LLM Decision Handling

| Vendor Says | Agent Response | Status |
|------------|---------------|--------|
| Accept (ஓகே, சரி, etc.) | Asks confirmation, then "ஆர்டர் accept ஆயிடுச்சு" | `ACCEPTED` |
| Reject (முடியாது, வேண்டாம், etc.) | Asks confirmation, then "ஆர்டர் reject ஆயிடுச்சு" | `REJECTED` |
| Repeat order | Repeats full order details + asks accept/reject | (continues) |
| Busy / call later | "அப்புறம் கால் பண்றேன்" | `CALLBACK_REQUESTED` |
| Unclear | Asks to clarify once, then ends | `UNCLEAR_RESPONSE` |
| Silence (after 2 prompts) | "அப்புறம் ட்ரை பண்றேன்" | `NO_RESPONSE` |

### Call Ending Detection

The agent detects call-ending responses by looking for:
- Exact status keywords: `ACCEPTED`, `REJECTED`, `CALLBACK_REQUESTED`, `NO_RESPONSE`, `UNCLEAR_RESPONSE`
- Tamil closing phrases with "ஆயிடுச்சு" (it's done) + "தேங்க்ஸ்" (thanks)
- Skips double-check questions containing "பண்ணிட்டுமா" or "பண்றீங்களா"

---

## Webhook

| Setting | Value |
|---------|-------|
| URL | `https://n8n.srv932301.hstgr.cloud/webhook/voicebot` |
| Method | POST |

**Payload:**
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

**Possible status values:** `ACCEPTED`, `REJECTED`, `CALLBACK_REQUESTED`, `NO_RESPONSE`, `UNCLEAR_RESPONSE`

---

## Tamil Number Conversion

Amounts are converted to spoken Tamil for natural TTS pronunciation:

| Number | Tamil |
|--------|-------|
| 250 | இருநூற்று ஐம்பது |
| 500 | ஐநூறு |
| 720 | எழுநூற்று இருபது |
| 1000 | ஆயிரம் |
| 1250 | ஆயிரத்து இருநூற்று ஐம்பது |
| 2500 | ரெண்டு ஆயிரத்து ஐநூறு |

Quantities use colloquial Tamil: 1=ஒன்னு, 2=ரெண்டு, 3=மூணு, 4=நாலு, 5=அஞ்சு, etc.

---

## Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI server, API endpoints, WebSocket handler |
| `agent.py` | VoiceAgent orchestrator (STT + LLM + TTS coordination) |
| `config.py` | All configuration, greeting/prompt builders, Tamil number conversion |
| `sarvam_stt.py` | Sarvam STT WebSocket client (Saaras v3 with VAD) |
| `sarvam_tts.py` | Sarvam TTS WebSocket client (Bulbul v3, streaming) |
| `sarvam_llm.py` | Sarvam LLM HTTP client (chat completions, streaming support) |
| `Dockerfile` | Python 3.11-slim container |
| `requirements.txt` | fastapi, uvicorn, websockets, httpx, python-dotenv |

---

## Dependencies

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
websockets==14.1
httpx==0.28.1
python-dotenv==1.0.1
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SARVAM_API_KEY` | Sarvam AI API subscription key |
| `EXOTEL_ACCOUNT_SID` | Exotel account identifier |
| `EXOTEL_API_KEY` | Exotel API key for authentication |
| `EXOTEL_API_TOKEN` | Exotel API token for authentication |

---

## Test Call Command

```bash
curl -s -X POST https://voice-agent-838105683200.asia-south1.run.app/call \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "918072293726",
    "vendor_name": "Kavin",
    "company_name": "Keeggi",
    "order_id": "ORD-2024-7891",
    "items": [
      {"name": "Chicken Biryani", "qty": 2, "price": 250},
      {"name": "Paneer Butter Masala", "qty": 1, "price": 220}
    ]
  }'
```

---

## Key Architecture Notes

- `tts.speak()` is **non-blocking** — sends text to WebSocket and returns immediately. Audio is generated and streamed asynchronously.
- TTS generates audio **much faster than real-time** (~2s to generate 10s of audio). Silence timeouts must account for the remaining playback time.
- `_on_tts_done()` fires when TTS finishes **generating**, NOT when the vendor finishes **hearing** it. Audio bytes are tracked to estimate actual playback duration.
- When chaining multiple speaks (e.g. "ஹலோ" + greeting), each `_on_tts_done` **immediately cancels** any previous timeout before waiting for its own playback to finish.
- Exotel call hangup = close WebSocket. The REST API returns 405 for voicebot calls. Closing the WebSocket makes Exotel advance to the Hangup applet.
- `pending_orders` dict links POST `/call` to WebSocket session, keyed by normalized phone number (last 10 digits).
