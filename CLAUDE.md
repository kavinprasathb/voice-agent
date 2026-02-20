# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An automated Tamil voice agent that calls food vendors to confirm orders. It places outbound calls via Exotel (Indian telephony), speaks Tamil using Sarvam AI TTS, listens with Sarvam AI STT, and decides responses with an LLM (OpenAI GPT-4o-mini). Results are posted to an n8n webhook.

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env   # Fill in API keys; also add OPENAI_API_KEY (not yet in .env.example)
uvicorn main:app --host 0.0.0.0 --port 8080
```

**Browser tester** (simulates Exotel WebSocket from browser for manual testing):
```bash
cd browser-tester && npm install && npm run dev  # localhost:5173, proxies /ws to :8080
```

**Docker:**
```bash
docker build -t voice-agent . && docker run -p 8080:8080 --env-file .env voice-agent
```

**Deploy (Cloud Run):**
```bash
gcloud run deploy voice-agent --source . --region asia-south1 --project voice-agent-order-confirm \
  --allow-unauthenticated --memory 512Mi --timeout 300 --concurrency 1 --max-instances 10 --no-session-affinity
```

There are no automated tests. The `browser-tester/` React app is the manual integration test tool.

## Architecture

### Data Flow

1. `POST /call` receives order JSON → stores in Firestore (keyed by last 10 digits of phone) → triggers Exotel outbound call
2. Exotel connects back via `WebSocket /ws` → "start" event looks up order from Firestore → creates `VoiceAgent`
3. VoiceAgent opens STT + TTS WebSocket connections and LLM client, speaks Tamil greeting
4. Conversation loop: vendor audio → echo suppression → STT → LLM → parse `<speak>/<status>` tags → TTS → audio back to phone
5. Terminal status (ACCEPTED/REJECTED/etc.) → webhook POST → end-confirmation → goodbye → WebSocket close (= Exotel hangup)

### Key Files

- **`main.py`** — FastAPI server: `GET /` health, `POST /call` initiation, `WebSocket /ws` for Exotel audio streaming. Uses Firestore to share pending orders across Cloud Run containers (needed because `--no-session-affinity` may route REST and WebSocket to different containers).
- **`agent.py`** — `VoiceAgent` class (~677 lines): core orchestrator. Manages greeting, echo suppression (3 layers: `tts.is_speaking` flag, 500ms post-TTS buffer, transcript word-overlap detection), playback-aware silence timeouts, rejection-reason deferral, end-confirmation flow, and queued transcript processing.
- **`config.py`** — Environment config, Tamil number conversion (`amount_to_tamil`), greeting builder, LLM system prompt (Tamil, with 7 intent-handling rules and `<speak>/<status>` output format).
- **`sarvam_stt.py`** — `SarvamSTT`: WebSocket client to `api.sarvam.ai` (Saaras v3, Tamil, 8kHz PCM). VAD-enabled with `speech_start`/`speech_end` events. Auto-reconnects up to 3 times.
- **`sarvam_tts.py`** — `SarvamTTS`: WebSocket client (Bulbul v3, Tamil). Non-blocking `speak()`. Two codec modes: `linear16`/8kHz for real calls, higher quality for browser tester (detected by `call_sid.startswith("test-")`).
- **`sarvam_llm.py`** — `SarvamLLM`: despite the name, calls **OpenAI GPT-4o-mini** (migrated from Sarvam's LLM due to malformed output). Non-streaming HTTP completions, strips `<think>` tags. Temperature 0.3, max 200 tokens.

### Critical Design Decisions

- **LLM is OpenAI, not Sarvam** — `sarvam_llm.py` is a legacy filename. Sarvam's model produced truncated XML tags.
- **Firestore for state** — In-memory dict fails with Cloud Run's `--no-session-affinity`. Firestore bridges the REST→WebSocket container gap.
- **WebSocket close = hangup** — Exotel REST API returns 405 for voicebot calls. Closing the WebSocket is the correct hangup mechanism.
- **Non-blocking TTS** — `speak()` returns immediately. Audio byte count estimates remaining phone playback time (TTS generates in ~2s but audio plays for ~10s); silence timeout starts only after estimated playback completes.
- **Rejection deferral** — When LLM sets REJECTED but also asks a question (detected by `?`, `ஏன்`, etc.), the agent waits for the vendor's reason before ending the call.

### Key Timing Constants

| Parameter | Value | Location |
|---|---|---|
| Call start delay | 2s | `agent.py` |
| Hello-to-greeting gap | 1s | `agent.py` |
| Echo buffer after TTS | 500ms | `agent.py` |
| Silence timeout | 7s after playback | `agent.py` |
| Max silence re-prompts | 2 | `agent.py` |
| End call delay | 5s | `agent.py` |

## Required Environment Variables

All in `.env` (see `.env.example`):
- `SARVAM_API_KEY` — Sarvam AI (STT + TTS)
- `EXOTEL_ACCOUNT_SID`, `EXOTEL_API_KEY`, `EXOTEL_API_TOKEN`, `EXOTEL_PHONE_NUMBER`, `EXOTEL_APP_ID` — Exotel telephony
- `WEBHOOK_URL` — n8n webhook endpoint
- `OPENAI_API_KEY` — OpenAI (not yet in `.env.example`, but required)
