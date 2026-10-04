"""Chat agents: precise end detection, and a fresh session once a chat ends.

Two behaviours are covered:

1. The text agents must only treat the mandated closing marker as the end of the
   conversation. Loose phrases ("take care", "in-person evaluation",
   "see a doctor") appear in ordinary advice and used to end chats mid-thread.
2. When the agent does signal the end, the chat endpoints drop the session so
   the next conversation starts fresh instead of inheriting the finished one.
"""

from unittest.mock import MagicMock

import logging

import pytest

from agent.events import AgentEvent, AgentType
from customagents.consultagent.consultagent import ConsultingAgent
from customagents.consultagent.consultprompt import CONSULT_PROMPT
from customagents.previsitagent.intakeagent import IntakeAgent

import api.routers.consult as consult_router


# --------------------------------------------------------------------------
# End detection
# --------------------------------------------------------------------------

def test_text_consult_detects_only_the_mandated_closing():
    assert ConsultingAgent._is_end_of_conversation("That completes our consultation.")
    assert ConsultingAgent._is_end_of_conversation("Our consultation is complete.")

    assert not ConsultingAgent._is_end_of_conversation(
        "An in-person evaluation may be needed to determine the exact cause."
    )
    assert not ConsultingAgent._is_end_of_conversation("Take care of your health and rest well.")
    assert not ConsultingAgent._is_end_of_conversation("You should see a doctor if it worsens.")


def test_text_intake_detects_the_mandated_closing():
    assert IntakeAgent._is_end_of_conversation(
        "Thank you. Your intake is complete. "
        "This information will be available for your doctor's review."
    )
    assert not IntakeAgent._is_end_of_conversation(
        "Before we finish, I need a few more details."
    )


def test_text_consult_prompt_mandates_a_detected_marker():
    assert "completes our consultation" in CONSULT_PROMPT
    assert ConsultingAgent._is_end_of_conversation("completes our consultation")


# --------------------------------------------------------------------------
# Session lifecycle
# --------------------------------------------------------------------------

class _FakeAgent:
    def __init__(self, events):
        self._events = events

    async def run(self, message):
        for event in self._events:
            yield event


class _FakeSessionManager:
    def __init__(self):
        self.requested = []
        self.deleted = []

    async def get_session(self, user_id, config, session_id=None):
        self.requested.append(session_id)
        return MagicMock(session_id=session_id or "default")

    async def delete_session(self, user_id, session_id):
        self.deleted.append((user_id, session_id))


def _request(manager):
    request = MagicMock()
    request.state.user = {"sub": "user-1"}
    request.app.state.config = None
    request.app.state.session_manager = manager
    return request


async def _drain(response):
    async for _ in response.body_iterator:
        pass


def _patch_agent(monkeypatch, events):
    monkeypatch.setattr(
        consult_router.AgentFactory, "create", lambda *a, **k: _FakeAgent(events)
    )


@pytest.mark.asyncio
async def test_consult_end_drops_session_so_next_chat_is_fresh(monkeypatch):
    _patch_agent(monkeypatch, [
        AgentEvent.text_delta("That completes our consultation.", AgentType.CONSULT),
        AgentEvent.status_end(AgentType.CONSULT),
    ])
    manager = _FakeSessionManager()

    response = await consult_router.consult_api(
        _request(manager), consult_router.ChatRequest(message="thanks")
    )
    await _drain(response)

    assert manager.deleted == [("user-1", "default")]


@pytest.mark.asyncio
async def test_consult_without_end_keeps_the_session(monkeypatch):
    _patch_agent(monkeypatch, [
        AgentEvent.text_delta("When did the pain first begin?", AgentType.CONSULT),
    ])
    manager = _FakeSessionManager()

    response = await consult_router.consult_api(
        _request(manager), consult_router.ChatRequest(message="my knee hurts")
    )
    await _drain(response)

    assert manager.deleted == []


@pytest.mark.asyncio
async def test_pinned_session_id_is_honoured_and_dropped(monkeypatch):
    _patch_agent(monkeypatch, [
        AgentEvent.status_end(AgentType.CONSULT),
    ])
    manager = _FakeSessionManager()

    response = await consult_router.consult_api(
        _request(manager), consult_router.ChatRequest(message="bye", session_id="abc")
    )
    await _drain(response)

    assert manager.requested == ["abc"]
    assert manager.deleted == [("user-1", "abc")]


@pytest.mark.asyncio
async def test_intake_end_drops_session(monkeypatch):
    _patch_agent(monkeypatch, [
        AgentEvent.text_delta(
            "Thank you. Your intake is complete.", AgentType.INTAKE
        ),
        AgentEvent.status_end(AgentType.INTAKE),
    ])
    manager = _FakeSessionManager()

    response = await consult_router.intake_stream(
        _request(manager), consult_router.ChatRequest(message="yes that's correct")
    )
    await _drain(response)

    assert manager.deleted == [("user-1", "default")]


@pytest.mark.asyncio
async def test_consult_logs_requested_and_resolved_session_id(monkeypatch, caplog):
    _patch_agent(monkeypatch, [
        AgentEvent.text_delta("When did it start?", AgentType.CONSULT),
    ])
    manager = _FakeSessionManager()

    with caplog.at_level(logging.INFO, logger="api.routers.consult"):
        response = await consult_router.consult_api(
            _request(manager),
            consult_router.ChatRequest(message="hello", session_id="abc"),
        )
        await _drain(response)

    assert "requested_session_id=abc" in caplog.text
    assert "resolved_session_id=abc" in caplog.text


@pytest.mark.asyncio
async def test_consult_logs_when_the_end_drops_the_session(monkeypatch, caplog):
    _patch_agent(monkeypatch, [AgentEvent.status_end(AgentType.CONSULT)])
    manager = _FakeSessionManager()

    with caplog.at_level(logging.INFO, logger="api.routers.consult"):
        response = await consult_router.consult_api(
            _request(manager), consult_router.ChatRequest(message="bye")
        )
        await _drain(response)

    assert "conversation ended" in caplog.text
    assert "dropping session_id=default" in caplog.text
