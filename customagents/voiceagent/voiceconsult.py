from __future__ import annotations
import re
import base64
from typing import TYPE_CHECKING, AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType, AgentType
from client.response import StreamEventType
from prompts.system import get_system_prompt
from .voiceconsultprompt import VOICE_CONSULT_PROMPT
from .voiceagent import build_patient_context_section

class VoiceConsultAgent(Agent):

    # Regexes that signal the voice consultation is concluding. Matching is done
    # against punctuation-stripped, lowercased text (see
    # `_is_end_of_conversation`), so these are written in normalized form.
    #
    # "completes our consultation" is the marker VOICE_CONSULT_PROMPT requires
    # in the closing acknowledgment. Only statement forms are matched: the bare
    # infinitive ("complete our consultation") is ordinary mid-consultation
    # wording, and phrases like "in person evaluation" or "see a doctor" appear
    # in normal advice, so they must not end the call.
    END_PATTERNS = (
        r"(?:completes|concludes) (?:our|the) consultation",
        r"(?:our|the) consultation is (?:now )?complete",
        r"(?:our|the) consultation has been completed",
        # Emergency escalation ends the consultation.
        r"call emergency services",
        r"go to the nearest emergency department",
    )

    def __init__(self, config, session=None):
        super().__init__(config, VOICE_CONSULT_PROMPT, AgentType.VOICE_CONSULT)
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
