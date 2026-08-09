"""Persistência Neo4j do grafo de políticas."""

from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.knowledge_graph.models import KnowledgeGraphDocument


class Neo4jKnowledgeGraph:
    """Escreve nós idempotentes e relações sempre delimitadas por tenant."""

    def __init__(self, uri: str, username: str, password: str, database: str) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=(username, password))
        self._database = database

    async def ensure_constraints(self) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "CREATE CONSTRAINT policy_tenant_id IF NOT EXISTS "
                "FOR (n:Tenant) REQUIRE n.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT policy_rule_id IF NOT EXISTS FOR (n:Rule) REQUIRE n.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT policy_version_id IF NOT EXISTS "
                "FOR (n:PolicyVersion) REQUIRE n.id IS UNIQUE"
            )

    async def upsert_document(self, document: KnowledgeGraphDocument) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._write_document, document)

    async def search_rules(
        self, tenant_id: str, topic: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Busca regras explicitamente relacionadas a um tema dentro do tenant."""

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (tenant:Tenant {id: $tenant_id})-[:OWNS]->
                    (policy:Policy)-[:HAS_VERSION]->(version:PolicyVersion)
                    -[:DEFINES]->(rule:Rule)
                WHERE version.active = true AND rule.active = true
                  AND policy.tenant_id = $tenant_id AND version.tenant_id = $tenant_id
                  AND rule.tenant_id = $tenant_id
                  AND toLower(rule.topic) CONTAINS toLower($topic)
                RETURN rule.statement AS statement, rule.amount AS amount,
                       rule.currency AS currency, rule.conditions AS conditions,
                       rule.exceptions AS exceptions
                LIMIT $limit
                """,
                tenant_id=tenant_id,
                topic=topic,
                limit=limit,
            )
            return [dict(record) async for record in result]

    @staticmethod
    async def _write_document(tx: Any, document: KnowledgeGraphDocument) -> None:
        await tx.run(
            """
            MERGE (tenant:Tenant {id: $tenant_id})
            MERGE (policy:Policy {id: $policy_id})
            SET policy.tenant_id = $tenant_id, policy.document_id = $document_id,
                policy.title = $title
            MERGE (tenant)-[:OWNS]->(policy)
            WITH policy
            OPTIONAL MATCH (policy)-[:HAS_VERSION]->(old:PolicyVersion)
            SET old.active = false
            MERGE (version:PolicyVersion {id: $version_id})
            SET version.tenant_id = $tenant_id, version.document_id = $document_id,
                version.version = $version, version.valid_from = $valid_from,
                version.valid_until = $valid_until, version.active = true,
                version.extractor_version = $extractor_version
            MERGE (policy)-[:HAS_VERSION]->(version)
            """,
            tenant_id=document.tenant_id,
            document_id=document.document_id,
            policy_id=f"{document.tenant_id}:{document.document_id}",
            version_id=f"{document.tenant_id}:{document.document_id}:{document.version}",
            title=document.title,
            version=document.version,
            valid_from=document.valid_from,
            valid_until=document.valid_until,
            extractor_version=document.extractor_version,
        )
        for fact in document.facts:
            await tx.run(
                """
                MATCH (version:PolicyVersion {id: $version_id})
                MERGE (rule:Rule {id: $rule_id})
                SET rule.tenant_id = $tenant_id, rule.topic = $topic,
                    rule.statement = $statement, rule.amount = $amount,
                    rule.currency = $currency, rule.conditions = $conditions,
                    rule.active = true, rule.extractor_version = $extractor_version
                MERGE (version)-[:DEFINES]->(rule)
                MERGE (topic:Topic {id: $topic})
                MERGE (rule)-[:ABOUT]->(topic)
                FOREACH (condition IN $conditions |
                    MERGE (node:Condition {id: condition})
                    MERGE (rule)-[:HAS_CONDITION]->(node))
                FOREACH (exception IN $exceptions |
                    MERGE (node:Exception {id: exception})
                    MERGE (rule)-[:HAS_EXCEPTION]->(node))
                MERGE (evidence:Chunk {id: $chunk_id})
                SET evidence.tenant_id = $tenant_id, evidence.section = $section
                MERGE (rule)-[:SUPPORTED_BY]->(evidence)
                """,
                version_id=f"{document.tenant_id}:{document.document_id}:{document.version}",
                rule_id=f"{fact.tenant_id}:{fact.document_id}:{fact.version}:{fact.chunk_id}",
                tenant_id=fact.tenant_id,
                topic=fact.topic,
                statement=fact.statement,
                amount=fact.amount,
                currency=fact.currency,
                conditions=list(fact.conditions),
                exceptions=list(fact.exceptions),
                extractor_version=document.extractor_version,
                chunk_id=fact.chunk_id,
                section=fact.section,
            )

    async def close(self) -> None:
        await self._driver.close()
