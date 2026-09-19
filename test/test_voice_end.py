"""Regression tests for end-of-conversation signalling in the voice agents.

The voice intake/consult agents now emit `status_end` (mirroring the text
agents) once the LLM response contains a closing phrase. The WebSocket router
forwards that as `{"type": "status", "status": "end"}`.
"""

from unittest.mock import MagicMock

import pytest

from agent.events import AgentEvent, AgentEventType
from customagents.voiceagent.voiceintake import VoiceIntakeAgent
from customagents.voiceagent.voiceconsult import VoiceConsultAgent
from customagents.voiceagent.voiceintakeprompt import VOICE_INTAKE_PROMPT
from customagents.voiceagent.voiceconsultprompt import VOICE_CONSULT_PROMPT


def test_voice_prompts_do_not_repeat_the_connect_greeting():
    # The greeting is delivered once by the WebSocket router on connect; the
    # agent prompts must not instruct the model to greet again (would double it).
    assert "Hello, I'm your medical intake assistant." not in VOICE_INTAKE_PROMPT
    assert "Hi, I'm your medical assistant." not in VOICE_CONSULT_PROMPT


def _fake_session():
    session = MagicMock()
    session.context_manager = MagicMock()
    session.metadata = {}
    return session


def test_voice_intake_end_patterns_are_detected():
    assert VoiceIntakeAgent._is_end_of_conversation(
        "Thank you. Your intake is complete. This information will be available for your doctor's review."
    )
    assert VoiceIntakeAgent._is_end_of_conversation("THANK YOU. YOUR INTAKE IS COMPLETE.")
    assert not VoiceIntakeAgent._is_end_of_conversation("What is your full name?")
    assert not VoiceIntakeAgent._is_end_of_conversation("")


def test_voice_consult_end_patterns_are_detected():
    assert VoiceConsultAgent._is_end_of_conversation(
        "I recommend an in-person evaluation to determine the cause."
    )
    assert VoiceConsultAgent._is_end_of_conversation("Please go to the emergency department.")
    assert not VoiceConsultAgent._is_end_of_conversation("When did the pain begin?")
    assert not VoiceConsultAgent._is_end_of_conversation("")


@pytest.mark.asyncio
async def test_voice_intake_emits_status_end_on_closing_phrase(config):
    session = _fake_session()
    agent = VoiceIntakeAgent(config, session=session)

    async def fake_loop():
        yield AgentEvent.text_delta("Thank you. Your intake is complete.", agent=agent.agent_type)

    agent._agentic_loop = fake_loop

    events = [event async for event in agent.run("yes, that's correct")]

    assert any(event.type == AgentEventType.STATUS_END for event in events)


@pytest.mark.asyncio
async def test_voice_intake_no_status_end_mid_conversation(config):
    session = _fake_session()
    agent = VoiceIntakeAgent(config, session=session)

    async def fake_loop():
        yield AgentEvent.text_delta("What is your date of birth?", agent=agent.agent_type)

    agent._agentic_loop = fake_loop

    events = [event async for event in agent.run("I have a headache")]

    assert not any(event.type == AgentEventType.STATUS_END for event in events)


@pytest.mark.asyncio
async def test_voice_consult_emits_status_end_on_closing_phrase(config):
    session = _fake_session()
    agent = VoiceConsultAgent(config, session=session)

    async def fake_loop():
        yield AgentEvent.text_delta(
            "I recommend an in-person evaluation within 24 hours.",
            agent=agent.agent_type,
        )

    agent._agentic_loop = fake_loop

    events = [event async for event in agent.run("the pain is getting worse")]

    assert any(event.type == AgentEventType.STATUS_END for event in events)
