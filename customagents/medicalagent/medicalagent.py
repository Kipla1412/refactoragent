from __future__ import annotations
from typing import AsyncGenerator

from agent.agent import Agent
from agent.events import AgentEvent, AgentType
from .medicalprompt import MEDICAL_PROMPT
from prompts.system import get_system_prompt


class MedicalAgent(Agent):

    def __init__(self, config, session=None):
        super().__init__(
            config=config,
            system_prompt=MEDICAL_PROMPT,
            agent_type=AgentType.MEDICAL,
        )
        if session:
            self.session = session

    async def run(
        self,
        message: str = ""
    ) -> AsyncGenerator[AgentEvent, None]:

        if not self.session.context_manager:
            await self.session.initialize()

        self.session.agent_name = "MedicalAgent"

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=self.system_prompt,
        )

        self.session.context_manager.set_system_prompt(full_system_prompt)

        if message:
            self.session.context_manager.add_user_message(message)

        self.session.start_mlflow_run("Medical Agent Query")

        try:
            async for event in self._agentic_loop():
                yield event

        except Exception as e:
            yield AgentEvent.agent_error(
                error=f"Medical Agent Error: {str(e)}"
            )

        finally:
            self.session.end_mlflow_run()

    async def __aenter__(self):
        if not self.session.context_manager:
            await self.session.initialize()
        return self
