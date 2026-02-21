# Voice Agent — Development Log

This document records all major changes, bug fixes, architectural decisions, and lessons learned. It serves as context for future development sessions.

---

## Session: Feb 2025 — Rejection Flow Fix + LLM Migration + End Confirmation

### 1. Rejection Reason Collection Fix

**Problem**: When a vendor rejects an order, the LLM correctly asks "ஏன் சார்? ஐட்டம் இல்லையா?" (why?) but simultaneously sets `<status>REJECTED</status>`. The agent treated REJECTED as terminal and immediately ended the call — the vendor never got to give their rejection reason.

**Root Cause**: In `_on_transcript()`, `_extract_terminal_status()` found "REJECTED" and triggered `_end_call()` immediately, even though the LLM had just asked a follow-up question.

**Fix** (in `agent.py`):
- Added `_rejection_pending` and `_rejection_partial_reason` state fields
- Added `_speak_is_question()` helper — detects question markers (`?`, `ஏன்`, `இல்லையா`, `என்ன`, `முடியுமா`, `சொல்லுங்க`)
- Modified terminal status logic: if status is REJECTED **and** speak text is a question → set `_rejection_pending = True`, don't end call, wait for vendor's answer
- When next response comes: if REJECTED again (not a question) or vendor gives reason → end call with the real reason
- Silence timeout: if vendor stays silent after rejection question → end call as REJECTED with partial reason

**Lesson**: When an LLM sets a terminal status but also asks a question in the same response, the code must detect this conflict and defer the terminal action.

**Failed approach**: Tried rewriting Rule 7 in the system prompt to tell the LLM to use `CONFIRMING` status when asking for rejection reason. This backfired — the LLM used CONFIRMING but then never transitioned to REJECTED on the next turn. The call ended as NO_RESPONSE instead. **Conclusion**: Don't fight the LLM's natural behavior — fix it in code instead.

---

### 2. LLM Migration: Sarvam sarvam-m → OpenAI GPT-4o-mini

**Why**: Sarvam's `sarvam-m` model was producing truncated/malformed responses with `<speak>` and `<status>` tags, especially at low token limits.

**Changes** (in `sarvam_llm.py`):
- Changed API URL from `config.SARVAM_LLM_URL` → `config.OPENAI_LLM_URL`
- Changed auth header from `api-subscription-key` → `Authorization: Bearer`
- Changed model from `config.LLM_MODEL` → `config.OPENAI_LLM_MODEL` (gpt-4o-mini)
- `max_tokens` increased from 100 → 200 (Tamil text + XML tags need more tokens)

**Changes** (in `config.py`):
- Added `OPENAI_API_KEY`, `OPENAI_LLM_URL`, `OPENAI_LLM_MODEL`

**Changes** (in `.env`):
- Added `OPENAI_API_KEY`

**Note**: The file is still named `sarvam_llm.py` for backwards compatibility. STT and TTS still use Sarvam AI.

---

### 3. LLM Response Parser Improvements

**Problem**: GPT-4o-mini sometimes returns Tamil text without `<speak>` wrapper tags but with `<status>` tags. The old parser extracted empty `speak_text`.

**Fix** (in `agent.py` `_parse_llm_response()`):
- If no `<speak>` tag but `<status>` exists → extract text before `<status>` as speech
- If no tags at all → treat entire response as speech, use `_detect_status_fallback()`
- Handle missing `</speak>` (truncated responses) → extract everything after `<speak>`
- Always strip leftover XML tags from speak text as final cleanup

**Lesson**: Never trust the LLM to perfectly format its output. Build robust parsing with multiple fallback levels.

---

### 4. max_tokens Increase (100 → 200)

**Problem**: Tamil text in XML tags requires more tokens than English. At 100 tokens, responses were being truncated mid-tag, producing malformed output like `<speak>கவின் சார்... ஆர்டர் confirm பண்ணிட்` (no closing tag).

**Fix**: Increased `max_tokens` to 200 in `sarvam_llm.py`.

**Lesson**: Tamil/non-Latin scripts consume more tokens per word. Always test token limits with actual Tamil responses, not English estimates.

---

### 5. End Confirmation Feature

**Problem**: Agent was ending calls abruptly after terminal status. User wanted the agent to ask "anything else?" before hanging up.

