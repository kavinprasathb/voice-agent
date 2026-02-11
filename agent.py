import asyncio
import json
import logging
from typing import Optional

import httpx
from starlette.websockets import WebSocket

import config
from sarvam_stt import SarvamSTT
from sarvam_tts import SarvamTTS
from sarvam_llm import SarvamLLM

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Orchestrates a single call session: Exotel <-> STT <-> LLM <-> TTS."""

    # Echo suppression: don't send audio to STT for this long after TTS finishes
    ECHO_BUFFER_MS = 2500
    # Server-side flush: if no audio sent to STT for this long, flush
    FLUSH_AFTER_MS = 2000

    def __init__(self, exotel_ws: WebSocket, stream_sid: str, call_sid: str):
        self.exotel_ws = exotel_ws
        self.stream_sid = stream_sid
        self.call_sid = call_sid

        self.stt: Optional[SarvamSTT] = None
        self.tts: Optional[SarvamTTS] = None
        self.llm: Optional[SarvamLLM] = None

        self._processing = False
        self._audio_chunks_received = 0
        self._audio_chunks_sent_to_stt = 0
        self._call_ended = False

        # Echo suppression tracking
        self._tts_last_finished = 0  # timestamp when TTS last finished speaking
        self._last_audio_sent_time = 0  # timestamp of last audio chunk sent to STT
        self._flush_task: Optional[asyncio.Task] = None

        # Final status keywords the LLM outputs
        self._status_keywords = [
            "ACCEPTED", "REJECTED", "CALLBACK_REQUESTED",
            "NO_RESPONSE", "UNCLEAR_RESPONSE",
        ]

    async def _send_log(self, msg: str):
        """Send a log event back to the browser."""
        try:
            await self.exotel_ws.send_json({
                "event": "log",
                "message": msg,
            })
        except Exception:
            pass

    async def start(self):
        """Initialize all AI services and send greeting."""
        await self._send_log("Starting voice agent...")

        self.llm = SarvamLLM()
        self.stt = SarvamSTT(on_transcript=self._on_transcript, on_log=self._send_log)
        self.tts = SarvamTTS(on_audio=self._on_tts_audio, on_log=self._send_log, on_done=self._on_tts_done)

        await self.stt.connect()
        await self.tts.connect()

        await self._send_log(f"Agent ready for call {self.call_sid}")

        # Wait 2 seconds before speaking, then say hello first
        await asyncio.sleep(2)
        await self._speak("ஹலோ")
        await asyncio.sleep(1)

        # Send full greeting
        await self._speak(config.GREETING)

    async def handle_media(self, payload: str):
        """Handle incoming audio from Exotel — forward to STT with echo suppression."""
        self._audio_chunks_received += 1
        now = asyncio.get_event_loop().time() * 1000  # ms

        # Log first chunk
        if self._audio_chunks_received == 1:
            await self._send_log(f"Receiving mic audio... (STT connected={self.stt._connected if self.stt else 'N/A'})")

        # ECHO SUPPRESSION: Don't send audio to STT while agent is speaking
        # or for ECHO_BUFFER_MS after agent finishes speaking
        if self.tts and self.tts.is_speaking:
            return
        if self._tts_last_finished > 0 and (now - self._tts_last_finished) < self.ECHO_BUFFER_MS:
            return

        # Don't send if call already ended
        if self._call_ended:
            return

        if self.stt and self.stt._connected:
            sent = await self.stt.send_audio(payload)
            if sent:
                self._audio_chunks_sent_to_stt += 1
                self._last_audio_sent_time = now

                # Schedule a server-side flush after silence
                self._schedule_flush()

        if self._audio_chunks_received % 100 == 0:
            await self._send_log(f"Audio: {self._audio_chunks_received} recv, {self._audio_chunks_sent_to_stt} sent to STT")

    def _schedule_flush(self):
        """Schedule a flush after FLUSH_AFTER_MS of no new audio to STT."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = asyncio.create_task(self._delayed_flush())

    async def _delayed_flush(self):
        """Wait for silence then flush STT."""
        await asyncio.sleep(self.FLUSH_AFTER_MS / 1000)
        # Only flush if no new audio was sent during the wait
        now = asyncio.get_event_loop().time() * 1000
        if (now - self._last_audio_sent_time) >= (self.FLUSH_AFTER_MS - 100):
            if self.stt and self.stt._connected and not self._call_ended:
                await self._send_log("Server-side silence detected — flushing STT")
                await self.stt.flush()

    async def handle_flush(self):
        """Handle flush signal from browser — user stopped speaking."""
        await self._send_log("User stopped speaking — flushing STT...")
        if self.stt:
            await self.stt.flush()

    async def handle_dtmf(self, digit: str):
        await self._send_log(f"DTMF: {digit}")

    async def _on_transcript(self, text: str, is_final: bool):
        """Called when STT produces a transcript."""
        text = text.strip()

        # Ignore empty transcripts
        if not text:
            return

        # Ignore very short transcripts (noise/echo artifacts)
        if len(text) < 3:
            await self._send_log(f"Ignored short transcript: '{text}'")
            return

        await self._send_log(f"You said: {text}")

        # Don't process while agent is speaking (echo prevention)
        if self.tts and self.tts.is_speaking:
            await self._send_log("Ignoring — agent is still speaking")
            return

        if not is_final:
            return

        if self._processing:
            await self._send_log("Still processing previous message...")
            return

        self._processing = True
        try:
            await self._send_log(f"Thinking...")
            response = await self.llm.chat(text)
            await self._send_log(f"Agent: {response}")

            # Speak the response first
            await self._speak(response)

            # Check if the response indicates call is ending
            status = self._detect_call_ending(response)
            if status:
                await self._send_webhook(status)
                await self._end_call(status)
        except Exception as e:
            await self._send_log(f"Error: {e}")
        finally:
            self._processing = False

    def _detect_call_ending(self, response: str) -> Optional[str]:
        """Detect if the agent's FINAL response indicates the call is ending.
        Only triggers on confirmed closing lines (with ஆயிடுச்சு + தேங்க்ஸ்),
        NOT on double-check questions (பண்ணிட்டுமா??).
        """
        lower = response.lower()

        # Skip double-check questions — they contain "?" and are asking, not confirming
        if "பண்ணிட்டுமா" in lower or "பண்றீங்களா" in lower:
            return None

        # Check for exact status keywords first (if LLM outputs them)
        upper = response.upper().strip()
        for keyword in self._status_keywords:
            if keyword in upper:
                return keyword

        # Only match FINAL confirmation lines (ஆயிடுச்சு = "it's done")
        # These must have both the decision + thanks/closing
        has_thanks = any(s in lower for s in ["தேங்க்ஸ்", "thanks", "நன்றி"])

        accept_finals = [
            "accept ஆயிடுச்சு", "அக்செப்ட் ஆயிடுச்சு",
            "accept பண்ணிட்டாங்க", "accept பண்ணிட்டோம்",
            "order accepted", "உறுதிப்படுத்தப்பட்டது",
        ]
        reject_finals = [
            "reject ஆயிடுச்சு", "ரிஜெக்ட் ஆயிடுச்சு",
            "reject பண்ணிட்டாங்க", "reject பண்ணிட்டோம்",
            "order rejected",
        ]
        callback_signals = [
            "அப்புறம் கால் பண்றேன்", "அப்புறம் ட்ரை பண்றேன்",
            "அப்புறம் கால்", "later பண்றேன்",
        ]
        unclear_signals = [
            "கிளியரா சொல்ல முடியல", "அப்புறம் ட்ரை",
        ]

        for signal in accept_finals:
            if signal in lower and has_thanks:
                return "ACCEPTED"
        for signal in reject_finals:
            if signal in lower and has_thanks:
                return "REJECTED"
        for signal in callback_signals:
            if signal in lower:
                return "CALLBACK_REQUESTED"
        for signal in unclear_signals:
            if signal in lower:
                return "UNCLEAR_RESPONSE"

        return None

    async def _send_webhook(self, status: str):
        """Send order confirmation result to n8n webhook."""
        if self._call_ended:
            return
        self._call_ended = True

        payload = {
            "order_id": config.TEST_ORDER["order_id"],
            "vendor_name": config.TEST_ORDER["vendor_name"],
            "company": config.TEST_ORDER["company_name"],
            "total_amount": config.TOTAL_AMOUNT,
            "status": status,
            "call_sid": self.call_sid,
        }

        await self._send_log(f"Sending webhook: Status={status}")
        logger.info(f"Sending webhook to {config.WEBHOOK_URL}: {payload}")

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(config.WEBHOOK_URL, json=payload)
                await self._send_log(f"Webhook sent: {resp.status_code}")
                logger.info(f"Webhook response: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            await self._send_log(f"Webhook error: {e}")
            logger.error(f"Webhook error: {e}")

    async def _end_call(self, status: str):
        """Notify the browser of the result and end the call."""
        status_labels = {
            "ACCEPTED": "Order Accepted",
            "REJECTED": "Order Rejected",
            "CALLBACK_REQUESTED": "Callback Requested",
            "NO_RESPONSE": "No Response",
            "UNCLEAR_RESPONSE": "Unclear Response",
        }
        label = status_labels.get(status, status)

        # Wait a moment for TTS to finish playing
        await asyncio.sleep(3)

        try:
            await self.exotel_ws.send_json({
                "event": "end_call",
                "status": status,
                "message": f"Call ended — {label}",
            })
        except Exception:
            pass

        await self._send_log(f"Call ended — {label}")
        logger.info(f"Call ended for {self.call_sid}: {status}")

    async def _on_tts_done(self):
        """Called when TTS finishes speaking — mark timestamp for echo suppression."""
        self._tts_last_finished = asyncio.get_event_loop().time() * 1000
        await self._send_log("TTS done — echo buffer active")

    async def _speak(self, text: str):
        if self.tts:
            await self.tts.speak(text)

    async def _on_tts_audio(self, audio_base64: str):
        try:
            await self.exotel_ws.send_json({
                "event": "media",
                "stream_sid": self.stream_sid,
                "media": {
                    "payload": audio_base64,
                }
            })
        except Exception as e:
            logger.error(f"Error sending audio: {e}")

    async def _interrupt(self):
        await self._send_log("Interrupted by customer")
        if self.tts:
            await self.tts.stop()
        try:
            await self.exotel_ws.send_json({
                "event": "clear",
                "stream_sid": self.stream_sid,
            })
        except Exception:
            pass

    async def stop(self):
        logger.info(f"Agent stopping for call {self.call_sid}")
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        if self.stt:
            await self.stt.close()
        if self.tts:
            await self.tts.close()
        if self.llm:
            await self.llm.close()
        logger.info(f"Agent stopped for call {self.call_sid}")
