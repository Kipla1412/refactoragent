from __future__ import annotations
import re
import base64
from typing import TYPE_CHECKING, AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType, AgentType
from client.response import StreamEventType
from prompts.system import get_system_prompt

if TYPE_CHECKING:
    from client.llm_client import LLMClient

LANGUAGE_MAP = {
    "en-IN": "English",
    "ta-IN": "Tamil",
    "en": "English",
    "ta": "Tamil",
}


async def translate_text(
    client: "LLMClient",
    text: str,
    target_language: str,
    source_language: str = "en",
) -> str:
    """Translate text between languages using the LLM."""
    if not target_language or not text:
        return text
    if target_language == source_language:
        return text

    source_name = LANGUAGE_MAP.get(source_language, source_language)
    target_name = LANGUAGE_MAP.get(target_language, target_language)

    if source_language in ("en-IN", "en"):
        prompt = (
            f"Translate the following English text to {target_name}. "
            "Return ONLY the translation, no explanations, no quotes, no prefixes."
        )
    elif target_language in ("en-IN", "en"):
        prompt = (
            f"Translate the following {source_name} text to English. "
            "Return ONLY the translation, no explanations, no quotes, no prefixes."
        )
    else:
        prompt = (
            f"Translate the following {source_name} text to {target_name}. "
            "Return ONLY the translation, no explanations, no quotes, no prefixes."
        )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]

    try:
        async for event in client.chat_completion(messages, stream=False):
            if event.type == StreamEventType.MESSAGE_COMPLETE and event.text_delta:
                translated = event.text_delta.content.strip()
                return translated if translated else text
    except Exception as e:
        print(f"Translation error: {e}")

    return text

class VoiceSession:

    def __init__(self, agent, tts):
        self.agent = agent
        self.tts = tts

    async def _translate_to_english(
        self,
        text: str,
        source_language: str,
    ) -> str:
        """Normalize user input to English before it reaches the Core Agent.

        Only Tamil → English is supported. English input passes through
        unchanged.
        """
        if not source_language or source_language in ("en-IN", "en", "", None):
            return text
        if source_language not in ("ta-IN", "ta"):
            return text

        try:
            result = await translate_text(
                self.agent.session.client, text,
                target_language="en", source_language=source_language
            )
        except Exception as e:
            print(f"[TRANSLATE] Tamil → English failed: {e}")
            return text

        print(f"[TRANSLATE] '{text[:50]}...' -> '{result[:50]}...' (ta→en)")
        return result

    async def _translate_to(self, text: str, target_language: str) -> str:
        if not target_language or target_language in ("en-IN", "en", "", None):
            print(f"[TRANSLATE] Skipped — target_language={target_language}")
            return text
        if target_language not in ("ta-IN", "ta"):
            print(f"[TRANSLATE] Unsupported output language '{target_language}' — sending English")
            return text

        result = await translate_text(
            self.agent.session.client, text,
            target_language=target_language, source_language="en"
        )
        print(f"[TRANSLATE] '{text[:50]}...' -> '{result[:50]}...' (lang={target_language})")
        return result

    async def _drain_tts(self):
        """Drain audio until the TTS completion event (single-turn helper)."""
        while True:
            try:
                res = await self.tts.receive_audio()
                if res is None:
                    break
                if hasattr(res, "type") and res.type == "event":
                    event_data = getattr(res, "data", None)
                    if event_data and getattr(event_data, "event_type", None) == "final":
                        break
                if hasattr(res, "data") and res.data and hasattr(res.data, "audio"):
                    if res.data.audio:
                        yield base64.b64decode(res.data.audio)
            except Exception as e:
                print(f"TTS Drain Error: {e}")
                break

    async def process_transcript_to_audio(
        self,
        transcript: str,
        target_language: str = "en-IN",
        source_language: str = "en-IN",
    ):
        print(f"[PROCESS] target_language={target_language} source_language={source_language} transcript='{transcript[:50]}...'")

        # Start each synthesis turn with a fresh TTS connection. Sarvam
        # finalizes the session after a flush+drain, so reusing the same
        # socket for the next turn produces no audio.
        await self.tts.reconnect()

        # Normalize user input to English before it reaches the Core Agent.
        english_transcript = await self._translate_to_english(transcript, source_language)

        buffer = ""
        tts_buffer = ""
        text_buffer = ""

        async for event in self.agent.run(english_transcript):
            if event.type == AgentEventType.TEXT_DELTA:
                token = event.data["content"]
                buffer += token
                tts_buffer += token
                text_buffer += token

                total_len = len(tts_buffer.strip())

                has_punct = bool(re.search(r"[.!?]\s*$", buffer))
                should_process = (
                    (has_punct and total_len >= 15) or
                    (total_len >= 40 and " " in buffer)
                )

                if should_process:
                    text_to_speak = tts_buffer.strip()
                    chunk_text = text_buffer.strip()
                    tts_buffer = ""
                    buffer = ""
                    text_buffer = ""
                    if text_to_speak:
                        if chunk_text:
                            yield {"type": "text", "content": chunk_text + " "}
                        translated = await self._translate_to(text_to_speak, target_language)
                        await self.tts.send_text(translated)
                elif has_punct:
                    buffer = ""

        remaining = tts_buffer.strip() or buffer.strip()
        if remaining:
            chunk_text = text_buffer.strip()
            if chunk_text:
                yield {"type": "text", "content": chunk_text}
            translated = await self._translate_to(remaining, target_language)
            await self.tts.send_text(translated)

        # Flush once at the end, then drain all remaining audio.
        await self.tts.flush()
        async for audio_bytes in self._drain_tts():
            yield {"type": "audio", "content": audio_bytes}

    async def text_to_audio(self, text: str):
        await self.tts.reconnect()
        await self.tts.send_text(text)
        await self.tts.flush()
        async for audio_bytes in self._drain_tts():
            yield audio_bytes
