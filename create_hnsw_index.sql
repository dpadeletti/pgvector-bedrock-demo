-- create_hnsw_index.sql
--
-- Crea l indice HNSW sulla colonna embedding.
-- Da eseguire dopo il popolamento (1000+ documenti).
--
-- USO:
--   psql -h DB_HOST -U postgres -d postgres -f create_hnsw_index.sql
--
-- HNSW vs sequential scan:
--   < 1.000 doc   sequential scan e ok
--   > 1.000 doc   HNSW riduce latenza da O(n) a O(log n)
--   > 100.000 doc HNSW essenziale
--
-- Parametri HNSW:
--   m               : connessioni per nodo (default 16)
--                     piu alto = piu preciso, piu RAM
--   ef_construction : ampiezza ricerca durante build (default 64)
--                     piu alto = piu preciso, build piu lenta

-- Abilita pgvector (se non gia abilitato)
CREATE EXTENSION IF NOT EXISTS vector;

-- Indice HNSW per similarita coseno (<=>)
CREATE INDEX IF NOT EXISTS idx_documents_embedding_hnsw
    ON documents
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Verifica
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'documents'
  AND indexname = 'idx_documents_embedding_hnsw';

-- Statistiche
SELECT
    COUNT(*)                                       AS total_documents,
    pg_size_pretty(pg_total_relation_size('documents')) AS table_size
FROM documents;
