
"""
Reindex the ``clinical_documents`` OpenSearch index with a valid k-NN mapping.

The original index maps the ``embedding`` field as ``knn_vector`` with only a
``dimension``, which is missing the required ``method`` definition. OpenSearch
never builds the ANN graph in that state, so every ``knn`` query fails with:

    Field 'embedding' is not built for ANN search.

This script backs up the existing documents, recreates the index with an
HNSW ``method`` on the embedding field, and reindexes the saved documents.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from opensearchpy import OpenSearch, helpers

INDEX_NAME = "clinical_documents"

# Match the existing mapping and settings, adding the missing ``method``.
INDEX_CONFIG: dict[str, Any] = {
    "settings": {
        "index": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "knn": True,
        }
    },
    "mappings": {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "chunk_type": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "space_type": "l2",
                    "engine": "lucene",
                    "parameters": {
                        "ef_construction": 128,
                        "m": 16,
                    },
                },
            },
            "encounter_id": {"type": "keyword"},
            "file_id": {"type": "keyword"},
            "patient_id": {"type": "keyword"},
            "report_type": {"type": "keyword"},
            "service_request_id": {"type": "keyword"},
            "source_file": {"type": "keyword"},
            "text": {"type": "text"},
        }
    },
}


def get_client() -> OpenSearch:
    import os

    host = os.environ.get("OPENSEARCH_HOST", "localhost")
    port = int(os.environ.get("OPENSEARCH_PORT", "9200"))
    use_ssl = os.environ.get("OPENSEARCH_SSL", "false").lower() == "true"
    user = os.environ.get("OPENSEARCH_USER")
    password = os.environ.get("OPENSEARCH_PASSWORD")

    kwargs: dict[str, Any] = {
        "hosts": [{"host": host, "port": port}],
        "use_ssl": use_ssl,
        "verify_certs": False,
        "ssl_show_warn": False,
        "timeout": 30,
    }
    if user and password:
        kwargs["http_auth"] = (user, password)

    return OpenSearch(**kwargs)


def fetch_documents(client: OpenSearch) -> list[dict[str, Any]]:
    """Return the full ``_source`` of every document in the index."""
    count = client.count(index=INDEX_NAME)["count"]
    if count == 0:
        return []

    docs: list[dict[str, Any]] = []
    for hit in helpers.scan(
        client,
        index=INDEX_NAME,
        query={"query": {"match_all": {}}},
        _source=True,
    ):
        docs.append(hit["_source"])
    return docs


def main() -> int:
    client = get_client()

    if not client.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' does not exist. Nothing to do.")
        return 0

    print(f"Backing up {INDEX_NAME} documents...")
    docs = fetch_documents(client)
    print(f"Fetched {len(docs)} documents.")

    backup_path = "clinical_documents_backup.json"
    with open(backup_path, "w", encoding="utf-8") as fh:
        json.dump(docs, fh, ensure_ascii=False)
    print(f"Backup written to {backup_path}")

    print(f"Deleting index '{INDEX_NAME}'...")
    client.indices.delete(index=INDEX_NAME, ignore=[404])

    print(f"Creating index '{INDEX_NAME}' with k-NN method...")
    client.indices.create(index=INDEX_NAME, body=INDEX_CONFIG)

    if not docs:
        print("No documents to reindex.")
        return 0

    print(f"Reindexing {len(docs)} documents...")
    actions = [
        {
            "_index": INDEX_NAME,
            "_source": doc,
        }
        for doc in docs
    ]
    success, errors = helpers.bulk(client, actions, raise_on_error=False)
    print(f"Reindexed {success} documents.")

    if errors:
        print("Some documents failed to reindex:")
        for error in errors:
            print(json.dumps(error, ensure_ascii=False))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
