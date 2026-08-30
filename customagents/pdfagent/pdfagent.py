from __future__ import annotations

from typing import AsyncGenerator

from agent.agent import Agent
from agent.events import AgentEvent, AgentType
from prompts.system import get_system_prompt

from .pdfprompt import PDF_CHAT_PROMPT


class PDFChatAgent(Agent):
    def __init__(self, config, session=None):
        super().__init__(config, PDF_CHAT_PROMPT, AgentType.PDF_CHAT)
        if session:
            self.session = session

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        if not message or not message.strip():
            yield AgentEvent.agent_error("Message is empty.")
            return

        if not self.session.context_manager:
            await self.session.initialize()

        self.session.agent_name = "PDFChatAgent"

        pdf_text = self.session.metadata.get("pdf_context")
        if not pdf_text or not pdf_text.strip():
            yield AgentEvent.agent_error(
                "No PDF document is available. Please upload a PDF first."
            )
            return

        # Inject the PDF as part of the system prompt (regenerated every turn)
        # rather than appending it to permanent conversation history. This keeps
        # the PDF reusable across questions without duplicating it.
        role_prompt = (
            f"{self.system_prompt}\n\n"
            "==================================================\n"
            "ACTIVE PDF DOCUMENT (source of truth)\n"
            "==================================================\n\n"
            f"{pdf_text}"
        )

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=role_prompt,
            user_memory=getattr(self, "memory", None),
        )
        self.session.context_manager.set_system_prompt(full_system_prompt)

        self.session.context_manager.add_user_message(message)

        self.session.start_mlflow_run(message)

        try:
            async for event in self._agentic_loop():
                if hasattr(event, "data") and event.data.get("agent") is None:
                    event.data["agent"] = self.agent_type
                yield event
        finally:
            self.session.end_mlflow_run()

    async def __aenter__(self):
        if not self.session.context_manager:
            await self.session.initialize()
        return self
