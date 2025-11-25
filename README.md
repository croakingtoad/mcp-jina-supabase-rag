# MCP Jina Supabase RAG

A lean, focused MCP server for crawling documentation websites and indexing them to Supabase for RAG (Retrieval-Augmented Generation).

## Features

- **Smart URL Discovery**: Tries sitemap.xml first, falls back to Crawl4AI recursive discovery
- **Hybrid Content Extraction**: Uses Jina AI for fast content extraction, Crawl4AI as fallback
- **Multi-Project Support**: Index multiple documentation sites to separate Supabase projects
- **Efficient Chunking**: Intelligent text chunking with configurable size and overlap
- **Vector Embeddings**: OpenAI embeddings stored in Supabase pgvector

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server Tools                         │
├─────────────────────────────────────────────────────────────┤
│  1. crawl_and_index(url_pattern, project_name)             │
│  2. list_projects()                                         │
│  3. search_documents(query, project_name, limit)           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Discovery Layer                           │
├─────────────────────────────────────────────────────────────┤
│  • Try sitemap.xml (fast)                                   │
│  • Try common doc patterns                                  │
│  • Crawl4AI recursive discovery (fallback)                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Extraction Layer                           │
├─────────────────────────────────────────────────────────────┤
│  • Jina AI Reader API (primary, fast)                       │
│  • Crawl4AI (fallback for complex pages)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Chunking & Embedding Layer                     │
├─────────────────────────────────────────────────────────────┤
│  • Smart text chunking                                      │
│  • OpenAI embeddings (text-embedding-3-small)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Supabase Storage                          │
├─────────────────────────────────────────────────────────────┤
│  • pgvector for similarity search                           │
│  • Project isolation via source column                      │
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.12+
- [Supabase account](https://supabase.com)
- [OpenAI API key](https://platform.openai.com)
- [Jina AI API key](https://jina.ai) (optional, recommended)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/mcp-jina-supabase-rag.git
cd mcp-jina-supabase-rag
```

2. Install dependencies:
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e .

# Or using pip
pip install -e .
```

3. Set up Supabase database:
```bash
# Run the SQL in supabase_schema.sql in your Supabase SQL Editor
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Usage

### Running the MCP Server

```bash
# SSE transport (recommended for remote connections)
python src/main.py

# The server will start on http://localhost:8052/sse
```

### Configure MCP Client

#### Claude Code
```bash
claude mcp add --transport sse jina-supabase http://localhost:8052/sse
```

#### Cursor / Claude Desktop
```json
{
  "mcpServers": {
    "jina-supabase": {
      "transport": "sse",
      "url": "http://localhost:8052/sse"
    }
  }
}
```

### Slash Command

Create `/home/marty/.claude/commands/jina.md`:

```markdown
---
allowed-tools: mcp__jina-supabase
argument-hint: <url_pattern> <project_name>
description: Crawl documentation and index to Supabase RAG
---

# Index Documentation to Supabase

Use the jina-supabase MCP server to crawl and index documentation.

Arguments:
- $1: URL pattern (e.g., https://docs.example.com/*)
- $2: Project name for isolation

Example:
/jina https://docs.anthropic.com/claude/* anthropic-docs
```

## Tools

### `crawl_and_index`
Crawl a documentation site and index to Supabase.

**Parameters:**
- `url_pattern` (string): URL or pattern to crawl
- `project_name` (string): Project identifier for isolation
- `discovery_method` (string, optional): `auto`, `sitemap`, or `crawl`
- `extraction_method` (string, optional): `auto`, `jina`, or `crawl4ai`

**Example:**
```python
await crawl_and_index(
    url_pattern="https://docs.supabase.com/docs/*",
    project_name="supabase-docs",
    discovery_method="auto",
    extraction_method="jina"
)
```

### `list_projects`
List all indexed projects.

**Returns:** List of project names with document counts

### `search_documents`
Search indexed documents using vector similarity.

**Parameters:**
- `query` (string): Search query
- `project_name` (string, optional): Filter by project
- `limit` (int, optional): Max results (default: 5)

**Example:**
```python
results = await search_documents(
    query="How do I set up authentication?",
    project_name="supabase-docs",
    limit=10
)
```

## Configuration

See `.env.example` for all configuration options.

### Discovery Methods

- `auto`: Try sitemap first, fallback to crawl
- `sitemap`: Only use sitemap.xml (fast, fails if no sitemap)
- `crawl`: Only use Crawl4AI recursive discovery (slow, comprehensive)

### Extraction Methods

- `auto`: Use Jina for bulk extraction (>10 URLs), Crawl4AI otherwise
- `jina`: Use Jina AI Reader API (fast, requires API key)
- `crawl4ai`: Use Crawl4AI browser automation (slow, no API key needed)

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/
```

## Differences from mcp-crawl4ai-rag

| Feature | mcp-crawl4ai-rag | mcp-jina-supabase-rag |
|---------|------------------|------------------------|
| **Focus** | Full-featured RAG with knowledge graphs | Lean documentation indexer |
| **Discovery** | Recursive only | Sitemap first, crawl fallback |
| **Extraction** | Crawl4AI only | Jina primary, Crawl4AI fallback |
| **Dependencies** | Heavy (Neo4j, etc.) | Light (core only) |
| **Use Case** | Advanced RAG with hallucination detection | Fast doc indexing |

## License

MIT

## Contributing

Contributions welcome! Please open an issue first to discuss changes.
