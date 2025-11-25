"""
MCP Server for Documentation Crawling and RAG Indexing

Combines Jina AI and Crawl4AI for fast documentation indexing to Supabase.
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional, Literal

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from discovery import URLDiscoverer
from extraction import ContentExtractor
from utils import TextChunker, EmbeddingGenerator
from storage import SupabaseStore

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("jina-supabase-rag")

# Global instances
discoverer: Optional[URLDiscoverer] = None
extractor: Optional[ContentExtractor] = None
chunker: Optional[TextChunker] = None
embedder: Optional[EmbeddingGenerator] = None
store: Optional[SupabaseStore] = None


@asynccontextmanager
async def lifespan(app):
    """Initialize services on startup"""
    global discoverer, extractor, chunker, embedder, store

    logger.info("Initializing MCP server...")

    # Initialize components
    discoverer = URLDiscoverer(
        timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        max_crawl_depth=3,
        max_urls=1000
    )

    extractor = ContentExtractor(
        jina_api_key=os.getenv("JINA_API_KEY"),
        timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        max_parallel=int(os.getenv("MAX_PARALLEL_REQUESTS", "10"))
    )

    chunker = TextChunker(
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200"))
    )

    embedder = EmbeddingGenerator(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    )

    store = SupabaseStore()

    logger.info("MCP server initialized successfully")

    yield

    logger.info("Shutting down MCP server...")


# Set lifespan
mcp.app.router.lifespan_context = lifespan


@mcp.tool()
async def crawl_and_index(
    url_pattern: str,
    project_name: str,
    discovery_method: Literal["auto", "sitemap", "crawl", "manual"] = "auto",
    extraction_method: Literal["auto", "jina", "crawl4ai"] = "auto"
) -> str:
    """
    Crawl a documentation site and index to Supabase for RAG

    Args:
        url_pattern: URL or pattern to crawl (e.g., https://docs.example.com/*)
        project_name: Project identifier for isolation
        discovery_method: How to discover URLs (auto, sitemap, crawl, manual)
        extraction_method: How to extract content (auto, jina, crawl4ai)

    Returns:
        Status message with indexing details
    """
    try:
        logger.info(f"Starting crawl and index for {url_pattern} -> {project_name}")

        # Step 1: Discover URLs
        logger.info(f"Discovering URLs using method: {discovery_method}")
        discovery_result = await discoverer.discover(url_pattern, method=discovery_method)

        if not discovery_result.urls:
            error_msg = discovery_result.error or "No URLs found"
            logger.error(f"Discovery failed: {error_msg}")
            return f"❌ Discovery failed: {error_msg}"

        logger.info(f"Discovered {len(discovery_result.urls)} URLs via {discovery_result.method}")

        # Step 2: Extract content
        logger.info(f"Extracting content using method: {extraction_method}")
        extracted = await extractor.extract(discovery_result.urls, method=extraction_method)

        successful_extractions = [e for e in extracted if e.success]
        if not successful_extractions:
            return f"❌ Failed to extract content from any URLs"

        logger.info(f"Successfully extracted {len(successful_extractions)}/{len(extracted)} documents")

        # Step 3: Process each document
        total_chunks_stored = 0

        for doc in successful_extractions:
            logger.info(f"Processing {doc.url}")

            # Chunk the content
            chunks = chunker.chunk_markdown(doc.markdown or doc.content)
            chunk_texts = [c.content for c in chunks]

            logger.info(f"  Created {len(chunks)} chunks")

            # Generate embeddings
            embeddings = await embedder.generate_embeddings(chunk_texts)

            logger.info(f"  Generated {len(embeddings)} embeddings")

            # Store in Supabase
            stored = await store.store_documents(
                project_name=project_name,
                source_url=doc.url,
                title=doc.title,
                chunks=chunk_texts,
                embeddings=embeddings,
                metadata={
                    "extraction_method": doc.method,
                    "discovery_method": discovery_result.method
                }
            )

            total_chunks_stored += stored
            logger.info(f"  Stored {stored} chunks")

        # Summary
        success_msg = f"""✅ Successfully indexed to project: {project_name}

📊 Summary:
  • URLs discovered: {len(discovery_result.urls)} (via {discovery_result.method})
  • Documents extracted: {len(successful_extractions)}/{len(extracted)} (via {extraction_method})
  • Total chunks stored: {total_chunks_stored}

🔍 You can now search this content using the search_documents tool with project_name="{project_name}"
"""
        logger.info("Crawl and index completed successfully")
        return success_msg

    except Exception as e:
        error_msg = f"❌ Error during crawl and index: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


@mcp.tool()
async def search_documents(
    query: str,
    project_name: Optional[str] = None,
    limit: int = 5
) -> str:
    """
    Search indexed documents using semantic similarity

    Args:
        query: Search query text
        project_name: Optional project filter
        limit: Maximum results to return (1-20)

    Returns:
        Formatted search results
    """
    try:
        # Limit bounds checking
        limit = max(1, min(20, limit))

        logger.info(f"Searching for: '{query}' in project: {project_name or 'all'}")

        # Generate query embedding
        query_embedding = await embedder.generate_single(query)

        # Search
        results = await store.search_similar(
            query_embedding=query_embedding,
            project_name=project_name,
            threshold=0.7,
            limit=limit
        )

        if not results:
            return f"No results found for query: '{query}'"

        # Format results
        output = [f"🔍 Search Results for: '{query}'\n"]

        if project_name:
            output.append(f"📁 Project: {project_name}\n")

        output.append(f"Found {len(results)} results:\n")

        for i, result in enumerate(results, 1):
            output.append(f"\n{i}. {result.title or 'Untitled'}")
            output.append(f"   URL: {result.source_url}")
            output.append(f"   Similarity: {result.similarity:.2%}")
            output.append(f"   Chunk: {result.chunk_index + 1}")
            output.append(f"\n   Content:")
            # Truncate content to 300 chars
            content_preview = result.content[:300]
            if len(result.content) > 300:
                content_preview += "..."
            output.append(f"   {content_preview}\n")

        return "\n".join(output)

    except Exception as e:
        error_msg = f"❌ Search error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


@mcp.tool()
async def list_projects() -> str:
    """
    List all indexed projects with statistics

    Returns:
        Formatted list of projects
    """
    try:
        projects = await store.list_projects()

        if not projects:
            return "No projects found. Use crawl_and_index to create your first project."

        output = ["📚 Indexed Projects:\n"]

        for proj in projects:
            output.append(f"\n📁 {proj['name']}")
            output.append(f"   Base URL: {proj.get('base_url', 'N/A')}")
            output.append(f"   Documents: {proj.get('document_count', 0)}")

            last_indexed = proj.get('last_indexed_at')
            if last_indexed:
                output.append(f"   Last Indexed: {last_indexed}")

            if proj.get('description'):
                output.append(f"   Description: {proj['description']}")

        return "\n".join(output)

    except Exception as e:
        error_msg = f"❌ Error listing projects: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


@mcp.tool()
async def delete_project(project_name: str) -> str:
    """
    Delete a project and all its documents

    Args:
        project_name: Name of project to delete

    Returns:
        Confirmation message
    """
    try:
        count = await store.delete_project(project_name)
        return f"✅ Deleted project '{project_name}' ({count} documents)"
    except Exception as e:
        error_msg = f"❌ Error deleting project: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


if __name__ == "__main__":
    # Run the server
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8052"))
    transport = os.getenv("TRANSPORT", "sse")

    logger.info(f"Starting MCP server on {host}:{port} with {transport} transport")

    mcp.run(transport=transport)
