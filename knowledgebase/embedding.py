import logging
import httpx
from typing import Optional
from config.config import Config

logger = logging.getLogger(__name__)

class EmbeddingConnector:
    """
    Infrastructure Layer — Jina AI Embedding Connector
    
    Responsibilities:
    - Manage httpx.AsyncClient lifecycle.
    - Provide a health check to verify API connectivity.
    """

    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    def connect(self) -> httpx.AsyncClient:
        """Returns a reusable async client instance."""
        if self._client is None or self._client.is_closed:
            logger.info("Initializing Jina AI Embedding Client | URL: %s", self.config.jina_api_url)
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "Authorization": f"Bearer {self.config.jina_api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client

    # async def is_healthy(self) -> bool:
    #     """
    #     Health Check: Verifies the JINA_API_KEY and connection.
    #     Performs a lightweight request to the models endpoint.
    #     """
    #     try:
    #         client = self.connect()
    #         # We call the models endpoint to verify the API key is active
    #         response = await client.get(self.config.jina_api_url)
            
    #         if response.status_code == 200:
    #             logger.info("Jina Embedding Health Check: PASSED")
    #             return True
    #         else:
    #             logger.error("Jina Health Check: FAILED | Status: %s | %s", 
    #                          response.status_code, response.text)
    #             return False
    #     except Exception as e:
    #         logger.error("Jina Health Check: ERROR | %s", str(e))
    #         return False

    async def close(self):
        """Gracefully closes the underlying HTTP transport."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("Jina Embedding connection pool closed.")
            self._client = None

    async def __aenter__(self):
        return self.connect()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()