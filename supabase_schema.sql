-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table for storing chunked content with embeddings
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    total_chunks INTEGER NOT NULL,
    embedding VECTOR(1536),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on project_name for filtering
CREATE INDEX IF NOT EXISTS idx_documents_project_name ON documents(project_name);

-- Create index on source_url for grouping
CREATE INDEX IF NOT EXISTS idx_documents_source_url ON documents(source_url);

-- Create vector similarity index using HNSW
CREATE INDEX IF NOT EXISTS idx_documents_embedding ON documents
USING hnsw (embedding vector_cosine_ops);

-- Create projects table for tracking indexed projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    base_url TEXT NOT NULL,
    description TEXT,
    document_count INTEGER DEFAULT 0,
    last_indexed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Function to search documents by similarity
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_project TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    project_name TEXT,
    source_url TEXT,
    title TEXT,
    content TEXT,
    chunk_index INTEGER,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.project_name,
        d.source_url,
        d.title,
        d.content,
        d.chunk_index,
        d.metadata,
        1 - (d.embedding <=> query_embedding) AS similarity
    FROM documents d
    WHERE 1 - (d.embedding <=> query_embedding) > match_threshold
        AND (filter_project IS NULL OR d.project_name = filter_project)
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function to update project document count
CREATE OR REPLACE FUNCTION update_project_document_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE projects
        SET document_count = document_count + 1,
            last_indexed_at = NOW(),
            updated_at = NOW()
        WHERE name = NEW.project_name;

        -- Create project if it doesn't exist
        IF NOT FOUND THEN
            INSERT INTO projects (name, base_url, document_count, last_indexed_at)
            VALUES (NEW.project_name, NEW.source_url, 1, NOW())
            ON CONFLICT (name) DO UPDATE
            SET document_count = projects.document_count + 1,
                last_indexed_at = NOW(),
                updated_at = NOW();
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE projects
        SET document_count = GREATEST(0, document_count - 1),
            updated_at = NOW()
        WHERE name = OLD.project_name;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update project document counts
CREATE TRIGGER update_project_count_trigger
AFTER INSERT OR DELETE ON documents
FOR EACH ROW
EXECUTE FUNCTION update_project_document_count();

-- Create updated_at trigger for documents
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Grant necessary permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO authenticated;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON projects TO authenticated;