**Implementation** (in `agent.py`):
- Added `_end_confirmation_pending` and `_end_confirmation_status` fields
- Added `_end_confirm_keywords` list for detecting confirmation words
- Added `_is_user_confirming_end()` helper
- Added `_initiate_end_confirmation()` — waits for TTS playback to finish, then asks: "சரி சார், வேற ஏதாவது இருக்கா? இல்லன்னா call cut பண்ணிடலாமா?"
- All terminal status paths now call `_initiate_end_confirmation()` instead of `_end_call()`
- In `_on_transcript()`: if `_end_confirmation_pending` is True, check user's response → if confirming, say bye and end; if not, reset and pass to LLM

**Silence handling**: If user stays silent during end confirmation → timeout fires → end call.

---

### 6. `_webhook_sent` vs `_call_ended` Separation

**Problem**: `_send_webhook()` was setting `_call_ended = True`, which blocked `handle_media()` (no audio to STT) and the silence timeout handler (returned immediately). This broke the end confirmation flow — after webhook was sent, the agent couldn't hear the user's confirmation.

**Fix**:
- `_send_webhook()` now uses `_webhook_sent` flag (only prevents duplicate webhooks)
- `_end_call()` sets `_call_ended = True` (blocks audio processing)
- These are now separate concerns: webhook can be sent while call stays open

**Lesson**: Don't overload a single flag for multiple purposes. Webhook delivery and call lifecycle are independent operations.

---

### 7. TTS Overlap Fix in End Confirmation

**Problem**: End confirmation audio ("வேற ஏதாவது இருக்கா?") was overlapping with the closing message ("ஆர்டர் confirm பண்ணிட்டேன்") because `_speak()` is non-blocking.

**Fix** (in `_initiate_end_confirmation()`):
```python
# Wait for current TTS to finish generating
while self.tts and self.tts.is_speaking:
    await asyncio.sleep(0.1)
# Wait for phone playback to finish
while self._playback_in_progress:
    await asyncio.sleep(0.1)
# Small buffer so user hears the closing message fully
await asyncio.sleep(1)
```

**Lesson**: When chaining TTS messages, must wait for: (1) generation to complete, (2) playback to complete, (3) small buffer. `_speak()` returns immediately — it does NOT mean the user has heard the message.

---

### 8. New System Prompt

Merged a cleaner system prompt from `Voice agent Suggestion/System Prompt.txt` with the required technical format. Key elements preserved:
- `<speak>` and `<status>` tag format
- Dynamic order details injection via `build_system_prompt()`
- All status values (CONFIRMING, ACCEPTED, REJECTED, etc.)
- Character: "Ramesh" from the company, polite Tamil-speaking call executive
- Rule: Start every reply with vendor's name for fastest TTS playback

---

### 9. Client-Side Acceptance Detection

**Existing feature** (not changed in this session, but documented):
- `_acceptance_keywords` list checks if vendor clearly said "ஓகே", "சரி", etc.
- If detected, skips LLM entirely → picks random acceptance closing → sends webhook
- Prevents LLM from over-thinking clear acceptance signals

---

## Session: Feb 21, 2026 — Key Pool, Two-Phase Greeting, Variation Support, Browser Tester Overhaul

### 1. API Key Pool for Concurrent Calls

**Problem**: With 3 Sarvam API keys, only 1 concurrent call worked. Calls 2 & 3 failed because each call opens 2 WebSockets (STT + TTS) to Sarvam, which limits concurrent connections per key.

**Fix**: Created `sarvam_key_pool.py` — an `asyncio.Queue`-based FIFO pool.
- `checkout(timeout=30s)` — waits for an available key
- `release(key)` — synchronous `put_nowait` for safe use in `finally` blocks
- `status()` — exposes pool metrics for health endpoint
- Max queue size of 10 to prevent unbounded waiting

**Changes across files**:
- `config.py`: Parse `SARVAM_API_KEYS` (comma-separated) with backward compat to single `SARVAM_API_KEY`
- `sarvam_stt.py` + `sarvam_tts.py`: Accept `api_key` parameter, use per-call key instead of global
- `agent.py`: Accept `api_key` + `on_key_release` callback, release key in `stop()`
- `main.py`: Initialize pool on startup, checkout/release in WebSocket handler with `nonlocal` closure

**Deployment**: Cloud Run `--concurrency` raised from 1 to 10. `SARVAM_API_KEYS` env var added with 3 keys.

**Finding**: Concurrent call testing revealed that **Exotel** (not Sarvam) is the bottleneck — only 1 WebSocket stream per voicebot app ID. Key pool works correctly; Exotel limits need investigation.

---

### 2. Two-Phase Greeting

