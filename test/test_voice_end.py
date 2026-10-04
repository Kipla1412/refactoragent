"""Regression tests for end-of-conversation signalling in the voice agents.

The voice intake/consult agents now emit `status_end` (mirroring the text
agents) once the LLM response contains a closing phrase. The WebSocket router
forwards that as `{"type": "status", "status": "end"}`.
"""

from unittest.mock import MagicMock

import pytest

from agent.events import AgentEvent, AgentEventType, AgentType
from customagents.voiceagent.voiceagent import VoiceSession
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
    assert VoiceConsultAgent._is_end_of_conversation("That completes our consultation.")
    assert VoiceConsultAgent._is_end_of_conversation(
        "Please call emergency services or go to the nearest emergency department."
    )
    assert not VoiceConsultAgent._is_end_of_conversation("When did the pain begin?")
    assert not VoiceConsultAgent._is_end_of_conversation("")


def test_end_patterns_tolerate_paraphrasing():
    # The closings must be recognised regardless of punctuation/casing variants.
    assert VoiceIntakeAgent._is_end_of_conversation("Thank you, your intake is now complete.")
    assert VoiceIntakeAgent._is_end_of_conversation("Your intake has been completed.")
    assert VoiceIntakeAgent._is_end_of_conversation("That completes your intake!")
    assert VoiceConsultAgent._is_end_of_conversation("This concludes our consultation.")
    assert VoiceConsultAgent._is_end_of_conversation(
        "That completes our consultation. Take care."
    )
    assert VoiceConsultAgent._is_end_of_conversation("Our consultation is now complete.")


def test_mid_conversation_questions_do_not_end_the_call():
    """Ordinary wording must never terminate the session.

    These all previously matched: the bare infinitive "complete your intake"
    appears in routine questions, and "in person evaluation" / "see a doctor"
    appear in normal advice.
    """
    assert not VoiceIntakeAgent._is_end_of_conversation(
        "Hello again. To help complete your intake, are you currently taking any "
        "medications for your fever, headache, cough, or any other reason?"
    )
    assert not VoiceIntakeAgent._is_end_of_conversation(
        "Before we finish, I need a few more details. Are you taking any medicines?"
    )
    assert not VoiceIntakeAgent._is_end_of_conversation(
        "Since you are ending the conversation, please note that the intake is "
        "not yet complete."
    )
    assert not VoiceConsultAgent._is_end_of_conversation(
        "To complete our consultation, I need a few more details."
    )
    assert not VoiceConsultAgent._is_end_of_conversation(
        "I recommend an in-person evaluation to determine the exact cause."
    )
    assert not VoiceConsultAgent._is_end_of_conversation(
        "Do you see a doctor regularly for this?"
    )


def test_consult_prompt_instructs_a_matching_closing():
    # The prompt's closing acknowledgment must contain a phrase the detector
    # recognises, otherwise the consultation can never signal its end.
    closing = "That completes our consultation."
    assert closing in VOICE_CONSULT_PROMPT
    assert VoiceConsultAgent._is_end_of_conversation(closing)


class _FakeTTS:
    def __init__(self):
        self.sent = []
        self.flushed = False

    async def reconnect(self):
        pass

    async def send_text(self, text):
        self.sent.append(text)

    async def flush(self):
        self.flushed = True

    async def receive_audio(self):
        return None


class _FakeAgent:
    def __init__(self, events):
        self._events = events
        self.session = MagicMock()

    async def run(self, transcript):
        for event in self._events:
            yield event


@pytest.mark.asyncio
async def test_voice_session_emits_end_frame_on_status_end():
    # End-to-end: agent STATUS_END -> VoiceSession -> {"type": "status", "status": "end"}
    fake_agent = _FakeAgent([
        AgentEvent.text_delta("That completes our consultation.", AgentType.VOICE_CONSULT),
        AgentEvent.status_end(AgentType.VOICE_CONSULT),
    ])
    session = VoiceSession(agent=fake_agent, tts=_FakeTTS())

    frames = [
        frame
        async for frame in session.process_transcript_to_audio(
            "thank you doctor", target_language="en-IN", source_language="en-IN"
        )
    ]

    assert any(
        frame.get("type") == "status" and frame.get("status") == "end" for frame in frames
    )


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
            "That completes our consultation. Take care.",
            agent=agent.agent_type,
        )

    agent._agentic_loop = fake_loop

    events = [event async for event in agent.run("the pain is getting worse")]

    assert any(event.type == AgentEventType.STATUS_END for event in events)
