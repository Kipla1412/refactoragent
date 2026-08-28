from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, List

from pydantic import BaseModel, Field

from config.config import Config
from knowledgebase.opensearch import OpenSearchConnector
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult

logger = logging.getLogger(__name__)


class MedicalDocumentSearchParams(BaseModel):
    """
    Parameters used to search medical document chunks.

    The patient identifier restricts retrieval to documents belonging to
    the requested patient. An optional file identifier can further
    restrict retrieval to a specific uploaded document.
    """

    query_text: str = Field(
        ...,
        description="The user's medical document question."
    )

    vector: list[float] = Field(
        ...,
        description="Embedding vector generated from the user's question."
    )

    patient_id: str = Field(
        ...,
        description="Patient identifier used to restrict document retrieval."
    )

    file_id: str | None = Field(
        default=None,
        description=(
            "Optional document/file identifier used to restrict retrieval "
            "to a specific file."
        )
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of document chunks to return."
    )


class MedicalDocumentSearchTool(Tool):
    """Retrieve relevant medical document chunks from OpenSearch.

    The tool combines lexical BM25 retrieval with vector similarity
    retrieval and relies on the configured OpenSearch search pipeline
    for result fusion/ranking.
    """

    name = "medical_document_search"
    description = (
        "Search indexed medical documents using hybrid keyword and vector retrieval."
    )
    kind = ToolKind.NETWORK

    def __init__(self, config: Config):
        """Initialize the medical document search tool."""
        super().__init__(config)

    @property
    def schema(self) -> type[BaseModel]:
        """Return the input schema expected by the tool."""
        return MedicalDocumentSearchParams

    @staticmethod
    def _build_scope_filter(params: MedicalDocumentSearchParams) -> dict[str, Any] | None:
        """Build an OpenSearch filter query for the authorized retrieval scope.

        Returns a single query object suitable for a ``hybrid`` subquery filter,
        or ``None`` when no scope constraints are available.
        """
        must: list[dict[str, Any]] = []

        patient_id = params.patient_id
        if patient_id and patient_id != "patient_id":
            must.append({"term": {"patient_id": patient_id}})

        file_id = params.file_id
        if file_id and file_id != "file_id":
            must.append({"term": {"file_id": file_id}})

        if not must:
            return None
        if len(must) == 1:
            return must[0]

        return {"bool": {"must": must}}

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        """Execute hybrid retrieval against the medical document index."""
        try:
            params = MedicalDocumentSearchParams(**invocation.params)

            session = getattr(self.config, "_session", None)
            if session:
                client = session.opensearch_connector.connect()
            else:
                client = OpenSearchConnector(self.config).connect()

            scope_filter = self._build_scope_filter(params)

            match_query: dict[str, Any] = {
                "match": {
                    "text": {
                        "query": params.query_text,
                    }
                }
            }
            if scope_filter:
                match_query = {
                    "bool": {
                        "must": match_query,
                        "filter": scope_filter,
                    }
                }

            knn_query: dict[str, Any] = {
                "knn": {
                    "embedding": {
                        "vector": params.vector,
                        "k": params.limit,
                    }
                }
            }
            if scope_filter:
                knn_query["knn"]["embedding"]["filter"] = scope_filter

            search_body = {
                "size": params.limit,
                "_source": [
                    "chunk_id",
                    "chunk_type",
                    "text",
                    "patient_id",
                    "file_id",
                ],
                "query": {
                    "hybrid": {
                        "queries": [
                            match_query,
                            knn_query,
                        ]
                    }
                },
            }

            response = await asyncio.to_thread(
                client.search,
                index=self.config.medical_document_index,
                body=search_body,
                params={
                    "search_pipeline": self.config.opensearch_search_pipeline,
                },
            )

            results = [
                {
                    "score": hit.get("_score"),
                    "chunk_id": hit.get("_source", {}).get("chunk_id"),
                    "chunk_type": hit.get("_source", {}).get("chunk_type"),
                    "text": hit.get("_source", {}).get("text"),
                }
                for hit in response["hits"]["hits"]
            ]

            return ToolResult.success_result(
                output=json.dumps(results, indent=2),
                metadata={"total_hits": response["hits"]["total"]["value"]},
            )

        except Exception as exc:
            logger.exception("Medical document retrieval failed")
            return ToolResult.error_result(
                error=f"Medical document search failed: {exc}"
            )