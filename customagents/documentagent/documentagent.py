from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

from agent.agent import Agent
from agent.events import AgentEvent, AgentType
from config.config import Config
from prompts.system import get_system_prompt

from .documentprompt import DOCUMENT_RETRIEVAL_PROMPT


class DocumentRetrievalAgent(Agent):
    """Agent for answering questions using indexed medical documents.

    The agent uses the base agentic loop and configured retrieval tools
    to generate answers grounded in the medical document collection.

    Model, prompt, and tool selection are handled by AgentFactory and
    the configuration/registry layer.
    """

    def __init__(self, config: Config, session: Optional[Any] = None) -> None:
        """Initialize the document retrieval agent.

        Args:
            config: Application configuration.
            session: Optional existing session used to preserve
                conversation history and shared runtime resources.
        """
        super().__init__(
            config,
            DOCUMENT_RETRIEVAL_PROMPT,
            agent_type=AgentType.DOCUMENT_RETRIEVAL,
        )

        if session:
            self.session = session

        # Retrieval is mandatory: never allow a bare LLM answer without
        # searching the medical documents first.
        self.force_tool_choice = True
        # Only the retrieval tools are relevant here. This prevents the model
        # from routing the question through unrelated tools like memory.
        self.allowed_tool_names = [
            "jina_embedding",
            "medical_document_search",
        ]

    async def run(self, message: str) -> AsyncGenerator[AgentEvent, None]:
        """Process a user question using the document retrieval pipeline.

        The method prepares the session, applies the resolved system
        prompt, records the user message, starts MLflow tracking, and
        delegates execution to the base agentic loop.

        Args:
            message: User's document-related question.

        Yields:
            AgentEvent objects produced by the agentic loop.
        """
        if not message or not message.strip():
            raise ValueError("Document retrieval message cannot be empty.")

        # 1. Ensure the session is ready.
        if not self.session.context_manager:
            await self.session.initialize()

        # 2. Identify the current agent for tracking.
        self.session.agent_name = "DocumentRetrievalAgent"

        # 3. Build the complete system prompt, including the retrieval scope
        # controlled by the application. The scope must be injected so the
        # agent uses the real identifiers instead of guessing placeholders.
        scope_lines = ["## Retrieval Scope (authorized by the application)"]
        patient_id = self.session.metadata.get("patient_id")
        file_id = self.session.metadata.get("file_id")

        if patient_id:
            scope_lines.append(f"patient_id: {patient_id}")
        else:
            scope_lines.append("patient_id: (none provided)")

        if file_id:
            scope_lines.append(f"file_id: {file_id}")
        else:
            scope_lines.append("file_id: (none provided)")

        role_prompt = (
            f"{self.system_prompt}\n\n{chr(10).join(scope_lines)}"
        )

        full_system_prompt = get_system_prompt(
            config=self.config,
            role_prompt=role_prompt,
            user_memory=getattr(self, "memory", None),
        )

        self.session.context_manager.set_system_prompt(full_system_prompt)

        # 4. Add the user's question.
        self.session.context_manager.add_user_message(message.strip())

        # 5. Start MLflow tracking.
        self.session.start_mlflow_run(message)

        try:
            # 6. Execute the existing agentic loop.
            #
            # The configured tools (jina_embedding, medical_document_search)
            # are already available through the session/tool registry.
            async for event in self._agentic_loop():
                if hasattr(event, "data") and event.data.get("agent") is None:
                    event.data["agent"] = self.agent_type

                yield event

        finally:
            # 7. Always close the MLflow run.
            self.session.end_mlflow_run()

    async def __aenter__(self) -> DocumentRetrievalAgent:
        """Ensure the agent session is initialized before use."""
        if not self.session.context_manager:
            await self.session.initialize()

        return self