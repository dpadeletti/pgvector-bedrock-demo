-- =============================================================================
-- migrate_hybrid_search.sql
-- Aggiunge full-text search (tsvector) alla tabella documents esistente
-- per abilitare la ricerca ibrida (semantica + keyword BM25-like)
--
-- Esegui UNA VOLTA sul DB esistente:
--   psql -h <DB_HOST> -U postgres -d postgres -f migrate_hybrid_search.sql
-- =============================================================================

-- 1. Aggiunge colonna tsvector (multilingue: italiano + inglese)
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS content_tsv tsvector;

-- 2. Popola la colonna per i documenti esistenti
--    Usa 'simple' come fallback per testi misti IT/EN
UPDATE documents
SET content_tsv = to_tsvector('simple', coalesce(content, ''));

-- 3. Indice GIN per ricerche full-text veloci (O(log n))
CREATE INDEX IF NOT EXISTS idx_documents_content_tsv
  ON documents USING gin(content_tsv);

-- 4. Trigger: aggiorna automaticamente content_tsv su INSERT/UPDATE
CREATE OR REPLACE FUNCTION update_content_tsv()
RETURNS trigger AS $$
BEGIN
  NEW.content_tsv := to_tsvector('simple', coalesce(NEW.content, ''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_content_tsv ON documents;
CREATE TRIGGER trigger_update_content_tsv
  BEFORE INSERT OR UPDATE OF content
  ON documents
  FOR EACH ROW EXECUTE FUNCTION update_content_tsv();

-- 5. Verifica
SELECT
  count(*) AS total_docs,
  count(content_tsv) AS docs_with_tsv,
  pg_size_pretty(pg_total_relation_size('documents')) AS table_size
FROM documents;