**Problem**: Agent spoke a long monologue (name + company + all items + total), overwhelming the vendor.

**Fix**: Split greeting into two phases:
- Phase 1 (intro): "Kavin... வணக்கம்... நான் Keeggiல இருந்து பேசுறேன்... புது ஆர்டர் வந்திருக்கு"
- Wait for vendor acknowledgment (any speech) or timeout (remaining playback + 1.5s)
- Phase 2 (items): "Order ID... items... இது ஓகே-வா?"

**Implementation** (`agent.py`):
- `_greeting_phase` flag (0=none, 1=intro)
- `_intro_ack_event` (`asyncio.Event`) — set by any transcript during phase 1
- Phase 1 intercept in `_on_transcript()` before the short-text filter
- 15s fallback timeout (`_greeting_fallback_timeout`) if `_on_tts_done` never fires

**Config changes**: `build_greeting_intro()` and `build_greeting_items()` split from `build_greeting()`.

---

### 3. End Confirmation Replaced with Pre-Decision Confirmation

**Problem**: The "anything else?" end confirmation was unnatural.

**Fix**: Removed end confirmation entirely. Instead, the LLM now asks for confirmation BEFORE marking as ACCEPTED/REJECTED:
- Vendor says "okay" → Agent: "ஆர்டர் accept பண்றீங்க, correct-ஆ?" (status: CONFIRMING)
- Vendor confirms → Agent: "confirm பண்ணிட்டேன். நன்றி." (status: ACCEPTED → end)
- Same pattern for REJECTED (asks reason first, then confirms the rejection)

This is purely a system prompt change — `CONFIRMING` keeps the conversation going, only final `ACCEPTED`/`REJECTED` triggers webhook + call end.

**Removed**: `_end_confirmation_pending`, `_end_confirmation_status`, `_end_confirm_keywords`, `_is_user_confirming_end()`, `_initiate_end_confirmation()`. Replaced with `_finish_call()`.

---

### 4. Variation Support + Remove Price

**Problem**: Items needed variation info (small/medium/large), and price should not be spoken.

**Changes**:
- `main.py`: `OrderItem` model — added `variation: Optional[str] = None`, included in `/call` item dicts
- `config.py` `_build_items_summary()`: includes variation when not null (e.g., "Murthaba small ஒன்னு"), no price
- `config.py` `build_greeting_items()`: removed total price ("டோட்டல் X ரூபாய்")
- `config.py` `build_system_prompt()`: removed price/total from order details, instructed LLM to never mention price
- Browser tester: added variation dropdown per item, sends `null` when empty

---

### 5. Browser Tester Audio — MP3 Playback

**Problem**: Browser tester expected raw PCM but server sent MP3 for browser calls. Multiple iterations:
1. Set browser TTS to `linear16` → fixed glitch but sounded "robotic"
2. Reverted to MP3 + `new Audio()` blob → blocked by browser autoplay policy
3. Final fix: `AudioContext.decodeAudioData()` + `BufferSource`

**Final implementation** (`useVoiceAgent.js`):
- Accumulates MP3 chunks in array
- Flushes on `tts_done` server event (or 500ms gap fallback)
- Decodes via `ctx.decodeAudioData()` → queues `AudioBuffer`s → plays via `BufferSource`
- `AudioContext` created during `connect()` (user gesture) to avoid Chrome suspension
- Fallback: if MP3 decode fails, tries raw PCM interpretation

**Server-side** (`agent.py`): sends `{"event": "tts_done"}` from `_on_tts_done()`.

---

### 6. Browser Echo Suppression

**Problem**: Browser plays agent's voice through speakers, mic picks it up, STT transcribes it as user speech ("ம்.", garbage text).

**Root cause**: Server-side echo suppression blocks mic during TTS *generation*, but browser plays audio *after* generation (buffered). Mic is unblocked while audio still plays.

**Fix** (browser-side in `useVoiceAgent.js`):
- `agentSpeakingRef` flag — `true` from first media chunk arrival to playback finish
- Mic processor skips sending when `agentSpeakingRef.current === true`
- Reset on playback queue empty or `clearAudioQueue()`

---

### 7. Browser Playback Duration Estimation

**Problem**: Silence timeout fired while vendor was still listening to order items. Two issues:
1. MP3 bytes / (sample_rate * 2) assumes raw PCM → underestimates MP3 playback by ~3x
2. Browser buffers all audio → subtracting generation time gives `remaining ≈ 0`

