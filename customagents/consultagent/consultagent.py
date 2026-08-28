
from __future__ import annotations
from typing import AsyncGenerator
from agent.agent import Agent
from agent.events import AgentEvent, AgentType
from prompts.system import get_system_prompt
from .consultprompt import CONSULT_PROMPT

class ConsultingAgent(Agent):
    def __init__(self, config, session=None):
        """
        Initialize with a specific prompt. 
        Pass an existing session to keep history across agents.
        """
        super().__init__(config, CONSULT_PROMPT, AgentType.CONSULT)
        if session:
            self.session = session

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """
        The main entry point for the medical consultation.
        Uses the base Agentic Loop to support tracking and future tools.
        """
        # 1. Ensure the session is ready
        if not self.session.context_manager:
            await self.session.initialize()

        # 2. Setup metadata for tracking
        self.session.agent_name = "DoctorAI"

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=self.system_prompt, # This is your CONSULT_PROMPT
            user_memory=getattr(self, 'memory', None) # Pass memory if available
        )
        # Set it in the context manager
        self.session.context_manager.set_system_prompt(full_system_prompt)
        
        # 4. Add the patient's message
        self.session.context_manager.add_user_message(message)

        # 5. MLflow Tracking (Start after system prompt is set for better logging)
        self.session.start_mlflow_run(message)
        

        try:
            # 6. Run the core loop
            async for event in self._agentic_loop():
                if hasattr(event, 'data') and event.data.get("agent") is None:
                    event.data["agent"] = self.agent_type
                yield event
        finally:
            self.session.end_mlflow_run()

    async def __aenter__(self):
        if not self.session.context_manager:
            await self.session.initialize()
        return self