"""
Inizializzazione database e tabelle
"""
from config import get_db_connection, EMBEDDING_DIMENSION


def init_database():
    """
    Crea le tabelle necessarie per pgvector
    """
    print("🔧 Inizializzazione database...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verifica pgvector
        print("   Verifico estensione pgvector...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
        
        # Crea tabella documents
        print("   Creo tabella documents...")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                embedding vector({EMBEDDING_DIMENSION}),
                metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Crea indice per similarity search
        print("   Creo indice per similarity search...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx 
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        conn.commit()
        
        # Verifica setup
        cur.execute("SELECT COUNT(*) FROM documents")
        count = cur.fetchone()[0]
        
        print(f"✅ Database inizializzato con successo!")
        print(f"   Documenti esistenti: {count}")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Errore inizializzazione: {e}")
        return False


def reset_database():
    """
    Elimina e ricrea le tabelle (⚠️ CANCELLA TUTTI I DATI)
    """
    print("⚠️  ATTENZIONE: Questa operazione cancellerà tutti i dati!")
    confirm = input("Confermi? (scrivi 'SI' per confermare): ")
    
    if confirm != "SI":
        print("Operazione annullata.")
        return False
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print("   Elimino tabella documents...")
        cur.execute("DROP TABLE IF EXISTS documents CASCADE")
        conn.commit()
        
        print("   Ricreo struttura...")
        cur.close()
        conn.close()
        
        return init_database()
        
    except Exception as e:
        print(f"❌ Errore reset: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_database()
    else:
        init_database()