**Fix** (`agent.py` `_on_tts_done()`):
- Browser tester: `playback_sec = bytes / 24000` (MP3 ~192kbps estimate)
- Browser tester: `remaining = playback_sec` (full duration, no generation subtraction)
- Real telephony: unchanged (`bytes / (sample_rate * 2)`, subtract generation time)

---

### 8. Browser Order Data Pass-Through

**Problem**: Browser tester always used `config.DEFAULT_ORDER` regardless of what was entered in the UI.

**Root cause**: `main.py` WebSocket handler read `call_sid`, `from`, `to` from `start_data` but never read `vendor_name`, `order_id`, `items` which the browser sends.

**Fix** (`main.py`): After Firestore lookup fails, check `start_data.get("order_id")` and construct `order_data` from the browser-provided fields.

---

### 9. Tamil Number Pronunciation Contractions

**Problem**: Formal written Tamil numbers (நூற்று, நாற்பது) sound unnatural in speech.

**Fix** (`config.py`):
- `_TENS[40]`: நாற்பது → நாப்பது
- `_HUNDREDS_COMBINE`: all நூற்று → நூத்தி (e.g., இருநூற்று → இருநூத்தி)

---

### 10. Firestore Made Optional

**Problem**: `google-cloud-firestore` not installed locally, causing `ModuleNotFoundError`.

**Fix** (`main.py`): Wrapped import in try/except, set `db = None` on failure. All `db.` calls guarded with `if db:`.

---

## Architecture Overview (Current State)

```
Exotel (telephony) ←→ WebSocket ←→ FastAPI (main.py)
                                         ↓
                                    SarvamKeyPool (sarvam_key_pool.py)
                                         ↓
                                    VoiceAgent (agent.py)
                                    ├── SarvamSTT  (sarvam_stt.py)  — Sarvam saaras:v3
                                    ├── SarvamTTS  (sarvam_tts.py)  — Sarvam bulbul:v3
                                    └── SarvamLLM  (sarvam_llm.py)  — OpenAI gpt-4o-mini

Browser Tester (localhost:5173) ←→ WebSocket /ws ←→ Same FastAPI server
```

### Key State Machine

```
Call Start
  → checkout API key from pool
  → Phase 1: intro greeting ("name + company + new order")
  → wait for vendor ack or timeout (remaining + 1.5s)
  → Phase 2: read order items + "okay?"
  → wait for vendor response (silence timeout running)
  → vendor speaks → STT → LLM → TTS → loop
  → LLM returns ACCEPTED/REJECTED:
      → LLM asks confirmation first (status: CONFIRMING)
      → vendor confirms → LLM sets ACCEPTED/REJECTED
      → send webhook → _finish_call → goodbye → _end_call
  → rejection flow:
      → LLM asks reason (CONFIRMING) → vendor gives reason
      → LLM repeats + confirms (CONFIRMING) → vendor confirms
      → REJECTED with reason → webhook → end
  → release API key back to pool
```

### Important Timing

| Event | Duration |
|-------|----------|
| Call start delay | 2s |
| Hello-to-intro gap | 1s |
| Intro response wait | remaining_playback + 1.5s |
| Echo buffer after TTS | 500ms |
| Silence timeout | 7s after playback ends |
| Max silence re-prompts | 2 before ending as NO_RESPONSE |
| End call delay (goodbye) | 5s |
| Browser MP3 byte rate | ~24KB/s estimate |

---

## Files Modified

| File | Purpose |
|------|---------|
| `agent.py` | Main orchestrator — rejection pending, end confirmation, parser fixes |
| `sarvam_llm.py` | LLM client — switched to OpenAI gpt-4o-mini |
| `config.py` | Added OpenAI config, system prompt, Tamil number mappings |
| `.env` | Added OPENAI_API_KEY |

## Common Debugging Tips

1. **Agent saying raw tags** ("speak", "status"): Check `_parse_llm_response()` — likely LLM response is malformed or truncated. Increase `max_tokens` or improve tag stripping.
2. **Call ending too early on rejection**: Check `_rejection_pending` logic — the agent should wait if it's asking a question.
3. **Audio not captured after webhook**: Check that `_send_webhook` uses `_webhook_sent` flag, NOT `_call_ended`.
4. **TTS messages overlapping**: Ensure `_initiate_end_confirmation` waits for `tts.is_speaking` and `_playback_in_progress` to clear.
5. **Echo of agent's own speech**: Check echo suppression timing — `ECHO_BUFFER_MS`, `_playback_in_progress`, `_tts_last_finished`.
