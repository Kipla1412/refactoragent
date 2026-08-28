from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from config.config import Config
from knowledgebase.embedding import EmbeddingConnector
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult

logger = logging.getLogger(__name__)


class JinaEmbeddingParams(BaseModel):
    """Parameters required to generate a Jina query embedding."""

    text: str = Field(
        ...,
        min_length=1,
        description="Text to convert into an embedding vector.",
    )
    task: Literal[
        "retrieval.query",
        "retrieval.passage",
    ] = Field(
        default="retrieval.query",
        description=(
            "Embedding task. Use retrieval.query for user queries "
            "and retrieval.passage when embedding document content."
        ),
    )


class JinaEmbeddingTool(Tool):
    """Generate embeddings using the configured Jina AI embedding model.

    This tool is intentionally independent of OpenSearch and document
    retrieval. It converts text into a vector that can subsequently be
    consumed by a retrieval tool.
    """

    name = "jina_embedding"
    description = (
        "Generate a Jina AI embedding vector for semantic retrieval. "
        "Use retrieval.query for user questions."
    )
    kind = ToolKind.NETWORK

    def __init__(self, config: Config) -> None:
        """Initialize the Jina embedding tool.

        Args:
            config: Application configuration containing Jina settings.
        """
        super().__init__(config)

    @property
    def schema(self) -> type[BaseModel]:
        """Return the Pydantic schema used to validate tool parameters."""
        return JinaEmbeddingParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Generate an embedding for the supplied text.

        Args:
            invocation: Tool invocation containing the input text and embedding task.

        Returns:
            ToolResult containing the generated embedding vector and metadata.

        Raises:
            No exceptions are propagated. Failures are returned as an error ToolResult.
        """
        try:
            params = JinaEmbeddingParams(**invocation.params)

            session = getattr(self.config, "_session", None)
            if session:
                client = session.embedding_connector.connect()
            else:
                client = EmbeddingConnector(self.config).connect()

            response = await client.post(
                self.config.jina_api_url,
                json={
                    "model": self.config.jina_model,
                    "task": params.task,
                    "dimensions": self.config.jina_dimensions,
                    "input": [params.text],
                },
            )
            response.raise_for_status()

            data = response.json()
            vector = data["data"][0]["embedding"]

            if not vector:
                return ToolResult.error_result(
                    error="Jina returned an empty embedding."
                )

            return ToolResult.success_result(
                output=json.dumps({"vector": vector}),
                metadata={
                    "model": self.config.jina_model,
                    "dimensions": len(vector),
                    "task": params.task,
                },
            )

        except Exception as exc:
            logger.exception("Jina embedding generation failed.")
            return ToolResult.error_result(
                error=f"Jina embedding generation failed: {exc}"
            )