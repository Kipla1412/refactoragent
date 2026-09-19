
from __future__ import annotations
from typing import AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentType, AgentEventType
from prompts.system import get_system_prompt
from .consultprompt import CONSULT_PROMPT

class ConsultingAgent(Agent):

    GREETING = (
        "Hi! I'm your medical assistant. I'm here to help with your "
        "health concerns today."
    )

    # Phrases that signal the consultation is concluding.
    END_PATTERNS = (
        "consultation is complete",
        "in-person evaluation",
        "see a doctor",
        "emergency department",
        "follow-up instructions",
        "take care",
        "stay healthy",
    )

    def __init__(self, config, session=None):
        """
        Initialize with a specific prompt.
        Pass an existing session to keep history and greeting state.
        """
        super().__init__(config, CONSULT_PROMPT, AgentType.CONSULT)
        if session:
            self.session = session

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """
        The main entry point for the medical consultation. Greets on a
        fresh session, then answers via the base agentic loop.
        """
        if not self.session.context_manager:
            await self.session.initialize()

        self.session.agent_name = "DoctorAI"

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=self.system_prompt,
            user_memory=getattr(self, "memory", None),
        )
        self.session.context_manager.set_system_prompt(full_system_prompt)

        already_greeted = self.session.metadata.get("greeted", False)

        if message:
            self.session.context_manager.add_user_message(message)

        self.session.start_mlflow_run(message or "greeting")

        try:
            # Greet only once per session, on the first turn.
            if not already_greeted:
                self.session.metadata["greeted"] = True
                yield AgentEvent.text_complete(self.GREETING, agent=self.agent_type)

                # No real input yet — just greet and wait for the user.
                if not message.strip():
                    return

            response_text = ""
            async for event in self._agentic_loop():
                if hasattr(event, "data") and event.data.get("agent") is None:
                    event.data["agent"] = self.agent_type
                if event.type == AgentEventType.TEXT_DELTA:
                    content = event.data.get("content", "")
                    response_text += content
                yield event

            if self._is_end_of_conversation(response_text):
                yield AgentEvent.status_end(agent=self.agent_type)

        except Exception as e:
            yield AgentEvent.agent_error(error=f"Consult Loop Error: {str(e)}")

        finally:
            self.session.end_mlflow_run()

    @classmethod
    def _is_end_of_conversation(cls, response_text: str) -> bool:
        normalized = response_text.lower().strip()
        return any(pattern in normalized for pattern in cls.END_PATTERNS)

    async def __aenter__(self):
        if not self.session.context_manager:
            await self.session.initialize()
        return self