"""
Supabase storage layer for RAG documents
"""
import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from supabase import create_client, Client

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a similarity search"""
    id: str
    project_name: str
    source_url: str
    title: str
    content: str
    chunk_index: int
    metadata: Dict[str, Any]
    similarity: float


class SupabaseStore:
    """Handles storage and retrieval of documents in Supabase"""

    def __init__(
        self,
        url: str = None,
        service_key: str = None
    ):
        """
        Initialize Supabase client

        Args:
            url: Supabase project URL
            service_key: Supabase service key
        """
        self.url = url or os.getenv("SUPABASE_URL")
        self.service_key = service_key or os.getenv("SUPABASE_SERVICE_KEY")

        if not self.url or not self.service_key:
            raise ValueError(
                "Supabase credentials not found. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
            )

        self.client: Client = create_client(self.url, self.service_key)

    async def store_documents(
        self,
        project_name: str,
        source_url: str,
        title: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata: Dict[str, Any] = None
    ) -> int:
        """
        Store document chunks with embeddings

        Args:
            project_name: Project identifier
            source_url: Source URL of the document
            title: Document title
            chunks: List of text chunks
            embeddings: List of embedding vectors
            metadata: Additional metadata to store

        Returns:
            Number of chunks stored
        """
        if len(chunks) != len(embeddings):
            raise ValueError(f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")

        # Delete existing documents from this source
        try:
            self.client.table("documents").delete().eq("source_url", source_url).execute()
            logger.debug(f"Deleted existing documents for {source_url}")
        except Exception as e:
            logger.warning(f"Failed to delete existing documents: {e}")

        # Prepare documents for insertion
        documents = []
        total_chunks = len(chunks)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            doc = {
                "project_name": project_name,
                "source_url": source_url,
                "title": title,
                "content": chunk,
                "chunk_index": i,
                "total_chunks": total_chunks,
                "embedding": embedding,
                "metadata": metadata or {}
            }
            documents.append(doc)

        # Insert in batches
        batch_size = 100
        inserted_count = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]

            try:
                result = self.client.table("documents").insert(batch).execute()
                inserted_count += len(batch)
                logger.debug(f"Inserted batch {i // batch_size + 1} ({len(batch)} documents)")
            except Exception as e:
                logger.error(f"Failed to insert batch: {e}")
                # Try inserting one by one as fallback
                for doc in batch:
                    try:
                        self.client.table("documents").insert(doc).execute()
                        inserted_count += 1
                    except Exception as inner_e:
                        logger.error(f"Failed to insert document: {inner_e}")

        logger.info(f"Stored {inserted_count}/{total_chunks} chunks for {source_url}")
        return inserted_count

    async def search_similar(
        self,
        query_embedding: List[float],
        project_name: Optional[str] = None,
        threshold: float = 0.7,
        limit: int = 5
    ) -> List[SearchResult]:
        """
        Search for similar documents using vector similarity

        Args:
            query_embedding: Query embedding vector
            project_name: Optional project filter
            threshold: Similarity threshold (0-1)
            limit: Max results to return

        Returns:
            List of SearchResult objects
        """
        try:
            # Call the match_documents function
            result = self.client.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                    "filter_project": project_name
                }
            ).execute()

            # Parse results
            search_results = []
            for row in result.data:
                search_results.append(SearchResult(
                    id=row["id"],
                    project_name=row["project_name"],
                    source_url=row["source_url"],
                    title=row["title"] or "",
                    content=row["content"],
                    chunk_index=row["chunk_index"],
                    metadata=row["metadata"] or {},
                    similarity=row["similarity"]
                ))

            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all indexed projects

        Returns:
            List of project dictionaries
        """
        try:
            result = self.client.table("projects").select("*").order("last_indexed_at", desc=True).execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return []

    async def get_project_stats(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a project"""
        try:
            result = self.client.table("projects").select("*").eq("name", project_name).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get project stats: {e}")
            return None

    async def delete_project(self, project_name: str) -> int:
        """
        Delete all documents for a project

        Args:
            project_name: Project to delete

        Returns:
            Number of documents deleted
        """
        try:
            # Delete documents
            result = self.client.table("documents").delete().eq("project_name", project_name).execute()
            count = len(result.data) if result.data else 0

            # Delete project entry
            self.client.table("projects").delete().eq("name", project_name).execute()

            logger.info(f"Deleted {count} documents for project {project_name}")
            return count
        except Exception as e:
            logger.error(f"Failed to delete project: {e}")
            return 0
