"""
Script di test rapido end-to-end
Esegue un test completo: connessione, inserimento, ricerca
"""

def quick_test():
    """
    Esegue un test completo del sistema
    """
    print("=" * 60)
    print("🧪 TEST RAPIDO pgvector + AWS Bedrock")
    print("=" * 60)
    print()
    
    # 1. Test connessione database
    print("1️⃣  Test connessione database...")
    try:
        from config import test_connection
        if not test_connection():
            print("   ⚠️  Configura prima il database (vedi README)")
            return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    
    print()
    
    # 2. Test generazione embedding
    print("2️⃣  Test generazione embedding Bedrock...")
    try:
        from embeddings import get_embedding
        test_text = "Questo è un test di embedding"
        embedding = get_embedding(test_text)
        print(f"   ✅ Embedding generato ({len(embedding)} dimensioni)")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        print("   ⚠️  Verifica accesso a Bedrock e credenziali AWS")
        return False
    
    print()
    
    # 3. Test inserimento documento
    print("3️⃣  Test inserimento documento...")
    try:
        from insert_data import insert_custom_document
        doc_id = insert_custom_document(
            "Python è fantastico per il machine learning",
            {"category": "Test", "language": "it"}
        )
        if doc_id:
            print(f"   ✅ Documento inserito con ID: {doc_id}")
        else:
            print("   ❌ Inserimento fallito")
            return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    
    print()
    
    # 4. Test similarity search
    print("4️⃣  Test similarity search...")
    try:
        from search import search_similar
        results = search_similar("programmazione e AI", limit=3)
        if results:
            print(f"   ✅ Ricerca completata ({len(results)} risultati)")
        else:
            print("   ⚠️  Nessun risultato trovato")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    
    print()
    print("=" * 60)
    print("✅ TEST COMPLETATO CON SUCCESSO!")
    print("=" * 60)
    print()
    print("🎉 Il sistema funziona correttamente!")
    print()
    print("Comandi utili:")
    print("  - python insert_data.py          # Inserisci documenti di esempio")
    print("  - python search.py --interactive # Ricerca interattiva")
    print("  - python search.py --stats       # Statistiche database")
    print()
    
    return True


if __name__ == "__main__":
    import sys
    
    try:
        success = quick_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        sys.exit(1)
