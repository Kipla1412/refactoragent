"""Voice stream robustness: a stalled TTS must not hang a turn, and an
interrupted turn must not leave an unanswered patient message in history.
"""

import asyncio
import base64
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from customagents.voiceagent.voiceagent import (
    VoiceSession,
    _drop_unanswered_user_message,
)


@dataclass
class _Event:
    type: str
    data: object


class _AudioResult:
    def __init__(self, audio):
        self.data = SimpleNamespace(audio=audio)


class _ScriptedTTS:
    def __init__(self, results):
        self._results = list(results)

    async def receive_audio(self):
        if not self._results:
            return None
        return self._results.pop(0)


class _StallingTTS:
    async def receive_audio(self):
        await asyncio.sleep(3600)


async def _collect(agen):
    return [item async for item in agen]


@pytest.mark.asyncio
async def test_drain_tts_yields_audio_and_stops_on_the_final_event():
    payload = base64.b64encode(b"PCMDATA").decode()
    trailing = base64.b64encode(b"SHOULD-NOT-APPEAR").decode()
    tts = _ScriptedTTS([
        _AudioResult(payload),
        _Event(type="event", data=SimpleNamespace(event_type="final")),
        _AudioResult(trailing),
    ])
    session = VoiceSession(agent=None, tts=tts)

    chunks = await _collect(session._drain_tts())

    assert chunks == [b"PCMDATA"]


@pytest.mark.asyncio
async def test_drain_tts_returns_when_the_tts_socket_stalls():
    session = VoiceSession(agent=None, tts=_StallingTTS())
    session.TTS_DRAIN_TIMEOUT_SECONDS = 0.05

    chunks = await asyncio.wait_for(_collect(session._drain_tts()), timeout=1.0)

    assert chunks == []


class _Msg:
    def __init__(self, role):
        self.role = role


class _FakeContextManager:
    def __init__(self, messages):
        self._messages = messages


class _FakeSession:
    def __init__(self, messages):
        self.context_manager = _FakeContextManager(messages)


def _roles(session):
    return [m.role for m in session.context_manager._messages]


def test_drop_unanswered_user_message_removes_a_trailing_user_turn():
    session = _FakeSession([_Msg("assistant"), _Msg("user")])

    _drop_unanswered_user_message(session)

    assert _roles(session) == ["assistant"]


def test_drop_unanswered_user_message_keeps_an_answered_turn():
    session = _FakeSession([_Msg("user"), _Msg("assistant")])

    _drop_unanswered_user_message(session)

    assert _roles(session) == ["user", "assistant"]


def test_drop_unanswered_user_message_tolerates_missing_state():
    _drop_unanswered_user_message(SimpleNamespace())
    _drop_unanswered_user_message(None)
