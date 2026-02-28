"""
Inserimento documenti di esempio con embeddings
"""
import json
from config import get_db_connection
from embeddings import get_embeddings_batch


# Documenti di esempio in italiano
SAMPLE_DOCUMENTS = [
    {
        "content": "L'intelligenza artificiale è una branca dell'informatica che si occupa di creare sistemi in grado di eseguire compiti che richiedono intelligenza umana.",
        "metadata": {"category": "AI", "language": "it"}
    },
    {
        "content": "Il machine learning è un sottoinsieme dell'intelligenza artificiale che permette ai computer di imparare dai dati senza essere esplicitamente programmati.",
        "metadata": {"category": "ML", "language": "it"}
    },
    {
        "content": "Le reti neurali sono modelli computazionali ispirati al funzionamento del cervello umano, utilizzate nel deep learning.",
        "metadata": {"category": "Deep Learning", "language": "it"}
    },
    {
        "content": "Python è uno dei linguaggi di programmazione più popolari per il machine learning e l'analisi dati.",
        "metadata": {"category": "Programming", "language": "it"}
    },
    {
        "content": "PostgreSQL è un database relazionale open source molto potente, utilizzato in molte applicazioni enterprise.",
        "metadata": {"category": "Database", "language": "it"}
    },
    {
        "content": "AWS offre servizi cloud scalabili per hosting, machine learning, analytics e molto altro.",
        "metadata": {"category": "Cloud", "language": "it"}
    },
    {
        "content": "Il transfer learning permette di riutilizzare modelli pre-addestrati per nuove applicazioni, risparmiando tempo e risorse.",
        "metadata": {"category": "ML", "language": "it"}
    },
    {
        "content": "La similarity search è una tecnica per trovare documenti o dati simili basandosi sulla distanza vettoriale.",
        "metadata": {"category": "Search", "language": "it"}
    },
    {
        "content": "Gli embeddings sono rappresentazioni vettoriali dense di testo che catturano il significato semantico delle parole.",
        "metadata": {"category": "NLP", "language": "it"}
    },
    {
        "content": "Docker è una piattaforma per sviluppare, distribuire ed eseguire applicazioni in container isolati.",
        "metadata": {"category": "DevOps", "language": "it"}
    }
]


def insert_documents(documents: list = None):
    """
    Inserisce documenti nel database con embeddings
    
    Args:
        documents: Lista di documenti (default: SAMPLE_DOCUMENTS)
    """
    if documents is None:
        documents = SAMPLE_DOCUMENTS
    
    print(f"📝 Inserimento {len(documents)} documenti...")
    
    try:
        # Genera embeddings
        print("   Genero embeddings con Bedrock...")
        texts = [doc["content"] for doc in documents]
        embeddings = get_embeddings_batch(texts)
        
        # Connessione DB
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Inserisci documenti
        print("   Inserisco nel database...")
        inserted = 0
        for doc, embedding in zip(documents, embeddings):
            cur.execute(
                """
                INSERT INTO documents (content, embedding, metadata)
                VALUES (%s, %s, %s)
                """,
                (doc["content"], embedding, json.dumps(doc["metadata"]))
            )
            inserted += 1
        
        conn.commit()
        
        # Verifica
        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]
        
        print(f"✅ {inserted} documenti inseriti con successo!")
        print(f"   Totale documenti nel database: {total}")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Errore inserimento: {e}")
        return False


def insert_custom_document(content: str, metadata: dict = None):
    """
    Inserisce un singolo documento custom
    
    Args:
        content: Testo del documento
        metadata: Metadata opzionale
    """
    print(f"📝 Inserimento documento custom...")
    
    try:
        from embeddings import get_embedding
        
        # Genera embedding
        print("   Genero embedding...")
        embedding = get_embedding(content)
        
        # Inserisci
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO documents (content, embedding, metadata)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (content, embedding, json.dumps(metadata) if metadata else None)
        )
        
        doc_id = cur.fetchone()[0]
        conn.commit()
        
        print(f"✅ Documento inserito con ID: {doc_id}")
        
        cur.close()
        conn.close()
        
        return doc_id
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--custom":
        # Inserimento custom da riga di comando
        if len(sys.argv) > 2:
            text = " ".join(sys.argv[2:])
            insert_custom_document(text)
        else:
            print("Uso: python insert_data.py --custom 'Il tuo testo qui'")
    else:
        # Inserimento documenti di esempio
        insert_documents()
