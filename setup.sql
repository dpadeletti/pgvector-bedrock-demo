-- Setup script per pgvector su AWS RDS PostgreSQL
-- Esegui con: psql -h your-endpoint.rds.amazonaws.com -U postgres -d postgres -f setup.sql

-- Abilita l'estensione pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Crea la tabella per i documenti con embeddings
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536),  -- Titan Embeddings v1 produce vettori di 1536 dimensioni
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crea indice per similarity search (IVFFlat è efficiente per dataset piccoli/medi)
-- Per dataset molto grandi (>1M vettori), considera HNSW
CREATE INDEX IF NOT EXISTS documents_embedding_idx 
ON documents USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Verifica installazione
SELECT 
    'pgvector versione: ' || extversion as info
FROM pg_extension 
WHERE extname = 'vector';

-- Test rapido
SELECT 'Setup completato! Pronto per inserire embeddings.' as status;
