from __future__ import annotations
import re
import base64
from typing import TYPE_CHECKING, AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType, AgentType
from client.response import StreamEventType
from prompts.system import get_system_prompt
from .voiceintakeprompt import VOICE_INTAKE_PROMPT
from .voiceagent import build_patient_context_section

class VoiceIntakeAgent(Agent):

    # Regexes that signal the voice intake conversation is complete. Matching is
    # done against punctuation-stripped, lowercased text (see
    # `_is_end_of_conversation`), so these are written in normalized form.
    END_PATTERNS = (
        r"intake (?:is|has been) (?:now )?complete",
        r"complet(?:e|es|ed) (?:your|the) intake",
        r"information will be available for your doctor",
    )

    def __init__(self, config, session=None):
        super().__init__(config, VOICE_INTAKE_PROMPT, AgentType.VOICE_INTAKE)
        if session:
            self.session = session

    async def run(self, transcript: str) -> AsyncGenerator[AgentEvent, None]:
        if not self.session.context_manager:
            await self.session.initialize()

        self.session.agent_name = self.__class__.__name__

        role_prompt = self.system_prompt
        patient_context = self.session.metadata.get("patient_context")
        if patient_context:
            role_prompt = f"{role_prompt}\n\n{build_patient_context_section(patient_context)}"

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=role_prompt,
        )
        self.session.context_manager.set_system_prompt(full_system_prompt)
        self.session.context_manager.add_user_message(transcript)

        self.session.start_mlflow_run(transcript)

        try:
            response_text = ""
            async for event in self._agentic_loop():
                if hasattr(event, 'data') and event.data.get("agent") is None:
                    event.data["agent"] = self.agent_type
                if event.type == AgentEventType.TEXT_DELTA:
                    response_text += event.data.get("content", "")
                yield event

            if self._is_end_of_conversation(response_text):
                yield AgentEvent.status_end(agent=self.agent_type)
        finally:
            self.session.end_mlflow_run()

    @classmethod
    def _is_end_of_conversation(cls, response_text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", response_text.lower()).strip()
        return any(re.search(pattern, normalized) for pattern in cls.END_PATTERNS)

    async def __aenter__(self):
        if not self.session.context_manager:
            await self.session.initialize()
        return self