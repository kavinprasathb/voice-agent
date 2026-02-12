import json
import logging
import re
from typing import Callable, List, Dict, Optional

import httpx

import config

logger = logging.getLogger(__name__)

# Sentence boundary pattern for Tamil/Tanglish
_SENTENCE_END = re.compile(r'[.!?।](?:\s|$)|\.{3}')
# Strip <think>...</think> tags from LLM output
_THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL)


class SarvamLLM:
    """Chat completion client for Sarvam AI with streaming support."""

    def __init__(self, system_prompt: Optional[str] = None):
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."}
        ]
        self.client = httpx.AsyncClient(timeout=30.0)

    async def chat(self, user_message: str) -> str:
        """Send user message and get assistant response (non-streaming)."""
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
                    "max_tokens": 100,
                },
            )
            response.raise_for_status()
            data = response.json()

            assistant_message = data["choices"][0]["message"]["content"]
            # Strip <think>...</think> reasoning tags if present
            assistant_message = _THINK_PATTERN.sub('', assistant_message).strip()
            self.messages.append({"role": "assistant", "content": assistant_message})

            logger.info(f"LLM response: {assistant_message[:80]}...")
            return assistant_message

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return "மன்னிக்கவும், ஒரு தொழில்நுட்ப சிக்கல் ஏற்பட்டுள்ளது."

    async def chat_stream(self, user_message: str, on_sentence: Optional[Callable] = None) -> str:
        """Stream LLM response, calling on_sentence for each sentence boundary."""
        self.messages.append({"role": "user", "content": user_message})

        full_response = ""
        buffer = ""

        try:
            async with self.client.stream(
                "POST",
                config.SARVAM_LLM_URL,
                headers={
                    "api-subscription-key": config.SARVAM_API_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.LLM_MODEL,
                    "messages": self.messages,
                    "temperature": 0.3,
                    "max_tokens": 100,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if not token:
                            continue

                        full_response += token
                        buffer += token

                        # Check for sentence boundary in buffer
                        if on_sentence and _SENTENCE_END.search(buffer):
                            sentence = buffer.strip()
                            if sentence:
                                logger.info(f"LLM sentence: {sentence[:60]}...")
                                await on_sentence(sentence)
                            buffer = ""
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue

            # Flush remaining buffer
            if on_sentence and buffer.strip():
                logger.info(f"LLM final chunk: {buffer.strip()[:60]}...")
                await on_sentence(buffer.strip())

            # Strip <think>...</think> reasoning tags if present
            full_response = _THINK_PATTERN.sub('', full_response).strip()
            self.messages.append({"role": "assistant", "content": full_response})
            logger.info(f"LLM full response: {full_response[:80]}...")
            return full_response

        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            # Fallback to non-streaming
            if not full_response:
                self.messages.pop()  # Remove the user message we added
                return await self.chat(user_message)
            # If we got partial response, use it
            self.messages.append({"role": "assistant", "content": full_response})
            return full_response

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
