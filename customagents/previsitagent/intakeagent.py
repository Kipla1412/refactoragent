from __future__ import annotations
from typing import AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentEventType, AgentType
from .intakeprompt import INTAKE_PROMPT
from prompts.system import get_system_prompt


class IntakeAgent(Agent):

    GREETING = (
        "Hello, I'm your medical intake assistant. I'll gather some "
        "information before your visit."
    )

    # Phrases that signal the intake conversation is complete.
    END_PATTERNS = (
        "intake is complete",
        "intake has been completed",
        "thank you. your intake",
        "information will be available for your doctor",
    )

    def __init__(self, config, session=None):
        """
        Follows the Consult Agent pattern:
        Base Agent handles the heavy lifting, we handle the clinical intake logic.
        """
        super().__init__(config, INTAKE_PROMPT, AgentType.INTAKE)
        if session:
            self.session = session

    async def run(self, message: str = "") -> AsyncGenerator[AgentEvent, None]:
        """
        The main entry point. On a brand-new session the agent greets the
        patient first; on subsequent turns it answers the user's message.
        Everything streams back through the same NDJSON response.
        """
        if not self.session.context_manager:
            await self.session.initialize()

        self.session.agent_name = "IntakeAssistant"

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=self.system_prompt,
            user_memory=getattr(self, "memory", None),
        )
        self.session.context_manager.set_system_prompt(full_system_prompt)

        already_greeted = self.session.metadata.get("greeted", False)

        if message:
            self.session.context_manager.add_user_message(message)

        self.session.start_mlflow_run("Intake Conversation Turn")

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
                if hasattr(event, "data") and "agent" in event.data:
                    event.data["agent"] = self.agent_type
                if event.type == AgentEventType.TEXT_DELTA:
                    content = event.data.get("content", "")
                    response_text += content
                yield event

            if self._is_end_of_conversation(response_text):
                yield AgentEvent.status_end(agent=self.agent_type)

        except Exception as e:
            yield AgentEvent.agent_error(error=f"Intake Loop Error: {str(e)}")

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
