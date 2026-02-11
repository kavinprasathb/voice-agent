import json
import logging

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

import config
from agent import VoiceAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voice Agent - Order Confirmation")

# Active call sessions
sessions: dict[str, VoiceAgent] = {}


@app.get("/")
async def health():
    return {"status": "ok", "active_calls": len(sessions)}


class CallRequest(BaseModel):
    to: str  # Vendor phone number (e.g. "918072293726")


@app.post("/call")
async def trigger_call(req: CallRequest):
    """Trigger an outbound call to a vendor via Exotel."""
    logger.info(f"Triggering call to {req.to}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                config.EXOTEL_API_URL,
                auth=(config.EXOTEL_API_KEY, config.EXOTEL_API_TOKEN),
                data={
                    "From": req.to,
                    "To": req.to,
                    "CallerId": config.EXOTEL_PHONE_NUMBER,
                    "Url": f"http://my.exotel.com/exoml/start/{config.EXOTEL_APP_ID}",
                },
            )
            logger.info(f"Exotel response: {resp.status_code} {resp.text[:300]}")

            if resp.status_code == 200:
                return {"status": "ok", "message": f"Call initiated to {req.to}"}
            else:
                return {"status": "error", "code": resp.status_code, "detail": resp.text[:300]}
    except Exception as e:
        logger.error(f"Failed to trigger call: {e}")
        return {"status": "error", "detail": str(e)}


@app.websocket("/ws")
async def exotel_websocket(ws: WebSocket):
    """Handle Exotel Voicebot WebSocket connection."""
    await ws.accept()
    logger.info("Exotel WebSocket connected")

    agent = None
    stream_sid = None

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            event = data.get("event", "")

            if event == "connected":
                logger.info("Exotel stream: connected")

            elif event == "start":
                start_data = data.get("start", {})
                stream_sid = data.get("stream_sid") or start_data.get("stream_sid", "")
                call_sid = start_data.get("call_sid", "")
                from_number = start_data.get("from", "")
                to_number = start_data.get("to", "")
                media_format = start_data.get("media_format", {})

                logger.info(
                    f"Call started: {call_sid} | from={from_number} to={to_number} "
                    f"| format={media_format} | stream={stream_sid}"
                )

                agent = VoiceAgent(
                    exotel_ws=ws,
                    stream_sid=stream_sid,
                    call_sid=call_sid,
                )
                sessions[stream_sid] = agent
                await agent.start()

            elif event == "media":
                if agent:
                    payload = data.get("media", {}).get("payload", "")
                    if payload:
                        await agent.handle_media(payload)

            elif event == "dtmf":
                if agent:
                    digit = data.get("dtmf", {}).get("digit", "")
                    await agent.handle_dtmf(digit)

            elif event == "flush":
                if agent:
                    await agent.handle_flush()

            elif event == "mark":
                mark_name = data.get("mark", {}).get("name", "")
                logger.info(f"Mark received: {mark_name}")

            elif event == "stop":
                reason = data.get("stop", {}).get("reason", "unknown")
                logger.info(f"Call stopped: reason={reason}")
                break

    except WebSocketDisconnect:
        logger.info("Exotel WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        if agent:
            await agent.stop()
        if stream_sid and stream_sid in sessions:
            del sessions[stream_sid]
        logger.info("Session cleaned up")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
