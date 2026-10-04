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


def test_intake_prompt_does_not_unconditionally_demand_full_name():
    """The role prompt must not tell the agent to always ask for the name.

    It used to end its Opening with "Begin the intake by asking for the
    patient's full name", which overrode the injected patient context.
    """
    from customagents.voiceagent.voiceintakeprompt import VOICE_INTAKE_PROMPT

    assert "asking for the patient's full name" not in VOICE_INTAKE_PROMPT
    assert "Known Patient Information" in VOICE_INTAKE_PROMPT


def test_patient_context_section_forbids_re_deriving_fields():
    section = build_patient_context_section("age = 34")
    assert "ALREADY COLLECTED" in section
    assert "date of birth" in section


def test_prompts_do_not_ask_for_dob_when_an_age_is_known():
    """An age is enough — asking for date of birth anyway was the bug reported.

    The demographic rules used to say "Prefer date of birth over asking for
    age", which contradicted the injected patient context.
    """
    from customagents.previsitagent.intakeprompt import INTAKE_PROMPT
    from customagents.voiceagent.voiceconsultprompt import VOICE_CONSULT_PROMPT
    from customagents.voiceagent.voiceintakeprompt import VOICE_INTAKE_PROMPT

    for prompt in (VOICE_INTAKE_PROMPT, VOICE_CONSULT_PROMPT, INTAKE_PROMPT):
        assert "Prefer date of birth over asking for age" not in prompt
        assert "do NOT ask for date of birth" in prompt
