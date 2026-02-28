"""
Similarity search con pgvector
"""
import sys
import json
from config import get_db_connection
from embeddings import get_embedding


def search_similar(query: str, limit: int = 5, similarity_threshold: float = 0.0):
    """
    Cerca documenti simili alla query
    
    Args:
        query: Testo della query
        limit: Numero massimo di risultati
        similarity_threshold: Soglia minima di similarità (0-1)
        
    Returns:
        Lista di tuple (id, content, similarity, metadata)
    """
    print(f"🔍 Ricerca: '{query}'")
    print()
    
    try:
        # Genera embedding della query
        print("   Genero embedding della query...")
        query_embedding = get_embedding(query)
        
        # Connessione DB
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Similarity search usando distanza coseno
        # Operatore <=> calcola la distanza coseno (0 = identici, 2 = opposti)
        # Convertiamo in similarità: 1 - distanza (1 = identici, 0 = non correlati)
        cur.execute(
            """
            SELECT 
                id,
                content,
                1 - (embedding <=> %s::vector) as similarity,
                metadata
            FROM documents
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_embedding, query_embedding, similarity_threshold, query_embedding, limit)
        )
        
        results = cur.fetchall()
        
        # Mostra risultati
        print(f"📊 Trovati {len(results)} risultati:\n")
        
        for i, (doc_id, content, similarity, metadata) in enumerate(results, 1):
            print(f"{i}. [ID: {doc_id}] Similarità: {similarity:.3f}")
            if metadata:
                meta = json.loads(metadata)
                category = meta.get('category', 'N/A')
                print(f"   Categoria: {category}")
            print(f"   {content}")
            print()
        
        cur.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"❌ Errore ricerca: {e}")
        return []


def search_by_category(category: str, limit: int = 10):
    """
    Cerca documenti per categoria
    
    Args:
        category: Categoria da cercare
        limit: Numero massimo di risultati
    """
    print(f"📁 Ricerca documenti categoria: {category}")
    print()
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            SELECT id, content, metadata
            FROM documents
            WHERE metadata->>'category' = %s
            ORDER BY id
            LIMIT %s
            """,
            (category, limit)
        )
        
        results = cur.fetchall()
        
        print(f"📊 Trovati {len(results)} documenti:\n")
        
        for i, (doc_id, content, metadata) in enumerate(results, 1):
            print(f"{i}. [ID: {doc_id}]")
            print(f"   {content}")
            print()
        
        cur.close()
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return []


def get_document_stats():
    """
    Mostra statistiche sui documenti
    """
    print("📈 Statistiche database:\n")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Conteggio totale
        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]
        print(f"   Totale documenti: {total}")
        
        # Conteggio per categoria
        cur.execute("""
            SELECT 
                metadata->>'category' as category,
                COUNT(*) as count
            FROM documents
            WHERE metadata IS NOT NULL
            GROUP BY metadata->>'category'
            ORDER BY count DESC
        """)
        
        categories = cur.fetchall()
        if categories:
            print(f"\n   Documenti per categoria:")
            for cat, count in categories:
                print(f"     - {cat}: {count}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Errore: {e}")


def interactive_search():
    """
    Modalità ricerca interattiva
    """
    print("🔍 Modalità ricerca interattiva")
    print("   (scrivi 'exit' per uscire, 'stats' per statistiche)\n")
    
    while True:
        try:
            query = input("Query: ").strip()
            
            if not query:
                continue
                
            if query.lower() == 'exit':
                print("Ciao! 👋")
                break
                
            if query.lower() == 'stats':
                get_document_stats()
                print()
                continue
            
            # Parametri opzionali
            limit = 5
            
            # Esegui ricerca
            search_similar(query, limit=limit)
            
        except KeyboardInterrupt:
            print("\n\nCiao! 👋")
            break
        except Exception as e:
            print(f"❌ Errore: {e}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            # Mostra statistiche
            get_document_stats()
        elif sys.argv[1] == "--category":
            # Ricerca per categoria
            if len(sys.argv) > 2:
                search_by_category(sys.argv[2])
            else:
                print("Uso: python search.py --category NOME_CATEGORIA")
        elif sys.argv[1] == "--interactive":
            # Modalità interattiva
            interactive_search()
        else:
            # Ricerca normale
            query = " ".join(sys.argv[1:])
            search_similar(query)
    else:
        # Modalità interattiva se nessun argomento
        interactive_search()
