import logging
from typing import List, Dict

import httpx

import config

logger = logging.getLogger(__name__)


class SarvamLLM:
    """Chat completion client for Sarvam AI."""

    def __init__(self):
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": config.SYSTEM_PROMPT}
        ]
        self.client = httpx.AsyncClient(timeout=30.0)

    async def chat(self, user_message: str) -> str:
        """Send user message and get assistant response."""
        self.messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.post(
                config.SARVAM_LLM_URL,
                headers={
                    "api-subscription-key": config.SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": self.messages,
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
            )
            response.raise_for_status()
            data = response.json()

            assistant_message = data["choices"][0]["message"]["content"]
            self.messages.append({"role": "assistant", "content": assistant_message})

            logger.info(f"LLM response: {assistant_message[:80]}...")
            return assistant_message

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "மன்னிக்கவும், ஒரு தொழில்நுட்ப சிக்கல் ஏற்பட்டுள்ளது. மீண்டும் முயற்சிக்கவும்."

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
