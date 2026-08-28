import logging
from typing import Optional
from opensearchpy import OpenSearch
from config.config import Config

logger = logging.getLogger(__name__)

class OpenSearchConnector:
    """
    Infrastructure Layer — OpenSearch Connector
    
    Handles the lifecycle of the OpenSearch connection for your AI Platform.
    """

    def __init__(self, config: Config):
        self.config = config
        self._client: Optional[OpenSearch] = None


    def connect(self) -> OpenSearch:
        """Lazily creates and returns the OpenSearch client."""
        if self._client is None:
            logger.info("Initializing OpenSearch client at %s:%s", 
                        self.config.opensearch_host, self.config.opensearch_port)
            
            client_kwargs = {
                "hosts": [{"host": self.config.opensearch_host, "port": self.config.opensearch_port}],
                "use_ssl": self.config.opensearch_ssl,
                "verify_certs": False,
                "ssl_show_warn": False,
                "timeout": 15
            }

            if self.config.opensearch_user and self.config.opensearch_password:
                client_kwargs["http_auth"] = (
                    self.config.opensearch_user, 
                    self.config.opensearch_password
                )

            self._client = OpenSearch(**client_kwargs)
        return self._client

    def is_healthy(self) -> bool:
        """Pings the server to ensure it is alive."""
        try:
            client = self.connect()
            return client.ping()
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return False
    
    def __enter__(self):
        """Allows use with 'with' statements."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Automatically closes the connection on exit."""
        self.close()
        
    def close(self):
        """Closes the transport layer safely."""
        if self._client:
            logger.info("Closing OpenSearch connection...")
            self._client.transport.close()
            self._client = None