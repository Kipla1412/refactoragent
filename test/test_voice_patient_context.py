"""Patient context injected via the voice WebSocket query param.

Clients may connect with ``?patient_context=name = X, age = 23``. When present,
the voice agents treat those demographics as already collected and must not ask
for them again; when absent, nothing is added to the prompt.
"""

from unittest.mock import MagicMock

import pytest

from agent.events import AgentEvent
from customagents.voiceagent.voiceagent import build_patient_context_section
from customagents.voiceagent.voiceintake import VoiceIntakeAgent
from customagents.voiceagent.voiceconsult import VoiceConsultAgent


def test_build_patient_context_section_includes_details():
    section = build_patient_context_section("name = hahsd, age = 23")
    assert "# Known Patient Information" in section
    assert "name = hahsd, age = 23" in section
    assert "Do NOT ask" in section


def test_build_patient_context_section_is_empty_for_blank_input():
    assert build_patient_context_section("") == ""
    assert build_patient_context_section("   ") == ""
    assert build_patient_context_section("[patient_context:]") == ""


def test_build_patient_context_section_unwraps_bracket_form():
    section = build_patient_context_section("[patient_context: name = hahsd, age =23]")
    assert "name = hahsd, age =23" in section
    assert "patient_context:" not in section
    assert "[" not in section.split("information")[-1]


def _fake_session(metadata=None):
    session = MagicMock()
    session.context_manager = MagicMock()
    session.metadata = dict(metadata or {})
    return session


async def _run_once(agent, message="hello"):
    async def fake_loop():
        yield AgentEvent.text_delta("Okay.", agent=agent.agent_type)

    agent._agentic_loop = fake_loop
    return [event async for event in agent.run(message)]


@pytest.mark.asyncio
async def test_intake_prompt_includes_patient_context(config):
    session = _fake_session({"patient_context": "name = hahsd, age = 23"})
    agent = VoiceIntakeAgent(config, session=session)

    await _run_once(agent)

    prompt = session.context_manager.set_system_prompt.call_args[0][0]
    assert "# Known Patient Information" in prompt
    assert "name = hahsd, age = 23" in prompt


@pytest.mark.asyncio
async def test_intake_prompt_omits_section_without_context(config):
    session = _fake_session()
    agent = VoiceIntakeAgent(config, session=session)

    await _run_once(agent)

    prompt = session.context_manager.set_system_prompt.call_args[0][0]
    assert "# Known Patient Information" not in prompt


@pytest.mark.asyncio
async def test_consult_prompt_includes_patient_context(config):
    session = _fake_session({"patient_context": "name = hahsd, age = 23"})
    agent = VoiceConsultAgent(config, session=session)

    await _run_once(agent)

    prompt = session.context_manager.set_system_prompt.call_args[0][0]
    assert "name = hahsd, age = 23" in prompt
