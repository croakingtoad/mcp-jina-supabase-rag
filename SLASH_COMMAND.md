# Slash Command for mcp-jina-supabase-rag

Create this file: `~/.claude/commands/jina.md`

```markdown
---
allowed-tools: mcp__jina-supabase-rag__*
argument-hint: <url_pattern> <project_name> [options]
description: Crawl documentation and index to Supabase RAG
---

# Index Documentation to Supabase

Crawl and index documentation websites to Supabase for RAG (Retrieval-Augmented Generation).

## Arguments

- **$1** - URL pattern (required)
  - Single URL: `https://docs.example.com/guide`
  - Pattern with wildcard: `https://docs.example.com/*`

- **$2** - Project name (required)
  - Alphanumeric identifier for this documentation set
  - Used to filter searches later
  - Examples: `supabase-docs`, `anthropic-claude`, `nextjs-docs`

- **$3-$N** - Optional arguments (parsed from natural language)
  - Discovery method: `sitemap` or `crawl`
  - Extraction method: `jina` or `crawl4ai`

## How It Works

1. **URL Discovery**: Tries sitemap.xml first, falls back to recursive crawling
2. **Content Extraction**: Uses Jina AI for fast extraction, Crawl4AI as fallback
3. **Chunking**: Intelligently splits content by headers and paragraphs
4. **Embedding**: Generates OpenAI embeddings for semantic search
5. **Storage**: Stores in Supabase with pgvector for similarity search

## Instructions

Parse the user's command to extract:
1. URL pattern (first positional argument)
2. Project name (second positional argument)
3. Optional preferences from remaining arguments

Call the `crawl_and_index` tool with:
- `url_pattern`: The URL or pattern
- `project_name`: The project identifier
- `discovery_method`: "auto" (default), "sitemap", or "crawl"
- `extraction_method`: "auto" (default), "jina", or "crawl4ai"

After indexing completes, inform the user they can search with:
```
/search "query text" project-name
```

## Examples

### Basic Usage
```bash
# Index Supabase documentation
/jina https://supabase.com/docs/* supabase-docs

# Index Anthropic Claude docs
/jina https://docs.anthropic.com/claude/* anthropic-claude

# Index Next.js documentation
/jina https://nextjs.org/docs/* nextjs-docs
```

### With Options
```bash
# Force sitemap discovery only
/jina https://docs.example.com/* example-docs sitemap

# Force Jina extraction
/jina https://docs.example.com/* example-docs jina

# Force Crawl4AI for both discovery and extraction
/jina https://docs.example.com/* example-docs crawl crawl4ai
```

### Single Page
```bash
# Index a single guide page
/jina https://docs.example.com/getting-started example-docs
```

## Task

Based on the provided URL pattern and project name:

1. Parse the command arguments
2. Call `mcp__jina-supabase-rag__crawl_and_index` with appropriate parameters
3. Report progress and final statistics
4. Remind user how to search the indexed content

## Searching Indexed Content

After indexing, users can search with:

```bash
# Search specific project
"Search the supabase-docs for authentication examples"
# This should call: mcp__jina-supabase-rag__search_documents

# Search all projects
"Search all indexed docs for API rate limiting"
```

Or create a companion command `/search` for convenience.
```

## Installation

```bash
# Create the command file
mkdir -p ~/.claude/commands
cat > ~/.claude/commands/jina.md << 'EOF'
[paste the markdown above]
EOF
```

## Testing

```bash
# List available commands
/help

# Try the jina command
/jina https://docs.anthropic.com/claude/docs/* anthropic-test
```
