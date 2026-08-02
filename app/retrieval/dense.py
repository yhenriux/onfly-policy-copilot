"""Armazenamento e busca vetorial com filtro obrigatório por empresa."""

from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from llama_index.core import Document
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.vector_stores import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
    VectorStoreQuery,
)
from llama_index.vector_stores.qdrant import QdrantVectorStore as LlamaIndexQdrantVectorStore
from qdrant_client import QdrantClient, models

from app.core.exceptions import RetrievalUnavailableError
from app.domain.models import DocumentChunk, RetrievedChunk


def _field_condition(key: str, value: str | bool) -> models.FieldCondition:
    """Cria uma condição simples para filtrar metadados no Qdrant."""

    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _external_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Mantém o contrato do projeto estável apesar dos nomes internos do LlamaIndex."""

    return {
        **payload,
        "document_id": payload.get("policy_document_id"),
        "text": payload.get("policy_text"),
        "is_active": payload.get("search_status") == "active",
        "is_deleted": payload.get("deletion_status") == "deleted",
    }


class QdrantVectorStore:
    """Armazena e recupera trechos de políticas no Qdrant local."""

    def __init__(
        self,
        *,
        collection_name: str,
        path: Path | None = None,
        url: str | None = None,
        api_key: str | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        if client is None and path is None and url is None:
            raise ValueError("Informe cliente, caminho local ou URL do Qdrant")
        if path is not None and url is not None:
            raise ValueError("Use caminho local ou URL do Qdrant, nunca os dois")
        self._client = client or (
            QdrantClient(url=url, api_key=api_key)
            if url is not None
            else QdrantClient(path=str(path))
        )
        self._collection_name = collection_name
        self._llama_index_store = LlamaIndexQdrantVectorStore(
            collection_name=collection_name,
            client=self._client,
            flat_metadata=True,
        )

    def ensure_collection(self, vector_size: int) -> None:
        """Cria a coleção uma vez usando similaridade de cosseno."""

        try:
            if not self._client.collection_exists(self._collection_name):
                self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    ),
                )
        except Exception as error:
            raise RetrievalUnavailableError("Não foi possível preparar a coleção") from error

    def _document_filter(
        self,
        *,
        tenant_id: str,
        document_id: str,
        version: str | None = None,
    ) -> models.Filter:
        if version is not None:
            return models.Filter(
                must=[
                    _field_condition("tenant_id", tenant_id),
                    _field_condition("policy_document_id", document_id),
                    _field_condition("version", version),
                ]
            )
        return models.Filter(
            must=[
                _field_condition("tenant_id", tenant_id),
                    _field_condition("policy_document_id", document_id),
            ]
        )

    def version_hashes(self, *, tenant_id: str, document_id: str, version: str) -> set[str]:
        """Informa quais conteúdos já foram gravados para uma versão."""

        if not self._client.collection_exists(self._collection_name):
            return set()
        points, _ = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=self._document_filter(
                tenant_id=tenant_id,
                document_id=document_id,
                version=version,
            ),
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        payloads = [cast(dict[str, Any], point.payload or {}) for point in points]
        # Registros anteriores não têm o nó serializado pelo LlamaIndex. Reindexá-los
        # com o mesmo identificador substitui o vetor antigo sem duplicar conteúdo.
        if any("_node_content" not in payload for payload in payloads):
            return set()
        return {str(payload["document_hash"]) for payload in payloads}

    def deactivate_versions(self, *, tenant_id: str, document_id: str) -> None:
        """Mantém versões antigas para auditoria, mas as retira da busca."""

        if not self._client.collection_exists(self._collection_name):
            return
        self._client.set_payload(
            collection_name=self._collection_name,
            payload={"search_status": "inactive"},
            points=self._document_filter(tenant_id=tenant_id, document_id=document_id),
            wait=True,
        )

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Grava trechos, vetores e metadados de forma rastreável."""

        if len(chunks) != len(embeddings):
            raise ValueError("Cada trecho deve possuir exatamente um vetor")

        nodes: list[BaseNode] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            metadata = {
                    "tenant_id": chunk.tenant_id,
                    "policy_document_id": chunk.document_id,
                    "title": chunk.title,
                    "version": chunk.version,
                    "valid_from": chunk.valid_from.isoformat(),
                    "valid_until": (
                        chunk.valid_until.isoformat() if chunk.valid_until is not None else None
                    ),
                    "source": chunk.source,
                    "chunk_id": chunk.chunk_id,
                    "position": chunk.position,
                    "section": chunk.section,
                    "policy_text": chunk.text,
                    "document_hash": chunk.document_hash,
                    "chunk_hash": chunk.chunk_hash,
                    "search_status": "active",
                    "deletion_status": "available",
                }
            document = Document(text=chunk.text, metadata=metadata)
            nodes.append(
                TextNode(
                    id_=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"{chunk.tenant_id}:{chunk.document_id}:{chunk.version}:{chunk.chunk_hash}",
                        )
                    ),
                    text=document.text,
                    metadata=document.metadata,
                    embedding=embedding,
                )
            )

        try:
            self._llama_index_store.add(nodes)
        except Exception as error:
            raise RetrievalUnavailableError("Não foi possível gravar os trechos") from error

    def search(
        self,
        query_vector: list[float],
        *,
        tenant_id: str,
        limit: int,
    ) -> list[RetrievedChunk]:
        """Devolve somente trechos ativos, não excluídos e da empresa solicitada."""

        if not tenant_id.strip():
            raise ValueError("tenant_id é obrigatório em toda busca")
        try:
            response = self._llama_index_store.query(
                VectorStoreQuery(
                    query_embedding=query_vector,
                    similarity_top_k=limit,
                    filters=MetadataFilters(
                        filters=[
                            MetadataFilter(
                                key="tenant_id", value=tenant_id, operator=FilterOperator.EQ
                            ),
                            MetadataFilter(
                                key="search_status", value="active", operator=FilterOperator.EQ
                            ),
                            MetadataFilter(
                                key="deletion_status",
                                value="available",
                                operator=FilterOperator.EQ,
                            ),
                        ]
                    ),
                )
            )
        except Exception as error:
            raise RetrievalUnavailableError("Não foi possível pesquisar as políticas") from error

        results: list[RetrievedChunk] = []
        for rank, (node, score) in enumerate(
            zip(response.nodes or [], response.similarities or [], strict=True), start=1
        ):
            payload = node.metadata
            results.append(
                RetrievedChunk(
                    tenant_id=str(payload["tenant_id"]),
                    document_id=str(payload["policy_document_id"]),
                    title=str(payload["title"]),
                    version=str(payload["version"]),
                    valid_from=date.fromisoformat(str(payload["valid_from"])),
                    valid_until=(
                        date.fromisoformat(str(payload["valid_until"]))
                        if payload.get("valid_until") is not None
                        else None
                    ),
                    source=str(payload["source"]),
                    chunk_id=str(payload["chunk_id"]),
                    position=int(payload["position"]),
                    section=str(payload["section"]),
                    text=str(payload["policy_text"]),
                    document_hash=str(payload["document_hash"]),
                    chunk_hash=str(payload["chunk_hash"]),
                    score=float(score),
                    dense_score=float(score),
                    dense_rank=rank,
                )
            )
        return results

    def active_payloads(self, *, tenant_id: str) -> list[dict[str, Any]]:
        """Lista os trechos pesquisáveis de uma empresa para a busca lexical."""

        if not tenant_id.strip():
            raise ValueError("tenant_id é obrigatório em toda busca")
        points, _ = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=models.Filter(
                must=[
                    _field_condition("tenant_id", tenant_id),
                    _field_condition("search_status", "active"),
                    _field_condition("deletion_status", "available"),
                ]
            ),
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        return [_external_payload(cast(dict[str, Any], point.payload or {})) for point in points]

    def logical_delete(self, *, tenant_id: str, document_id: str) -> int:
        """Marca todas as versões como excluídas sem apagar o histórico."""

        document_filter = self._document_filter(tenant_id=tenant_id, document_id=document_id)
        affected = int(
            self._client.count(
                collection_name=self._collection_name,
                count_filter=document_filter,
                exact=True,
            ).count
        )
        if affected:
            self._client.set_payload(
                collection_name=self._collection_name,
                payload={"search_status": "inactive", "deletion_status": "deleted"},
                points=document_filter,
                wait=True,
            )
        return affected

    def payloads(self, *, tenant_id: str, document_id: str) -> list[dict[str, Any]]:
        """Devolve metadados para testes e demonstrações, sem incluir vetores."""

        points, _ = self._client.scroll(
            collection_name=self._collection_name,
            scroll_filter=self._document_filter(tenant_id=tenant_id, document_id=document_id),
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
        return [_external_payload(cast(dict[str, Any], point.payload or {})) for point in points]

    def count(self, *, active_only: bool = False) -> int:
        """Informa quantos trechos estão gravados na coleção."""

        count_filter = None
        if active_only:
            count_filter = models.Filter(
                must=[
                    _field_condition("search_status", "active"),
                    _field_condition("deletion_status", "available"),
                ]
            )
        return int(
            self._client.count(
                self._collection_name,
                count_filter=count_filter,
                exact=True,
            ).count
        )

    def close(self) -> None:
        """Libera os recursos usados pelo Qdrant local."""

        self._client.close()

    def reset(self) -> None:
        """Remove a coleção sintética para permitir uma nova carga completa."""

        if self._client.collection_exists(self._collection_name):
            self._client.delete_collection(self._collection_name)
        if self._client.collection_exists(self._collection_name):
            raise RetrievalUnavailableError("A coleção sintética não foi removida")
