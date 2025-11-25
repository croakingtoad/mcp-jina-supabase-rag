  # Quick Start Guide

Get up and running with mcp-jina-supabase-rag in under 10 minutes.

## Prerequisites

- [ ] Python 3.12+
- [ ] Supabase account (free tier works)
- [ ] OpenAI API key
- [ ] Jina AI API key (optional but recommended)

## Step 1: Clone and Install

```bash
cd ~/repos
git clone <your-repo-url> mcp-jina-supabase-rag
cd mcp-jina-supabase-rag

# Install dependencies
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e .
crawl4ai-setup
```

## Step 2: Set Up Supabase

1. Go to [https://supabase.com](https://supabase.com) and create a project

2. In SQL Editor, run the schema:
```bash
# Copy the contents of supabase_schema.sql and run in Supabase SQL Editor
```

3. Get your credentials:
   - Project URL: Settings → API → Project URL
   - Service Key: Settings → API → service_role key (keep secret!)

## Step 3: Configure Environment

```bash
cp .env.example .env
nano .env  # or your favorite editor
```

Fill in:
```bash
# Required
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Optional (recommended for faster extraction)
JINA_API_KEY=jina_...
```

Get API keys:
- OpenAI: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Jina AI: [https://jina.ai](https://jina.ai) (free tier available)

## Step 4: Run the Server

```bash
# Start the MCP server
python src/main.py

# You should see:
# Starting MCP server on 0.0.0.0:8052 with sse transport
# MCP server initialized successfully
```

## Step 5: Connect to Claude Code

```bash
# Add the MCP server
claude mcp add --transport sse jina-supabase http://localhost:8052/sse

# Verify it's connected
claude mcp list
```

## Step 6: Create Slash Command

```bash
# Create the command directory if it doesn't exist
mkdir -p ~/.claude/commands

# Copy the command template
cp SLASH_COMMAND.md ~/.claude/commands/jina.md

# Edit if needed
nano ~/.claude/commands/jina.md
```

## Step 7: Test It Out!

In Claude Code, try:

```bash
# Index a small documentation site
/jina https://docs.anthropic.com/claude/docs/intro-to-claude anthropic-test

# Wait for it to complete, then search
"Search the anthropic-test project for information about API keys"

# List all projects
"List all indexed projects"
```

## Troubleshooting

### Server won't start

**Check logs:**
```bash
python src/main.py
# Look for error messages
```

**Common issues:**
- Missing environment variables → Check `.env` file
- Port already in use → Change `PORT` in `.env`
- Missing dependencies → Run `uv pip install -e .`

### Claude Code can't connect

```bash
# Check if server is running
curl http://localhost:8052/sse

# Should return SSE connection info

# Restart Claude Code
claude mcp restart jina-supabase
```

### Crawling is slow

- **Use sitemap**: `/jina https://docs.example.com/* project sitemap`
- **Get Jina API key**: Jina extraction is 3-5x faster than Crawl4AI
- **Reduce max_urls**: Edit `URLDiscoverer` max_urls parameter

### Indexing fails

**Check Supabase:**
1. Verify schema is installed (check "documents" table exists)
2. Check service key has correct permissions
3. Look at Supabase logs for errors

**Check embeddings:**
```bash
# Test OpenAI API key
python -c "import openai; openai.api_key='YOUR_KEY'; print(openai.models.list())"
```

## Next Steps

1. **Index your favorite docs**: Try indexing documentation you use frequently
2. **Create search command**: Add a `/search` command for quick queries
3. **Adjust chunking**: Modify `CHUNK_SIZE` in `.env` for your use case
4. **Set up multiple projects**: Index multiple doc sites for comprehensive RAG

## Configuration Options

Edit `.env` to customize:

```bash
# Discovery
DEFAULT_DISCOVERY_METHOD=auto  # auto, sitemap, crawl
MAX_URLS=1000

# Extraction
DEFAULT_EXTRACTION_METHOD=auto  # auto, jina, crawl4ai
MAX_PARALLEL_REQUESTS=10

# Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

## Example Workflows

### Index Multiple Documentation Sites

```bash
/jina https://docs.supabase.com/docs/* supabase
/jina https://docs.anthropic.com/claude/* anthropic
/jina https://nextjs.org/docs/* nextjs
/jina https://python.langchain.com/docs/* langchain
```

### Search Across All Projects

```
"Search all projects for rate limiting best practices"
```

### Project-Specific Search

```
"Search the supabase project for authentication examples"
```

### Clean Up Old Projects

```
"Delete the test-project"
```

## Support

- GitHub Issues: [Create an issue](https://github.com/yourusername/mcp-jina-supabase-rag/issues)
- Check logs: `python src/main.py` for detailed error messages
- Supabase logs: Check your Supabase project logs for database errors

## What's Next?

See the main [README.md](README.md) for:
- Architecture details
- Tool reference
- Development guide
- Advanced configuration
